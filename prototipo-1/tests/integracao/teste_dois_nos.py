"""Dois nós contra a mesma base — a montagem dos dois portáteis.

O que estes testes provam é que a correção não depende de haver um nó só. Não
há estado nenhum em memória do servidor: cada pedido abre a sua ligação, e o
`SELECT ... FOR UPDATE`, a chave primária de `op_id` e a sequência
`operacao_numero` vivem todos na base. Dois processos em máquinas diferentes
ficam serializados pelo PostgreSQL exatamente como dois fios na mesma.

O que **não** provam, e é preciso dizer: isto não é replicação. Não há eleição
de primário (RF-09) nem confirmação por maioria (RF-10), e a base partilhada é
um ponto único de falha — se ela cair, caem os dois nós. É uma topologia que
serve a etapa 1 e não substitui a etapa 2.
"""

import random
import threading
import unittest

from tests.ajudas import CasoComDoisNos, exige_base, exige_pilha

SEMENTE = 42


def _em_paralelo(tarefas) -> list:
    """Corre as tarefas ao mesmo tempo e devolve o que cada uma devolveu."""
    resultados: list = [None] * len(tarefas)
    partida = threading.Barrier(len(tarefas))

    def correr(indice, tarefa):
        partida.wait()  # todos arrancam juntos, senão não há concorrência
        resultados[indice] = tarefa()

    fios = [threading.Thread(target=correr, args=(indice, tarefa))
            for indice, tarefa in enumerate(tarefas)]
    for fio in fios:
        fio.start()
    for fio in fios:
        fio.join(timeout=120)
    return resultados


@exige_pilha
@exige_base
class TesteEstadoPartilhado(CasoComDoisNos):

    def teste_os_dois_nos_dizem_ids_diferentes(self):
        # Que são mesmo dois processos independentes, e não dois nomes para o
        # mesmo. Todo o resto deste ficheiro assenta nisto.
        _, em_a = self.pedir("A", "GET", "/saude")
        _, em_b = self.pedir("B", "GET", "/saude")

        self.assertEqual((em_a["no"], em_b["no"]), ("A", "B"))

    def teste_conta_criada_num_no_ve_se_no_outro(self):
        self.criar_conta("A", "alice", "100.00")

        estado, corpo = self.pedir("B", "GET", "/contas/alice")

        self.assertEqual((estado, corpo["saldo_centavos"]), (200, 10000))

    def teste_deposito_num_no_aparece_no_saldo_lido_no_outro(self):
        self.criar_conta("A", "alice", "100.00")

        self.pedir("B", "POST", "/contas/alice/deposito",
                   {"valor": "25.00", "op_id": "op-dep-no-b"})
        _, corpo = self.pedir("A", "GET", "/contas/alice")

        self.assertEqual(corpo["saldo_centavos"], 12500)

    def teste_transferencia_feita_num_no_aparece_no_extrato_lido_no_outro(self):
        self.criar_conta("A", "alice", "100.00")
        self.criar_conta("A", "bob", "0")

        self.pedir("B", "POST", "/transferencias", {
            "de": "alice", "para": "bob", "valor": "25.00", "op_id": "op-tr-no-b"})
        _, corpo = self.pedir("A", "GET", "/contas/bob/extrato")

        self.assertEqual(corpo["movimentos"][-1]["contraparte"], "alice")

    def teste_a_auditoria_da_o_mesmo_nos_dois_nos(self):
        self.criar_conta("A", "alice", "100.00")
        self.criar_conta("B", "bob", "50.00")

        _, em_a = self.pedir("A", "GET", "/auditoria")
        _, em_b = self.pedir("B", "GET", "/auditoria")

        self.assertEqual(em_a, em_b)


@exige_pilha
@exige_base
class TesteConcorrenciaEntreNos(CasoComDoisNos):

    QUANTOS = 10

    def _sacar_dos_dois_lados(self):
        """Vinte saques de R$ 1,00 numa conta com R$ 10,00, dez por cada nó."""
        self.criar_conta("A", "alice", "10.00")
        tarefas = []
        for no in ("A", "B"):
            for numero in range(self.QUANTOS):
                tarefas.append(
                    lambda alvo=no, n=numero: self.pedir(
                        alvo, "POST", "/contas/alice/saque",
                        {"valor": "1.00", "op_id": f"op-saque-{alvo}-{n:03d}"}))
        return _em_paralelo(tarefas)

    def teste_saques_concorrentes_em_nos_diferentes_nao_ultrapassam_o_saldo(self):
        # Este é o teste. Se o lock fosse do processo e não da base, cada nó
        # deixaria passar os seus dez e o banco criava R$ 10,00 do nada.
        resultados = self._sacar_dos_dois_lados()

        aceites = sum(1 for estado, _ in resultados if estado == 200)
        self.assertEqual(aceites, 10)

    def teste_saques_concorrentes_em_nos_diferentes_deixam_o_saldo_a_zero(self):
        self._sacar_dos_dois_lados()

        _, corpo = self.pedir("A", "GET", "/contas/alice")

        self.assertEqual(corpo["saldo_centavos"], 0)

    def teste_transferencias_cruzadas_entre_nos_nao_dao_deadlock(self):
        # alice->bob por um nó contra bob->alice pelo outro. A ordem total dos
        # locks nasce em `contas_tocadas()` e é a mesma nos dois processos, por
        # isso o impasse continua impossível mesmo com a base pelo meio.
        self.criar_conta("A", "alice", "100.00")
        self.criar_conta("A", "bob", "100.00")

        def sentido(no, de, para, marca):
            def correr():
                return [self.pedir(no, "POST", "/transferencias",
                                   {"de": de, "para": para, "valor": "1.00",
                                    "op_id": f"op-{marca}-{numero:03d}"})
                        for numero in range(20)]
            return correr

        resultados = _em_paralelo([sentido("A", "alice", "bob", "ab"),
                                   sentido("B", "bob", "alice", "ba")])

        estados = {estado for lado in resultados for estado, _ in lado}
        self.assertNotIn(500, estados)

    def teste_transferencias_cruzadas_entre_nos_nao_mudam_o_total(self):
        self.criar_conta("A", "alice", "100.00")
        self.criar_conta("A", "bob", "100.00")

        def sentido(no, de, para, marca):
            def correr():
                for numero in range(20):
                    self.pedir(no, "POST", "/transferencias",
                               {"de": de, "para": para, "valor": "1.00",
                                "op_id": f"op-tot-{marca}-{numero:03d}"})
            return correr

        _em_paralelo([sentido("A", "alice", "bob", "ab"),
                      sentido("B", "bob", "alice", "ba")])
        _, corpo = self.pedir("A", "GET", "/auditoria")

        self.assertEqual(corpo["total_centavos"], 20000)

    def teste_carga_sorteada_nos_dois_nos_nao_diverge_a_auditoria(self):
        contas = [f"conta-{numero:02d}" for numero in range(8)]
        for conta in contas:
            self.criar_conta("A", conta, "100.00")

        def trabalho(indice):
            no = "A" if indice % 2 == 0 else "B"

            def correr():
                sorteio = random.Random(SEMENTE + indice)
                for numero in range(20):
                    de, para = sorteio.sample(contas, 2)
                    self.pedir(no, "POST", "/transferencias", {
                        "de": de, "para": para, "valor": "1.00",
                        "op_id": f"op-carga-{indice}-{numero:03d}"})
            return correr

        _em_paralelo([trabalho(indice) for indice in range(6)])
        _, corpo = self.pedir("B", "GET", "/auditoria")

        self.assertEqual(corpo["divergencia_centavos"], 0)


@exige_pilha
@exige_base
class TesteIdempotenciaEntreNos(CasoComDoisNos):

    def teste_o_mesmo_op_id_em_nos_diferentes_move_o_dinheiro_uma_vez(self):
        # O cliente não sabe se o primeiro pedido chegou a ser aplicado, e
        # repete-o — se calhar contra o outro nó, porque o primeiro não
        # respondeu. A deduplicação tem de valer para os dois.
        self.criar_conta("A", "alice", "100.00")
        self.criar_conta("A", "bob", "0")
        pedido = {"de": "alice", "para": "bob", "valor": "25.00",
                  "op_id": "op-repetida-entre-nos"}

        self.pedir("A", "POST", "/transferencias", pedido)
        self.pedir("B", "POST", "/transferencias", pedido)
        _, corpo = self.pedir("A", "GET", "/contas/bob")

        self.assertEqual(corpo["saldo_centavos"], 2500)

    def teste_o_mesmo_op_id_em_nos_diferentes_devolve_o_mesmo_corpo(self):
        self.criar_conta("A", "alice", "100.00")
        self.criar_conta("A", "bob", "0")
        pedido = {"de": "alice", "para": "bob", "valor": "25.00",
                  "op_id": "op-repetida-corpo"}

        _, em_a = self.pedir("A", "POST", "/transferencias", pedido)
        _, em_b = self.pedir("B", "POST", "/transferencias", pedido)

        self.assertEqual(em_a, em_b)

    def teste_criar_a_mesma_conta_nos_dois_nos_e_recusado_no_segundo(self):
        self.criar_conta("A", "alice", "100.00")

        estado, _ = self.pedir("B", "POST", "/contas", {
            "conta": "alice", "saldo_inicial": "1.00", "op_id": "op-dup-no-b"})

        self.assertEqual(estado, 409)

    def teste_criar_a_mesma_conta_nos_dois_nos_nao_repoe_o_saldo(self):
        self.criar_conta("A", "alice", "100.00")

        self.pedir("B", "POST", "/contas", {
            "conta": "alice", "saldo_inicial": "1.00", "op_id": "op-dup-saldo"})
        _, corpo = self.pedir("A", "GET", "/contas/alice")

        self.assertEqual(corpo["saldo_centavos"], 10000)


if __name__ == "__main__":
    unittest.main()
