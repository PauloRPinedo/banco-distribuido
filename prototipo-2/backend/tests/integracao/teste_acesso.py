"""Sessão e dono da conta (RF-26).

O banco de um nó do Protótipo 1 não tinha utilizadores: qualquer pedido
movimentava qualquer conta. Aqui uma conta tem dono, e só ele a consulta,
saca dela ou a usa como origem de uma transferência.
"""

import unittest

from tests.ajudas import CasoComServidor, exige_base, exige_pilha


@exige_pilha
@exige_base
class TesteSessao(CasoComServidor):

    def teste_registo_com_email_repetido_e_409(self):
        estado, corpo = self.pedir("POST", "/auth/registo", {
            "nome": "outra", "email": "ana@exemplo.pt", "senha": "outra-senha"})

        self.assertEqual((estado, corpo["erro"]), (409, "email_duplicado"))

    def teste_login_com_senha_errada_e_401(self):
        estado, corpo = self.pedir("POST", "/auth/login", {
            "email": "ana@exemplo.pt", "senha": "errada"})

        self.assertEqual((estado, corpo["erro"]), (401, "credenciais_invalidas"))

    def teste_abrir_conta_sem_sessao_e_401(self):
        estado, corpo = self.pedir("POST", "/contas", {
            "conta": "alice", "op_id": "op-sem-sessao"}, token=None)

        self.assertEqual((estado, corpo["erro"]), (401, "sem_sessao"))

    def teste_token_alterado_e_401(self):
        estado, _ = self.pedir("GET", "/contas", token=self.token + "x")

        self.assertEqual(estado, 401)

    def teste_listar_devolve_so_as_contas_de_quem_pede(self):
        self.criar_conta("alice", "10.00")
        outro = self.entrar("rui@exemplo.pt")
        self.criar_conta("bob", "5.00", token=outro)

        _, corpo = self.pedir("GET", "/contas")

        self.assertEqual([conta["conta"] for conta in corpo["contas"]], ["alice"])


@exige_pilha
@exige_base
class TesteDono(CasoComServidor):

    def setUp(self) -> None:
        super().setUp()
        self.criar_conta("alice", "100.00")
        self.intruso = self.entrar("rui@exemplo.pt")
        self.criar_conta("bob", "0", token=self.intruso)

    def teste_consultar_conta_alheia_e_403(self):
        estado, corpo = self.pedir("GET", "/contas/alice", token=self.intruso)

        self.assertEqual((estado, corpo["erro"]), (403, "proibido"))

    def teste_extrato_de_conta_alheia_e_403(self):
        estado, _ = self.pedir("GET", "/contas/alice/extrato", token=self.intruso)

        self.assertEqual(estado, 403)

    def teste_sacar_de_conta_alheia_e_403_e_nao_mexe_no_saldo(self):
        estado, _ = self.pedir("POST", "/contas/alice/saque",
                               {"valor": "10.00", "op_id": "op-roubo-01"},
                               token=self.intruso)
        _, corpo = self.pedir("GET", "/contas/alice")

        self.assertEqual((estado, corpo["saldo_centavos"]), (403, 10000))

    def teste_transferir_a_partir_de_conta_alheia_e_403(self):
        estado, _ = self.pedir("POST", "/transferencias", {
            "de": "alice", "para": "bob", "valor": "10.00",
            "op_id": "op-roubo-02"}, token=self.intruso)

        self.assertEqual(estado, 403)

    def teste_repetir_o_op_id_de_outro_nao_devolve_a_resposta_dele(self):
        # Sem o passo 0 do serviço de escrita, o intruso recebia a resposta
        # guardada — com o saldo da alice lá dentro.
        self.pedir("POST", "/contas/alice/saque",
                   {"valor": "1.00", "op_id": "op-da-ana-01"})

        estado, _ = self.pedir("POST", "/contas/alice/saque",
                               {"valor": "1.00", "op_id": "op-da-ana-01"},
                               token=self.intruso)

        self.assertEqual(estado, 403)

    def teste_transferir_para_conta_alheia_e_permitido(self):
        estado, corpo = self.pedir("POST", "/transferencias", {
            "de": "alice", "para": "bob", "valor": "10.00", "op_id": "op-presente"})

        self.assertEqual((estado, corpo["saldos_centavos"]["bob"]), (200, 1000))

    def teste_depositar_em_conta_alheia_e_permitido(self):
        estado, _ = self.pedir("POST", "/contas/bob/deposito",
                               {"valor": "1.00", "op_id": "op-balcao-01"})

        self.assertEqual(estado, 200)


if __name__ == "__main__":
    unittest.main()
