"""O CLI contra um servidor a sério, em processos separados (subfase 1.7).

Aqui usam-se processos e não threads de propósito: é a única forma de verificar
os códigos de saída e de confirmar que a saída redirecionada sai sem cor.
"""

import socket
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
LIMITE_SEGUNDOS = 15

OK = 0
RECUSADO = 1
USO_INCORRETO = 2
SEM_SERVIDOR = 3


def _porta_livre() -> int:
    with socket.socket() as tomada:
        tomada.bind(("127.0.0.1", 0))
        return tomada.getsockname()[1]


def _esperar_por(url: str, limite: float) -> bool:
    """Espera por uma condição, não por um número de segundos.

    Um `sleep(2)` passa na máquina de quem o escreveu e falha na do colega.
    """
    import time
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        try:
            with urllib.request.urlopen(url, timeout=0.5):
                return True
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            continue
    return False


class TesteCli(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._temporario = tempfile.TemporaryDirectory()
        cls.porta = _porta_livre()
        cls.servidor = subprocess.Popen(
            # `--armazem ficheiro`: a suíte tem de correr numa máquina sem
            # PostgreSQL instalado.
            [sys.executable, "-m", "banco.servidor", "--id", "A",
             "--porta", str(cls.porta), "--endereco", "127.0.0.1",
             "--armazem", "ficheiro", "--dados", cls._temporario.name],
            cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        pronto = _esperar_por(
            f"http://127.0.0.1:{cls.porta}/interno/estado", LIMITE_SEGUNDOS)
        if not pronto:
            cls.servidor.kill()
            raise AssertionError("o servidor não arrancou a tempo")

    @classmethod
    def tearDownClass(cls):
        # communicate() em vez de wait(): lê e fecha os canos. Só esperar deixa
        # os descritores abertos e o interpretador queixa-se no fim da suíte.
        cls.servidor.terminate()
        try:
            cls.servidor.communicate(timeout=LIMITE_SEGUNDOS)
        except subprocess.TimeoutExpired:
            cls.servidor.kill()
            cls.servidor.communicate()
        cls._temporario.cleanup()

    def cli(self, *argumentos, porta=None):
        return subprocess.run(
            [sys.executable, "-m", "banco.cli", "--servidor",
             f"http://127.0.0.1:{porta or self.porta}", *argumentos],
            cwd=RAIZ, capture_output=True, text=True, timeout=LIMITE_SEGUNDOS)

    def teste_ciclo_completo_devolve_zero(self):
        self.assertEqual(self.cli("criar-conta", "ana", "--saldo",
                                  "100.00").returncode, OK)
        self.assertEqual(self.cli("criar-conta", "beto").returncode, OK)
        self.assertEqual(self.cli("transferir", "ana", "beto",
                                  "25.50").returncode, OK)
        self.assertEqual(self.cli("extrato", "ana").returncode, OK)
        self.assertEqual(self.cli("auditoria").returncode, OK)

    def teste_dinheiro_sai_no_formato_portugues(self):
        self.cli("criar-conta", "carla", "--saldo", "1234.56")

        resultado = self.cli("saldo", "carla")

        self.assertIn("R$ 1.234,56", resultado.stdout)

    def teste_saida_redirecionada_nao_leva_cor(self):
        # capture_output dá um cano, não um terminal: não pode sair um único
        # escape ANSI, senão os registos da demonstração ficam ilegíveis.
        self.cli("criar-conta", "diana", "--saldo", "10.00")

        resultado = self.cli("saldo", "diana")

        self.assertNotIn("\033", resultado.stdout)
        self.assertNotIn("\033", resultado.stderr)

    def teste_saldo_insuficiente_sai_com_um(self):
        self.cli("criar-conta", "elias", "--saldo", "1.00")

        resultado = self.cli("sacar", "elias", "500.00")

        self.assertEqual(resultado.returncode, RECUSADO)
        self.assertIn("saldo insuficiente", resultado.stderr)

    def teste_conta_inexistente_sai_com_um(self):
        resultado = self.cli("saldo", "fantasma")

        self.assertEqual(resultado.returncode, RECUSADO)

    def teste_erro_tem_tres_linhas_e_a_ultima_diz_o_que_fazer(self):
        resultado = self.cli("saldo", "fantasma")

        linhas = [l for l in resultado.stderr.splitlines() if l.strip()]
        self.assertEqual(len(linhas), 3)
        self.assertTrue(linhas[2].strip().startswith("→"))

    def teste_valor_mal_escrito_sai_com_dois(self):
        self.cli("criar-conta", "gil", "--saldo", "10.00")

        resultado = self.cli("depositar", "gil", "10.005")

        self.assertEqual(resultado.returncode, USO_INCORRETO)

    def teste_comando_inexistente_sai_com_dois(self):
        resultado = self.cli("voar")

        self.assertEqual(resultado.returncode, USO_INCORRETO)

    def teste_servidor_em_baixo_sai_com_tres(self):
        # Distinguir isto de uma recusa por regra é o ponto todo dos códigos.
        resultado = self.cli("auditoria", porta=_porta_livre())

        self.assertEqual(resultado.returncode, SEM_SERVIDOR)
        self.assertIn("não respondeu", resultado.stderr)

    def teste_repetir_nao_duplica_porque_o_op_id_muda(self):
        # Dois comandos iguais são duas operações: cada um gera o seu op_id.
        # A deduplicação protege a *retentativa* da mesma operação, não o
        # utilizador que escreve o comando duas vezes de propósito.
        self.cli("criar-conta", "hugo", "--saldo", "100.00")

        self.cli("depositar", "hugo", "10.00")
        self.cli("depositar", "hugo", "10.00")

        self.assertIn("R$ 120,00", self.cli("saldo", "hugo").stdout)


if __name__ == "__main__":
    unittest.main()
