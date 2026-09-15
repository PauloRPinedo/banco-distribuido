"""A invariante do dinheiro debaixo de concorrência real (RNF-01, RF-07, RF-08).

O teste unitário da invariante corre num só fio e prova que as operações estão
certas. Estes provam outra coisa: que continuam certas quando várias chegam ao
mesmo tempo à mesma conta. É o que o `SELECT ... FOR UPDATE` do repositório
garante, e sem ele `teste_saques_concorrentes_nao_ultrapassam_o_saldo` falha —
foi verificado a tirar a cláusula.
"""

import random
import threading
import unittest

from tests.ajudas import CasoComServidor, exige_base, exige_pilha

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
        fio.join(timeout=60)
    return resultados


@exige_pilha
@exige_base
class TesteSaquesConcorrentes(CasoComServidor):

    QUANTOS = 20

    def _sacar_todos(self):
        self.criar_conta("alice", "10.00")
        tarefas = [
            (lambda n=numero: self.pedir("POST", "/contas/alice/saque",
                                         {"valor": "1.00", "op_id": f"op-saque-{n:03d}"}))
            for numero in range(self.QUANTOS)
        ]
        return _em_paralelo(tarefas)

    def teste_saques_concorrentes_nao_ultrapassam_o_saldo(self):
        # 20 fios pedem R$ 1,00 de uma conta com R$ 10,00. Sem lock, dois fios
        # leem o mesmo saldo e escrevem por cima um do outro: passavam mais de
        # 10, e o banco criava dinheiro.
        resultados = self._sacar_todos()

        aceites = sum(1 for estado, _ in resultados if estado == 200)
        self.assertEqual(aceites, 10)

    def teste_saques_concorrentes_recusam_os_restantes_por_saldo(self):
        resultados = self._sacar_todos()

        recusados = sum(1 for estado, _ in resultados if estado == 422)
        self.assertEqual(recusados, 10)

    def teste_saques_concorrentes_deixam_o_saldo_a_zero(self):
        self._sacar_todos()

        _, corpo = self.pedir("GET", "/contas/alice")

        self.assertEqual(corpo["saldo_centavos"], 0)

    def teste_saques_concorrentes_nao_divergem_a_auditoria(self):
        self._sacar_todos()

        _, corpo = self.pedir("GET", "/auditoria")

        self.assertEqual(corpo["divergencia_centavos"], 0)


@exige_pilha
@exige_base
class TesteTransferenciasCruzadas(CasoComServidor):

    QUANTAS = 25

    def _cruzar(self):
        self.criar_conta("alice", "100.00")
        self.criar_conta("bob", "100.00")

        def num_sentido(de, para, marca):
            def correr():
                return [self.pedir("POST", "/transferencias",
                                   {"de": de, "para": para, "valor": "1.00",
                                    "op_id": f"op-{marca}-{numero:03d}"})
                        for numero in range(self.QUANTAS)]
            return correr

        return _em_paralelo([num_sentido("alice", "bob", "ab"),
                             num_sentido("bob", "alice", "ba")])

    def teste_transferencias_cruzadas_nao_dao_deadlock(self):
        # alice->bob contra bob->alice é o deadlock clássico. A ordem total dos
        # locks, que nasce em `contas_tocadas()`, torna-o impossível: sem ela o
        # PostgreSQL deteta o impasse e devolve erro.
        resultados = self._cruzar()

        estados = {estado for sentido in resultados for estado, _ in sentido}
        self.assertNotIn(500, estados)

    def teste_transferencias_cruzadas_nao_mudam_o_total(self):
        self._cruzar()

        _, corpo = self.pedir("GET", "/auditoria")

        self.assertEqual(corpo["total_centavos"], 20000)


@exige_pilha
@exige_base
class TesteMuitasContas(CasoComServidor):

    CONTAS = [f"conta-{numero:02d}" for numero in range(10)]
    FIOS = 8
    POR_FIO = 25

    def teste_transferencias_concorrentes_nao_mudam_o_total(self):
        # O teste que CODESTYLE 6 diz não poder faltar, agora com rede pelo
        # meio: sortear milhares de operações e verificar que a soma não mudou.
        for conta in self.CONTAS:
            self.criar_conta(conta, "100.00")

        def trabalho(indice):
            def correr():
                sorteio = random.Random(SEMENTE + indice)
                for numero in range(self.POR_FIO):
                    de, para = sorteio.sample(self.CONTAS, 2)
                    self.pedir("POST", "/transferencias", {
                        "de": de, "para": para, "valor": "1.00",
                        "op_id": f"op-{indice}-{numero:03d}"})
            return correr

        _em_paralelo([trabalho(indice) for indice in range(self.FIOS)])
        _, corpo = self.pedir("GET", "/auditoria")

        self.assertEqual(corpo["divergencia_centavos"], 0)

    def teste_nenhum_saldo_fica_negativo(self):
        for conta in self.CONTAS:
            self.criar_conta(conta, "5.00")

        def trabalho(indice):
            def correr():
                sorteio = random.Random(SEMENTE + indice)
                for numero in range(self.POR_FIO):
                    de, para = sorteio.sample(self.CONTAS, 2)
                    self.pedir("POST", "/transferencias", {
                        "de": de, "para": para, "valor": "2.00",
                        "op_id": f"op-neg-{indice}-{numero:03d}"})
            return correr

        _em_paralelo([trabalho(indice) for indice in range(self.FIOS)])

        saldos = [self.pedir("GET", f"/contas/{conta}")[1]["saldo_centavos"]
                  for conta in self.CONTAS]
        self.assertTrue(all(saldo >= 0 for saldo in saldos), saldos)


if __name__ == "__main__":
    unittest.main()
