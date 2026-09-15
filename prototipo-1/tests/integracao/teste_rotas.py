"""As rotas de cliente, contra um servidor a correr."""

import unittest

from tests.ajudas import CasoComServidor, exige_base, exige_pilha


@exige_pilha
@exige_base
class TesteCaminhoFeliz(CasoComServidor):

    def teste_criar_conta_devolve_o_saldo_inicial(self):
        estado, corpo = self.pedir("POST", "/contas", {
            "conta": "alice", "saldo_inicial": "100.00", "op_id": "op-criar-01"})

        self.assertEqual((estado, corpo["saldo_centavos"]), (200, 10000))

    def teste_criar_conta_devolve_o_saldo_em_texto(self):
        # O cliente não tem de dividir por 100: dividir seria pôr um float no
        # meio do dinheiro, que é o que o banco proíbe.
        _, corpo = self.pedir("POST", "/contas", {
            "conta": "alice", "saldo_inicial": "1234.56", "op_id": "op-criar-02"})

        self.assertEqual(corpo["saldo"], "R$ 1.234,56")

    def teste_saldo_inicial_e_zero_por_omissao(self):
        _, corpo = self.pedir("POST", "/contas", {"conta": "bob", "op_id": "op-criar-03"})

        self.assertEqual(corpo["saldo_centavos"], 0)

    def teste_consultar_saldo_devolve_a_conta(self):
        self.criar_conta("alice", "50.00")

        estado, corpo = self.pedir("GET", "/contas/alice")

        self.assertEqual((estado, corpo["saldo_centavos"]), (200, 5000))

    def teste_deposito_soma_ao_saldo(self):
        self.criar_conta("alice", "10.00")

        _, corpo = self.pedir("POST", "/contas/alice/deposito",
                              {"valor": "5.50", "op_id": "op-deposito-01"})

        self.assertEqual(corpo["saldo_centavos"], 1550)

    def teste_saque_subtrai_do_saldo(self):
        self.criar_conta("alice", "10.00")

        _, corpo = self.pedir("POST", "/contas/alice/saque",
                              {"valor": "4.00", "op_id": "op-saque-01"})

        self.assertEqual(corpo["saldo_centavos"], 600)

    def teste_transferencia_move_o_dinheiro_das_duas_contas(self):
        self.criar_conta("alice", "100.00")
        self.criar_conta("bob", "0")

        _, corpo = self.pedir("POST", "/transferencias", {
            "de": "alice", "para": "bob", "valor": "25.00", "op_id": "op-transf-01"})

        self.assertEqual(corpo["saldos_centavos"], {"alice": 7500, "bob": 2500})

    def teste_extrato_traz_os_movimentos_pela_ordem_em_que_aconteceram(self):
        self.criar_conta("alice", "100.00")
        self.pedir("POST", "/contas/alice/deposito",
                   {"valor": "10.00", "op_id": "op-dep-02"})
        self.pedir("POST", "/contas/alice/saque",
                   {"valor": "30.00", "op_id": "op-saq-02"})

        _, corpo = self.pedir("GET", "/contas/alice/extrato")

        self.assertEqual([movimento["tipo"] for movimento in corpo["movimentos"]],
                         ["criar_conta", "deposito", "saque"])

    def teste_extrato_da_origem_mostra_a_transferencia_com_sinal_negativo(self):
        self.criar_conta("alice", "100.00")
        self.criar_conta("bob", "0")
        self.pedir("POST", "/transferencias", {
            "de": "alice", "para": "bob", "valor": "25.00", "op_id": "op-transf-02"})

        _, corpo = self.pedir("GET", "/contas/alice/extrato")

        self.assertEqual(corpo["movimentos"][-1]["valor_centavos"], -2500)

    def teste_extrato_do_destino_mostra_a_contraparte(self):
        self.criar_conta("alice", "100.00")
        self.criar_conta("bob", "0")
        self.pedir("POST", "/transferencias", {
            "de": "alice", "para": "bob", "valor": "25.00", "op_id": "op-transf-03"})

        _, corpo = self.pedir("GET", "/contas/bob/extrato")

        self.assertEqual(corpo["movimentos"][-1]["contraparte"], "alice")

    def teste_auditoria_nao_diverge_depois_de_uma_transferencia(self):
        self.criar_conta("alice", "100.00")
        self.criar_conta("bob", "0")
        self.pedir("POST", "/transferencias", {
            "de": "alice", "para": "bob", "valor": "25.00", "op_id": "op-transf-04"})

        _, corpo = self.pedir("GET", "/auditoria")

        self.assertEqual(corpo["divergencia_centavos"], 0)

    def teste_auditoria_conta_os_depositos_e_os_saques(self):
        self.criar_conta("alice", "100.00")
        self.pedir("POST", "/contas/alice/deposito",
                   {"valor": "50.00", "op_id": "op-dep-03"})
        self.pedir("POST", "/contas/alice/saque",
                   {"valor": "20.00", "op_id": "op-saq-03"})

        _, corpo = self.pedir("GET", "/auditoria")

        self.assertEqual(corpo["total_centavos"], 13000)


@exige_pilha
@exige_base
class TesteErros(CasoComServidor):

    def teste_saque_maior_que_o_saldo_e_recusado(self):
        self.criar_conta("alice", "10.00")

        estado, _ = self.pedir("POST", "/contas/alice/saque",
                               {"valor": "500.00", "op_id": "op-sem-saldo"})

        self.assertEqual(estado, 422)

    def teste_saque_recusado_diz_quanto_ha_e_quanto_se_pediu(self):
        # A mensagem traz números concretos, não "operação inválida".
        self.criar_conta("alice", "10.00")

        _, corpo = self.pedir("POST", "/contas/alice/saque",
                              {"valor": "500.00", "op_id": "op-sem-saldo-2"})

        self.assertEqual(corpo["mensagem"],
                         "alice tem R$ 10,00 e a operação pede R$ 500,00")

    def teste_saque_recusado_nao_mexe_no_saldo(self):
        self.criar_conta("alice", "10.00")
        self.pedir("POST", "/contas/alice/saque",
                   {"valor": "500.00", "op_id": "op-sem-saldo-3"})

        _, corpo = self.pedir("GET", "/contas/alice")

        self.assertEqual(corpo["saldo_centavos"], 1000)

    def teste_conta_inexistente_e_404(self):
        estado, _ = self.pedir("GET", "/contas/ninguem")

        self.assertEqual(estado, 404)

    def teste_conta_duplicada_e_409(self):
        self.criar_conta("alice", "100.00")

        estado, _ = self.pedir("POST", "/contas", {
            "conta": "alice", "saldo_inicial": "50.00", "op_id": "op-duplicada"})

        self.assertEqual(estado, 409)

    def teste_conta_duplicada_nao_repoe_o_saldo(self):
        # O upsert que o projeto final usa faria desta segunda criação um
        # comando que repõe o saldo da alice. Dinheiro destruído (RNF-01).
        self.criar_conta("alice", "100.00")
        self.pedir("POST", "/contas", {
            "conta": "alice", "saldo_inicial": "1.00", "op_id": "op-duplicada-2"})

        _, corpo = self.pedir("GET", "/contas/alice")

        self.assertEqual(corpo["saldo_centavos"], 10000)

    def teste_valor_como_numero_json_e_recusado(self):
        # O dinheiro viaja como texto. 25.00 seria um float.
        self.criar_conta("alice", "100.00")

        estado, corpo = self.pedir("POST", "/contas/alice/deposito",
                                   {"valor": 25.00, "op_id": "op-numero"})

        self.assertEqual((estado, corpo["erro"]), (400, "valor_invalido"))

    def teste_valor_com_tres_casas_decimais_e_recusado(self):
        self.criar_conta("alice", "100.00")

        estado, _ = self.pedir("POST", "/contas/alice/deposito",
                               {"valor": "10.005", "op_id": "op-tres-casas"})

        self.assertEqual(estado, 400)

    def teste_valor_zero_e_recusado_num_deposito(self):
        self.criar_conta("alice", "100.00")

        estado, _ = self.pedir("POST", "/contas/alice/deposito",
                               {"valor": "0", "op_id": "op-zero"})

        self.assertEqual(estado, 400)

    def teste_id_de_conta_invalido_e_recusado(self):
        estado, corpo = self.pedir("POST", "/contas", {
            "conta": "Alice Silva", "op_id": "op-id-mau"})

        self.assertEqual((estado, corpo["erro"]), (400, "valor_invalido"))

    def teste_op_id_mal_formado_e_recusado(self):
        self.criar_conta("alice", "100.00")

        estado, corpo = self.pedir("POST", "/contas/alice/deposito",
                                   {"valor": "1.00", "op_id": "curto"})

        self.assertEqual((estado, corpo["erro"]), (400, "valor_invalido"))

    def teste_corpo_sem_op_id_e_recusado_com_a_forma_de_erro_do_banco(self):
        # E não com o 422 do FastAPI: há uma só forma de erro.
        self.criar_conta("alice", "100.00")

        estado, corpo = self.pedir("POST", "/contas/alice/deposito", {"valor": "1.00"})

        self.assertEqual((estado, set(corpo)), (400, {"erro", "mensagem"}))

    def teste_transferencia_para_a_mesma_conta_e_recusada(self):
        self.criar_conta("alice", "100.00")

        estado, _ = self.pedir("POST", "/transferencias", {
            "de": "alice", "para": "alice", "valor": "1.00", "op_id": "op-mesma"})

        self.assertEqual(estado, 400)

    def teste_transferencia_para_conta_inexistente_e_recusada(self):
        self.criar_conta("alice", "100.00")

        estado, _ = self.pedir("POST", "/transferencias", {
            "de": "alice", "para": "ninguem", "valor": "1.00", "op_id": "op-sem-destino"})

        self.assertEqual(estado, 404)

    def teste_transferencia_recusada_nao_mexe_na_origem(self):
        self.criar_conta("alice", "100.00")

        self.pedir("POST", "/transferencias", {
            "de": "alice", "para": "ninguem", "valor": "1.00",
            "op_id": "op-sem-destino-2"})
        _, corpo = self.pedir("GET", "/contas/alice")

        self.assertEqual(corpo["saldo_centavos"], 10000)

    def teste_extrato_de_conta_inexistente_e_404(self):
        estado, _ = self.pedir("GET", "/contas/ninguem/extrato")

        self.assertEqual(estado, 404)


if __name__ == "__main__":
    unittest.main()
