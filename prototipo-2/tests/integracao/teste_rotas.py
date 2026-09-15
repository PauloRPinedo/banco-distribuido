"""As rotas de cliente, faladas por HTTP a sério (subfase 1.6)."""

import contextlib
import io
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from banco.cluster.no import No
from banco.dominio.erros import ArmazemIndisponivel
from banco.persistencia.armazem_ficheiro import ArmazemEmFicheiro
from banco.interface.servidor_http import criar_servidor


class BaseComServidor(unittest.TestCase):

    def setUp(self):
        temporario = tempfile.TemporaryDirectory()
        self.addCleanup(temporario.cleanup)

        self.no = No("A", ArmazemEmFicheiro(Path(temporario.name)))
        self.addCleanup(self.no.fechar)

        # Porta 0: o sistema escolhe uma livre. Fixar uma porta faria os testes
        # falharem quando alguém tem o servidor da demonstração a correr.
        self.servidor = criar_servidor(self.no, "127.0.0.1", 0)
        self.porta = self.servidor.server_address[1]

        # As limpezas correm ao contrário da ordem de registo, e esta tem de ser
        # exatamente: parar o ciclo, esperar pela thread, fechar o socket.
        self.addCleanup(self.servidor.server_close)

        # poll_interval curto: o shutdown() espera por uma volta do ciclo, e o
        # valor por omissão (0,5 s) somava meio segundo a cada teste.
        thread = threading.Thread(target=self.servidor.serve_forever,
                                  args=(0.01,), daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(self.servidor.shutdown)

    def pedir(self, metodo, caminho, corpo=None):
        estado, corpo_lido, _ = self.pedir_com_cabecalhos(metodo, caminho, corpo)
        return estado, corpo_lido

    def pedir_com_cabecalhos(self, metodo, caminho, corpo=None):
        dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
        pedido = urllib.request.Request(
            f"http://127.0.0.1:{self.porta}{caminho}", data=dados, method=metodo,
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(pedido, timeout=5) as resposta:
                bruto = resposta.read()
                lido = json.loads(bruto) if bruto else {}
                return resposta.status, lido, dict(resposta.headers)
        except urllib.error.HTTPError as erro:
            return erro.code, json.loads(erro.read()), dict(erro.headers)


class TesteCaminhoFeliz(BaseComServidor):

    def teste_criar_conta_devolve_201(self):
        estado, corpo = self.pedir("POST", "/contas", {
            "conta": "alice", "saldo_inicial": "100.00", "op_id": "c1"})

        self.assertEqual(estado, 201)
        self.assertEqual(corpo["saldo_centavos"], 10000)

    def teste_ciclo_completo_de_operacoes(self):
        self.pedir("POST", "/contas",
                   {"conta": "alice", "saldo_inicial": "100.00", "op_id": "c1"})
        self.pedir("POST", "/contas",
                   {"conta": "bob", "saldo_inicial": "0", "op_id": "c2"})

        self.pedir("POST", "/contas/alice/deposito",
                   {"valor": "50.00", "op_id": "d1"})
        self.pedir("POST", "/contas/alice/saque", {"valor": "20.00", "op_id": "s1"})
        self.pedir("POST", "/transferencias",
                   {"de": "alice", "para": "bob", "valor": "30.00", "op_id": "t1"})

        _, alice = self.pedir("GET", "/contas/alice")
        _, bob = self.pedir("GET", "/contas/bob")
        self.assertEqual(alice["saldo_centavos"], 10000 + 5000 - 2000 - 3000)
        self.assertEqual(bob["saldo_centavos"], 3000)

    def teste_extrato_lista_os_movimentos(self):
        self.pedir("POST", "/contas",
                   {"conta": "alice", "saldo_inicial": "100.00", "op_id": "c1"})
        self.pedir("POST", "/contas/alice/deposito",
                   {"valor": "10.00", "op_id": "d1"})

        estado, corpo = self.pedir("GET", "/contas/alice/extrato")

        self.assertEqual(estado, 200)
        self.assertEqual([m["tipo"] for m in corpo["movimentos"]],
                         ["criar_conta", "deposito"])

    def teste_auditoria_nao_diverge(self):
        self.pedir("POST", "/contas",
                   {"conta": "alice", "saldo_inicial": "100.00", "op_id": "c1"})

        estado, corpo = self.pedir("GET", "/auditoria")

        self.assertEqual(estado, 200)
        self.assertFalse(corpo["divergente"])
        self.assertEqual(corpo["total_centavos"], 10000)

    def teste_estado_do_no(self):
        estado, corpo = self.pedir("GET", "/interno/estado")

        self.assertEqual(estado, 200)
        self.assertEqual(corpo["no"], "A")
        self.assertEqual(corpo["ultimo_indice"], 0)


class TesteErros(BaseComServidor):

    def setUp(self):
        super().setUp()
        self.pedir("POST", "/contas",
                   {"conta": "alice", "saldo_inicial": "100.00", "op_id": "c1"})

    def teste_conta_inexistente_da_404(self):
        estado, corpo = self.pedir("GET", "/contas/ninguem")

        self.assertEqual(estado, 404)
        self.assertEqual(corpo["erro"], "conta_inexistente")

    def teste_conta_duplicada_da_409(self):
        estado, corpo = self.pedir("POST", "/contas", {
            "conta": "alice", "saldo_inicial": "0", "op_id": "c2"})

        self.assertEqual(estado, 409)
        self.assertEqual(corpo["erro"], "conta_duplicada")

    def teste_saldo_insuficiente_da_422(self):
        estado, corpo = self.pedir("POST", "/contas/alice/saque",
                                   {"valor": "999.00", "op_id": "s1"})

        self.assertEqual(estado, 422)
        self.assertEqual(corpo["erro"], "saldo_insuficiente")
        self.assertIn("R$ 100,00", corpo["mensagem"])

    def teste_valor_como_numero_json_e_recusado(self):
        # Aceitar um número faria o json.loads devolver um float, e um float em
        # dinheiro é a origem do desvio que RNF-01 proíbe.
        estado, corpo = self.pedir("POST", "/contas/alice/deposito",
                                   {"valor": 10.5, "op_id": "d1"})

        self.assertEqual(estado, 400)
        self.assertEqual(corpo["erro"], "valor_invalido")

    def teste_escrita_sem_op_id_e_recusada(self):
        estado, corpo = self.pedir("POST", "/contas/alice/deposito",
                                   {"valor": "10.00"})

        self.assertEqual(estado, 400)
        self.assertIn("op_id", corpo["mensagem"])

    def teste_rota_inexistente_da_404(self):
        estado, corpo = self.pedir("GET", "/nao/existe")

        self.assertEqual(estado, 404)
        self.assertEqual(corpo["erro"], "rota_inexistente")

    def teste_metodo_errado_na_rota_certa_da_404(self):
        estado, _ = self.pedir("GET", "/transferencias")

        self.assertEqual(estado, 404)

    def teste_corpo_que_nao_e_json_da_400(self):
        pedido = urllib.request.Request(
            f"http://127.0.0.1:{self.porta}/contas", data=b"isto nao e json",
            method="POST", headers={"Content-Type": "application/json"})

        try:
            urllib.request.urlopen(pedido, timeout=5)
            self.fail("devia ter falhado")
        except urllib.error.HTTPError as erro:
            self.assertEqual(erro.code, 400)


class TesteFalhaDeDisco(BaseComServidor):
    """O que acontece quando o WAL não consegue gravar.

    Importa porque o cliente tem de conseguir distinguir isto de o servidor
    estar em baixo: são dois problemas com soluções diferentes.
    """

    def teste_erro_inesperado_a_gravar_da_500_e_nao_deixa_a_ligacao_cair(self):
        self.pedir("POST", "/contas",
                   {"conta": "alice", "saldo_inicial": "100.00", "op_id": "c1"})

        def falhar(_entrada):
            raise OSError(28, "No space left on device")
        self.no.armazem.acrescentar = falhar

        # O rasto do erro é esperado e vai para stderr; aqui só faz ruído.
        with contextlib.redirect_stderr(io.StringIO()):
            estado, corpo = self.pedir("POST", "/contas/alice/deposito",
                                       {"valor": "10.00", "op_id": "d1"})

        self.assertEqual(estado, 500)
        self.assertEqual(corpo["erro"], "erro_interno")

    def teste_armazem_indisponivel_da_503_e_nao_500(self):
        """Disco cheio ou base em baixo não é "erro interno".

        A distinção é para quem está do outro lado: 500 diz "algo se partiu, não
        insistas"; 503 diz "o banco está de pé e não pôde gravar, repete com o
        mesmo op_id quando passar". As duas situações pedem coisas diferentes a
        quem está à frente do ecrã.
        """
        self.pedir("POST", "/contas",
                   {"conta": "alice", "saldo_inicial": "100.00", "op_id": "c1"})

        def sem_armazem(_entrada):
            raise ArmazemIndisponivel("não foi possível gravar no log: disco cheio")
        self.no.armazem.acrescentar = sem_armazem

        estado, corpo = self.pedir("POST", "/contas/alice/deposito",
                                   {"valor": "10.00", "op_id": "d1"})

        self.assertEqual(estado, 503)
        self.assertEqual(corpo["erro"], "armazem_indisponivel")

    def teste_armazem_indisponivel_nao_mexe_no_saldo(self):
        self.pedir("POST", "/contas",
                   {"conta": "alice", "saldo_inicial": "100.00", "op_id": "c1"})

        def sem_armazem(_entrada):
            raise ArmazemIndisponivel("não foi possível gravar no log: disco cheio")
        self.no.armazem.acrescentar = sem_armazem

        self.pedir("POST", "/contas/alice/deposito",
                   {"valor": "10.00", "op_id": "d1"})

        _, alice = self.pedir("GET", "/contas/alice")
        self.assertEqual(alice["saldo_centavos"], 10000)

    def teste_erro_inesperado_a_gravar_nao_mexe_no_saldo(self):
        self.pedir("POST", "/contas",
                   {"conta": "alice", "saldo_inicial": "100.00", "op_id": "c1"})

        def falhar(_entrada):
            raise OSError(28, "No space left on device")
        self.no.armazem.acrescentar = falhar

        with contextlib.redirect_stderr(io.StringIO()):
            self.pedir("POST", "/contas/alice/deposito",
                       {"valor": "10.00", "op_id": "d1"})

        _, alice = self.pedir("GET", "/contas/alice")
        self.assertEqual(alice["saldo_centavos"], 10000)


class TesteIdempotencia(BaseComServidor):

    def teste_repetir_a_transferencia_nao_move_duas_vezes(self):
        self.pedir("POST", "/contas",
                   {"conta": "alice", "saldo_inicial": "100.00", "op_id": "c1"})
        self.pedir("POST", "/contas",
                   {"conta": "bob", "saldo_inicial": "0", "op_id": "c2"})
        corpo = {"de": "alice", "para": "bob", "valor": "25.00", "op_id": "t1"}

        _, primeira = self.pedir("POST", "/transferencias", corpo)
        _, segunda = self.pedir("POST", "/transferencias", corpo)

        self.assertEqual(primeira, segunda)
        _, alice = self.pedir("GET", "/contas/alice")
        self.assertEqual(alice["saldo_centavos"], 7500)


if __name__ == "__main__":
    unittest.main()


class TesteCabecalhosDeOrigem(BaseComServidor):
    """CORS: sem isto, o frontend na Vercel não consegue falar com o nó.

    O navegador não mostra o corpo da resposta a uma página de outra origem se
    estes cabeçalhos faltarem — e o sintoma, do lado de quem programa a página, é
    um erro de rede que não distingue "o banco está em baixo" de "o banco
    respondeu e o navegador deitou fora".
    """

    def teste_resposta_normal_traz_a_origem(self):
        _, _, cabecalhos = self.pedir_com_cabecalhos("GET", "/auditoria")

        self.assertEqual(cabecalhos["Access-Control-Allow-Origin"], "*")

    def teste_resposta_de_erro_tambem_traz_a_origem(self):
        """Se faltasse aqui, o frontend não conseguiria ler "saldo insuficiente".

        Uma recusa do banco é informação que a página tem de mostrar; sem o
        cabeçalho na resposta de erro, viraria um erro de rede genérico.
        """
        _, _, cabecalhos = self.pedir_com_cabecalhos("GET", "/contas/ninguem")

        self.assertEqual(cabecalhos["Access-Control-Allow-Origin"], "*")

    def teste_preflight_responde_204(self):
        estado, _, cabecalhos = self.pedir_com_cabecalhos("OPTIONS", "/transferencias")

        self.assertEqual(estado, 204)
        self.assertIn("POST", cabecalhos["Access-Control-Allow-Methods"])
        self.assertIn("Content-Type", cabecalhos["Access-Control-Allow-Headers"])

    def teste_preflight_de_rota_inexistente_da_404(self):
        """O preflight não pode dizer que sim a caminhos que não existem."""
        estado, _, _ = self.pedir_com_cabecalhos("OPTIONS", "/inventada")

        self.assertEqual(estado, 404)


class TesteOrigemRestrita(unittest.TestCase):

    def teste_origem_configurada_e_respeitada(self):
        """`--origens` existe para quem quiser apertar em vez de usar `*`."""
        temporario = tempfile.TemporaryDirectory()
        self.addCleanup(temporario.cleanup)
        no = No("A", ArmazemEmFicheiro(Path(temporario.name)))
        self.addCleanup(no.fechar)
        servidor = criar_servidor(no, "127.0.0.1", 0, "https://banco.vercel.app")
        self.addCleanup(servidor.server_close)
        porta = servidor.server_address[1]
        thread = threading.Thread(target=servidor.serve_forever, args=(0.01,),
                                  daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(servidor.shutdown)

        with urllib.request.urlopen(
                f"http://127.0.0.1:{porta}/auditoria", timeout=5) as resposta:
            origem = resposta.headers["Access-Control-Allow-Origin"]

        self.assertEqual(origem, "https://banco.vercel.app")
