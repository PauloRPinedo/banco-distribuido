"""Ferramentas partilhadas pelos testes.

As guardas de salto vivem aqui, num sítio só, para o motivo do salto ser
sempre o mesmo texto: quem corre a suite numa máquina limpa tem de perceber
pela leitura porque é que 15 testes não correram.

O `import` da pilha está dentro de um `try`, e não no topo de cada teste de
integração. Um `@skipUnless` numa classe não protege de um ImportError ao
carregar o módulo: o `unittest discover` reportaria erro, e não salto, e a
promessa de correr os testes sem instalar nada caía no primeiro comando.
"""

import json
import os
import socket
import threading
import time
import unittest
import urllib.error
import urllib.request

BASE_DE_TESTE = os.environ.get("BANCO_BD_TESTE")

try:
    import fastapi  # noqa: F401
    import psycopg2  # noqa: F401
    import uvicorn  # noqa: F401

    PILHA_INSTALADA = True
except ImportError:
    PILHA_INSTALADA = False

exige_pilha = unittest.skipUnless(
    PILHA_INSTALADA, "requer a pilha do servidor: pip install -r requisitos.txt")
exige_base = unittest.skipUnless(
    BASE_DE_TESTE, "requer uma base descartável: BANCO_BD_TESTE=postgresql:///banco_teste")


def esperar_ate(condicao, limite_segundos: float = 10.0) -> bool:
    """Espera por uma condição, nunca por um número de segundos inventado.

    Um `sleep` fixo é lento quando não precisa e falha quando a máquina está
    ocupada. Aqui o limite só serve para a suite não ficar pendurada.
    """
    fim = time.monotonic() + limite_segundos
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.02)
    return False


def preparar_base() -> None:
    """Cria o esquema se ainda não existir, e apaga tudo o que lá esteja.

    Recusa-se a trabalhar numa base cujo nome não diga `teste`. É uma linha, e
    é o que separa apagar dados de teste de apagar a base da demonstração na
    véspera da entrega.
    """
    import psycopg2

    if "teste" not in BASE_DE_TESTE:
        raise RuntimeError(
            f"recuso apagar {BASE_DE_TESTE!r}: o nome da base tem de conter 'teste'")

    conexao = psycopg2.connect(BASE_DE_TESTE)
    try:
        conexao.autocommit = True
        with conexao.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.conta')")
            if cursor.fetchone()[0] is None:
                caminho = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                       "db", "esquema.sql")
                with open(caminho, encoding="utf-8") as ficheiro:
                    cursor.execute(ficheiro.read())
            cursor.execute("TRUNCATE operacao, conta")
            cursor.execute("ALTER SEQUENCE operacao_numero RESTART WITH 1")
    finally:
        conexao.close()


def _porta_livre() -> int:
    with socket.socket() as tomada:
        tomada.bind(("127.0.0.1", 0))
        return tomada.getsockname()[1]


class CasoComServidor(unittest.TestCase):
    """Um servidor a sério, a falar HTTP a sério, numa porta livre.

    Não se usa o `TestClient` do FastAPI de propósito: arrastaria o `httpx`
    como quinta dependência, e sobretudo curto-circuitaria a rede. Os testes de
    concorrência só provam alguma coisa se passarem por tomadas verdadeiras e
    pelo conjunto de fios verdadeiro do servidor.
    """

    @classmethod
    def setUpClass(cls) -> None:
        import uvicorn

        os.environ["BANCO_BD"] = BASE_DE_TESTE
        preparar_base()

        cls.porta = _porta_livre()
        cls.base = f"http://127.0.0.1:{cls.porta}"
        configuracao = uvicorn.Config("banco.api.app:app", host="127.0.0.1",
                                      port=cls.porta, log_level="warning")
        cls._servidor = uvicorn.Server(configuracao)
        cls._fio = threading.Thread(target=cls._servidor.run, daemon=True)
        cls._fio.start()

        if not esperar_ate(lambda: cls.esta_de_pe(cls.base)):
            raise RuntimeError("o servidor de teste não respondeu a /saude")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._servidor.should_exit = True
        cls._fio.join(timeout=10)

    @staticmethod
    def esta_de_pe(base: str) -> bool:
        try:
            with urllib.request.urlopen(f"{base}/saude", timeout=1) as resposta:
                return resposta.status == 200
        except Exception:
            return False

    def setUp(self) -> None:
        preparar_base()

    def pedir(self, metodo: str, caminho: str, corpo: dict | None = None
              ) -> tuple[int, dict]:
        """Devolve (estado, corpo). Um erro HTTP é uma resposta, não uma exceção."""
        dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
        pedido = urllib.request.Request(
            f"{self.base}{caminho}", data=dados, method=metodo,
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(pedido, timeout=30) as resposta:
                return resposta.status, json.loads(resposta.read() or b"null")
        except urllib.error.HTTPError as erro:
            return erro.code, json.loads(erro.read() or b"null")

    def criar_conta(self, identificador: str, saldo_inicial: str = "0") -> None:
        estado, corpo = self.pedir("POST", "/contas", {
            "conta": identificador, "saldo_inicial": saldo_inicial,
            "op_id": f"criar-{identificador}"})
        self.assertEqual(estado, 200, corpo)
