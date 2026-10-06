"""O cluster a sério: três processos, três bases PostgreSQL, HTTP entre eles.

Cada nó é um `python -m banco.servidor` com a sua própria base
(`<base de teste>_a`, `_b`, `_c`, criadas no mesmo servidor PostgreSQL), e
fala com os outros por HTTP, como no compose e na AWS. Matar o primário é
`kill -9` ao processo: nada se fecha com educação.

Os tempos são curtos (heartbeat de 30 ms, eleição entre 150 e 300 ms) para a
suíte correr depressa; a proporção é a da demonstração.

O que se prova, contra as bases e não contra a memória dos processos:
- há um só primário, e as réplicas recusam escritas dizendo quem manda;
- cada escrita confirmada está nas três bases, com o mesmo conteúdo;
- matar o primário elege outro, com `epoch` maior, dentro do orçamento;
- nada confirmado se perde, e repetir o `op_id` não duplica;
- o nó morto volta como réplica e apanha o que perdeu;
- sem maioria não se escreve, mas lê-se;
- matar o primário a meio de transferências concorrentes não muda o total.
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from tests.ajudas import (BASE_DE_TESTE, _porta_livre,
                          esperar_ate, exige_base, exige_pilha, pedir_a)

RAIZ_DO_BACKEND = Path(__file__).resolve().parents[2]
TEMPOS = {"heartbeat_ms": 30, "timeout_eleicao_ms": [150, 300],
          "timeout_replicacao_ms": 200, "semente": 11}
IDS = ("A", "B", "C")


def _dsn_do_no(id_do_no: str) -> str:
    return f"{BASE_DE_TESTE}_{id_do_no.lower()}"


def _preparar_bases() -> None:
    """Cria (se faltar) e esvazia uma base por nó, com o esquema do projeto."""
    import psycopg2

    servidor, _, nome = BASE_DE_TESTE.rpartition("/")
    administracao = psycopg2.connect(f"{servidor}/postgres")
    administracao.autocommit = True
    try:
        with administracao.cursor() as cursor:
            for id_do_no in IDS:
                base = f"{nome}_{id_do_no.lower()}"
                cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (base,))
                if cursor.fetchone() is None:
                    cursor.execute(f'CREATE DATABASE "{base}"')
    finally:
        administracao.close()

    esquema = (RAIZ_DO_BACKEND / "db" / "esquema.sql").read_text(encoding="utf-8")
    for id_do_no in IDS:
        conexao = psycopg2.connect(_dsn_do_no(id_do_no))
        conexao.autocommit = True
        try:
            with conexao.cursor() as cursor:
                cursor.execute("SELECT to_regclass('public.conta')")
                if cursor.fetchone()[0] is None:
                    cursor.execute(esquema)
                cursor.execute("TRUNCATE operacao, conta, usuario, log_replicado")
                cursor.execute("DELETE FROM taxa_cambio WHERE vigente_desde > 0")
                cursor.execute("DELETE FROM estado_do_no")
        finally:
            conexao.close()


def impressao_digital(id_do_no: str) -> tuple:
    """O conteúdo da base de um nó, resumido. Três iguais = três bases iguais."""
    import psycopg2

    conexao = psycopg2.connect(_dsn_do_no(id_do_no))
    try:
        with conexao.cursor() as cursor:
            cursor.execute("""
                SELECT
                  (SELECT count(*) FROM usuario),
                  (SELECT md5(coalesce(string_agg(id || ':' || saldo_centavos, ','
                                                  ORDER BY id), '')) FROM conta),
                  (SELECT md5(coalesce(string_agg(op_id || ':' || tipo || ':' ||
                          valor_centavos || ':' || numero, ',' ORDER BY numero), ''))
                     FROM operacao),
                  (SELECT coalesce(sum(saldo_centavos), 0) FROM conta)
            """)
            return cursor.fetchone()
    finally:
        conexao.close()


class ClusterDeProcessos:

    def __init__(self) -> None:
        _preparar_bases()
        self.portas = {i: _porta_livre() for i in IDS}
        self.pasta = tempfile.mkdtemp(prefix="cluster-")
        self.configuracao = Path(self.pasta) / "cluster.json"
        self.configuracao.write_text(json.dumps({
            "nos": [{"id": i, "endereco": "127.0.0.1", "porta": self.portas[i]}
                    for i in IDS], **TEMPOS}), encoding="utf-8")
        self.processos: dict[str, subprocess.Popen] = {}
        self.registos: dict[str, object] = {}
        for i in IDS:
            self.arrancar(i)

    def base(self, id_do_no: str) -> str:
        return f"http://127.0.0.1:{self.portas[id_do_no]}"

    def arrancar(self, id_do_no: str) -> None:
        registo = self.registos.get(id_do_no) or tempfile.TemporaryFile()
        self.registos[id_do_no] = registo
        self.processos[id_do_no] = subprocess.Popen(
            [sys.executable, "-m", "banco.servidor", "--id", id_do_no,
             "--porta", str(self.portas[id_do_no]), "--endereco", "127.0.0.1"],
            cwd=RAIZ_DO_BACKEND,
            env={**os.environ, "BANCO_BD": _dsn_do_no(id_do_no), "NO_ID": id_do_no,
                 "CLUSTER_CONFIG": str(self.configuracao)},
            stdout=registo, stderr=subprocess.STDOUT)

    def matar(self, id_do_no: str) -> None:
        """`kill -9`: o processo não fecha nada."""
        processo = self.processos.pop(id_do_no)
        processo.kill()
        processo.wait(10)

    def vivos(self) -> list[str]:
        return list(self.processos)

    def estado(self, id_do_no: str) -> dict | None:
        try:
            estado, corpo = pedir_a(self.base(id_do_no), "GET", "/interno/estado")
        except Exception:  # noqa: BLE001 — ainda a arrancar
            return None
        return corpo if estado == 200 else None

    def primario(self, entre=None, limite: float = 10.0) -> str:
        candidatos = entre or self.vivos()
        encontrado: list[str] = []

        def ha_um():
            primarios = [i for i in candidatos
                         if (self.estado(i) or {}).get("papel") == "primário"]
            if len(primarios) == 1:
                encontrado[:] = primarios
                return True
            return False

        if not esperar_ate(ha_um, limite):
            raise AssertionError(f"nenhum primário único entre {candidatos}\n"
                                 + self.saida())
        return encontrado[0]

    def saida(self) -> str:
        partes = []
        for i, registo in self.registos.items():
            registo.seek(0)
            partes.append(f"--- nó {i} ---\n"
                          + registo.read().decode("utf-8", "replace")[-1500:])
        return "\n".join(partes)

    def parar(self) -> None:
        for i in list(self.processos):
            self.matar(i)
        for registo in self.registos.values():
            registo.close()


@exige_pilha
@exige_base
class TesteCluster(unittest.TestCase):

    def setUp(self) -> None:
        self.cluster = ClusterDeProcessos()
        self.addCleanup(self.cluster.parar)
        self.lider = self.cluster.primario()
        self.base = self.cluster.base(self.lider)
        estado, corpo = pedir_a(self.base, "POST", "/auth/registo", {
            "nome": "Ana", "email": "ana@teste.pt", "senha": "segredo-ana"})
        self.assertEqual(estado, 200, corpo)
        self.token = self.entrar(self.base)
        self.escrever("POST", "/contas", {"conta": "alice", "saldo_inicial": "100.00",
                                          "op_id": "op-criar-alice"})
        self.escrever("POST", "/contas", {"conta": "bob", "saldo_inicial": "0",
                                          "op_id": "op-criar-bob"})

    def entrar(self, base: str) -> str:
        estado, corpo = pedir_a(base, "POST", "/auth/login",
                                {"email": "ana@teste.pt", "senha": "segredo-ana"})
        self.assertEqual(estado, 200, corpo)
        return corpo["token"]

    def escrever(self, metodo, caminho, corpo, base=None, esperado=200):
        estado, resposta = pedir_a(base or self.base, metodo, caminho, corpo, self.token)
        self.assertEqual(estado, esperado, resposta)
        return resposta

    def bases_iguais(self, nos=IDS, limite: float = 5.0) -> tuple:
        """Espera que as bases dos nós indicados fiquem iguais e devolve-a."""
        impressoes: dict = {}

        def iguais():
            impressoes.update({i: impressao_digital(i) for i in nos})
            return len(set(impressoes.values())) == 1

        self.assertTrue(esperar_ate(iguais, limite), impressoes)
        return impressoes[nos[0]]

    # ------------------------------------------------------------------ testes

    def teste_ha_um_so_primario_e_as_replicas_dizem_quem_e(self):
        replica = next(i for i in IDS if i != self.lider)

        estado, corpo = pedir_a(self.cluster.base(replica), "POST",
                                "/contas/alice/deposito",
                                {"valor": "1.00", "op_id": "op-na-replica"})

        self.assertEqual((estado, corpo["erro"]), (409, "nao_sou_primario"))
        self.assertEqual(corpo["primario_provavel"], self.base)

    def teste_cada_escrita_fica_nas_tres_bases(self):
        self.escrever("POST", "/transferencias", {"de": "alice", "para": "bob",
                                                  "valor": "25.00", "op_id": "op-transf-1"})

        usuarios, _, _, total = self.bases_iguais()

        self.assertEqual((usuarios, total), (1, 10_000))

    def teste_matar_o_primario_elege_outro_e_nada_se_perde(self):
        self.escrever("POST", "/transferencias", {"de": "alice", "para": "bob",
                                                  "valor": "25.00", "op_id": "op-transf-1"})
        epoch = self.cluster.estado(self.lider)["epoch"]
        self.bases_iguais()

        inicio = time.monotonic()
        self.cluster.matar(self.lider)
        novo = self.cluster.primario()
        demorou = time.monotonic() - inicio

        # RNF-03, contra os tempos configurados: eleição máxima + uma ronda,
        # com folga para três processos Python na mesma máquina.
        orcamento = (TEMPOS["timeout_eleicao_ms"][1] + TEMPOS["timeout_replicacao_ms"]) / 1000 * 4
        self.assertLess(demorou, orcamento, f"failover em {demorou:.2f}s")
        self.assertNotEqual(novo, self.lider)
        self.assertGreater(self.cluster.estado(novo)["epoch"], epoch)

        # O utilizador e o dinheiro estão no novo primário.
        base = self.cluster.base(novo)
        token = self.entrar(base)
        estado, conta = pedir_a(base, "GET", "/contas/bob", token=token)
        self.assertEqual((estado, conta["saldo_centavos"]), (200, 2_500))

    def teste_repetir_o_op_id_depois_do_failover_nao_duplica(self):
        pedido = {"de": "alice", "para": "bob", "valor": "25.00", "op_id": "op-t-rep"}
        self.escrever("POST", "/transferencias", pedido)
        self.bases_iguais()
        self.cluster.matar(self.lider)
        novo = self.cluster.primario()

        self.escrever("POST", "/transferencias", pedido, base=self.cluster.base(novo))

        sobreviventes = tuple(self.cluster.vivos())
        self.assertEqual(self.bases_iguais(sobreviventes)[3], 10_000)
        estado, conta = pedir_a(self.cluster.base(novo), "GET", "/contas/bob",
                                token=self.token)
        self.assertEqual(conta["saldo_centavos"], 2_500)

    def teste_o_no_morto_volta_como_replica_e_apanha_o_que_perdeu(self):
        morto = self.lider
        self.cluster.matar(morto)
        novo = self.cluster.primario()
        self.escrever("POST", "/contas/alice/deposito",
                      {"valor": "10.00", "op_id": "op-sem-o-morto"},
                      base=self.cluster.base(novo))

        self.cluster.arrancar(morto)

        self.assertTrue(esperar_ate(
            lambda: (self.cluster.estado(morto) or {}).get("papel") == "réplica", 10))
        self.assertEqual(self.bases_iguais(IDS, limite=10)[3], 11_000)

    def teste_sem_maioria_nao_se_escreve_mas_le_se(self):
        for no in [i for i in IDS if i != self.lider]:
            self.cluster.matar(no)

        estado, corpo = pedir_a(self.base, "POST", "/contas/alice/deposito",
                                {"valor": "1.00", "op_id": "op-sozinho"}, self.token)
        self.assertEqual(estado, 503, corpo)
        self.assertIn(corpo["erro"], ("sem_quorum", "somente_leitura", "nao_sou_primario"))

        estado, conta = pedir_a(self.base, "GET", "/contas/alice", token=self.token)
        self.assertEqual((estado, conta["saldo_centavos"]), (200, 10_000))

    def teste_matar_o_primario_a_meio_de_transferencias_nao_muda_o_total(self):
        """RNF-01 no cenário que o projeto existe para resolver."""
        parar = threading.Event()
        confirmadas = []

        def transferir():
            numero = 0
            while not parar.is_set():
                numero += 1
                pedido = {"de": "alice", "para": "bob", "valor": "0.01",
                          "op_id": f"op-carga-{numero:05d}"}
                # Como um cliente: repete o mesmo op_id em todos os nós vivos
                # até alguém confirmar.
                for _ in range(40):
                    if parar.is_set():
                        return
                    for no in self.cluster.vivos():
                        try:
                            estado, _ = pedir_a(self.cluster.base(no), "POST",
                                                "/transferencias", pedido, self.token)
                        except Exception:  # noqa: BLE001
                            continue
                        if estado == 200:
                            confirmadas.append(pedido["op_id"])
                            break
                    else:
                        time.sleep(0.05)
                        continue
                    break

        fios = [threading.Thread(target=transferir) for _ in range(3)]
        for fio in fios:
            fio.start()
        time.sleep(0.5)
        self.cluster.matar(self.lider)
        self.cluster.primario()
        time.sleep(0.7)
        parar.set()
        for fio in fios:
            fio.join(20)

        self.assertGreater(len(confirmadas), 0)
        sobreviventes = tuple(self.cluster.vivos())
        _, _, _, total = self.bases_iguais(sobreviventes, limite=10)
        self.assertEqual(total, 10_000)
        # Cada transferência confirmada ao cliente está lá — nenhuma perdida.
        novo = self.cluster.primario()
        estado, bob = pedir_a(self.cluster.base(novo), "GET", "/contas/bob",
                              token=self.token)
        self.assertGreaterEqual(bob["saldo_centavos"], len(set(confirmadas)))


if __name__ == "__main__":
    unittest.main()
