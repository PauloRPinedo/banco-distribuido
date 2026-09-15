"""Deduplicação por `op_id` (SPECS 3.3).

Uma operação repetida pelo cliente move o dinheiro uma só vez. É o que torna
seguro repetir um pedido de que não se sabe o desfecho — a rede caiu depois de
o servidor ter aplicado, ou antes?
"""

import unittest

from tests.ajudas import CasoComServidor, exige_base, exige_pilha


@exige_pilha
@exige_base
class TesteMesmoOpId(CasoComServidor):

    def teste_transferencia_repetida_move_o_dinheiro_uma_vez(self):
        self.criar_conta("alice", "100.00")
        self.criar_conta("bob", "0")
        pedido = {"de": "alice", "para": "bob", "valor": "25.00", "op_id": "op-repetida"}

        self.pedir("POST", "/transferencias", pedido)
        self.pedir("POST", "/transferencias", pedido)
        _, corpo = self.pedir("GET", "/contas/bob")

        self.assertEqual(corpo["saldo_centavos"], 2500)

    def teste_transferencia_repetida_devolve_o_mesmo_corpo(self):
        self.criar_conta("alice", "100.00")
        self.criar_conta("bob", "0")
        pedido = {"de": "alice", "para": "bob", "valor": "25.00", "op_id": "op-repetida-2"}

        _, primeira = self.pedir("POST", "/transferencias", pedido)
        _, segunda = self.pedir("POST", "/transferencias", pedido)

        self.assertEqual(primeira, segunda)

    def teste_mesmo_op_id_com_outro_valor_devolve_o_resultado_guardado(self):
        # SPECS 3.3 diz "devolve o resultado guardado", e é o guardado mesmo:
        # não se volta a aplicar nada, nem sequer o que o cliente agora pede.
        self.criar_conta("alice", "100.00")
        self.criar_conta("bob", "0")
        self.pedir("POST", "/transferencias", {
            "de": "alice", "para": "bob", "valor": "25.00", "op_id": "op-repetida-3"})

        self.pedir("POST", "/transferencias", {
            "de": "alice", "para": "bob", "valor": "90.00", "op_id": "op-repetida-3"})
        _, corpo = self.pedir("GET", "/contas/bob")

        self.assertEqual(corpo["saldo_centavos"], 2500)

    def teste_deposito_repetido_soma_uma_vez(self):
        self.criar_conta("alice", "10.00")
        pedido = {"valor": "5.00", "op_id": "op-dep-repetido"}

        self.pedir("POST", "/contas/alice/deposito", pedido)
        self.pedir("POST", "/contas/alice/deposito", pedido)
        _, corpo = self.pedir("GET", "/contas/alice")

        self.assertEqual(corpo["saldo_centavos"], 1500)

    def teste_repeticao_nao_acrescenta_linha_ao_extrato(self):
        self.criar_conta("alice", "10.00")
        pedido = {"valor": "5.00", "op_id": "op-dep-repetido-2"}

        self.pedir("POST", "/contas/alice/deposito", pedido)
        self.pedir("POST", "/contas/alice/deposito", pedido)
        _, corpo = self.pedir("GET", "/contas/alice/extrato")

        self.assertEqual(len(corpo["movimentos"]), 2)

    def teste_repeticao_nao_diverge_a_auditoria(self):
        self.criar_conta("alice", "100.00")
        pedido = {"valor": "5.00", "op_id": "op-dep-repetido-3"}

        self.pedir("POST", "/contas/alice/deposito", pedido)
        self.pedir("POST", "/contas/alice/deposito", pedido)
        _, corpo = self.pedir("GET", "/auditoria")

        self.assertEqual(corpo["divergencia_centavos"], 0)


if __name__ == "__main__":
    unittest.main()
