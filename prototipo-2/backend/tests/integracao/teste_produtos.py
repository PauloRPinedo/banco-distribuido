"""Moedas, câmbio, prazo fixo e transferência externa, pela API (RF-19 a RF-25)."""

import os
import unittest

from tests.ajudas import CasoComServidor, exige_base, exige_pilha


@exige_pilha
@exige_base
class TesteCambio(CasoComServidor):

    def setUp(self) -> None:
        super().setUp()
        self.criar_conta("dolares", "100.00", moeda="USD")
        self.criar_conta("reais", "0", moeda="BRL")

    def teste_transferencia_simples_entre_moedas_e_409(self):
        estado, corpo = self.pedir("POST", "/transferencias", {
            "de": "dolares", "para": "reais", "valor": "1.00", "op_id": "op-moedas-01"})

        self.assertEqual((estado, corpo["erro"]), (409, "moedas_diferentes"))

    def teste_conversao_usa_a_taxa_de_partida(self):
        # USD -> BRL a 5,43 no esquema: 10,00 USD dão 54,30 BRL.
        estado, corpo = self.pedir("POST", "/transferencias/conversao", {
            "de": "dolares", "para": "reais", "valor": "10.00", "op_id": "op-cambio-01"})

        self.assertEqual((estado, corpo["valor_destino_centavos"], corpo["valor_destino"]),
                         (200, 5430, "R$ 54,30"))

    def teste_conversao_repetida_devolve_a_taxa_de_entao(self):
        pedido = {"de": "dolares", "para": "reais", "valor": "10.00",
                  "op_id": "op-cambio-02"}
        _, primeira = self.pedir("POST", "/transferencias/conversao", pedido)
        self.pedir("POST", "/admin/taxas", {"moeda_origem": "USD",
                                            "moeda_destino": "BRL", "taxa": "6.00"})

        _, segunda = self.pedir("POST", "/transferencias/conversao", pedido)

        self.assertEqual(segunda, primeira)

    def teste_taxa_nova_vale_para_a_conversao_seguinte(self):
        self.pedir("POST", "/admin/taxas", {"moeda_origem": "USD",
                                            "moeda_destino": "BRL", "taxa": "6.00"})

        _, corpo = self.pedir("POST", "/transferencias/conversao", {
            "de": "dolares", "para": "reais", "valor": "10.00", "op_id": "op-cambio-03"})

        self.assertEqual(corpo["valor_destino_centavos"], 6000)

    def teste_auditoria_por_moeda_nao_diverge_depois_de_um_cambio(self):
        self.pedir("POST", "/transferencias/conversao", {
            "de": "dolares", "para": "reais", "valor": "10.00", "op_id": "op-cambio-04"})

        _, corpo = self.pedir("GET", "/auditoria")

        totais = {linha["moeda"]: linha["total_centavos"] for linha in corpo["moedas"]}
        self.assertEqual((corpo["divergente"], totais), (False, {"BRL": 5430, "USD": 9000}))

    def teste_extrato_do_destino_mostra_o_valor_convertido(self):
        self.pedir("POST", "/transferencias/conversao", {
            "de": "dolares", "para": "reais", "valor": "10.00", "op_id": "op-cambio-05"})

        _, corpo = self.pedir("GET", "/contas/reais/extrato")

        self.assertEqual(corpo["movimentos"][-1]["valor"], "R$ 54,30")

    def teste_autotransferencia_entre_moedas_converte(self):
        estado, corpo = self.pedir("POST", "/transferencias/autotransferencia", {
            "de": "dolares", "para": "reais", "valor": "1.00", "op_id": "op-auto-01"})

        self.assertEqual((estado, corpo["valor_destino_centavos"]), (200, 543))

    def teste_autotransferencia_para_conta_alheia_e_403(self):
        outro = self.entrar("rui@exemplo.pt")
        self.criar_conta("do-rui", "0", token=outro, moeda="USD")

        estado, _ = self.pedir("POST", "/transferencias/autotransferencia", {
            "de": "dolares", "para": "do-rui", "valor": "1.00", "op_id": "op-auto-02"})

        self.assertEqual(estado, 403)


@exige_pilha
@exige_base
class TestePrazoFixo(CasoComServidor):

    def teste_saque_antes_do_vencimento_e_409(self):
        self.criar_conta("prazo", "100.00", produto="prazo_fixo",
                         taxa_juros="0.10", prazo_dias=30)

        estado, corpo = self.pedir("POST", "/contas/prazo/saque",
                                   {"valor": "1.00", "op_id": "op-prazo-01"})

        self.assertEqual((estado, corpo["erro"]), (409, "conta_bloqueada"))

    def teste_a_conta_mostra_o_produto_e_a_taxa(self):
        self.criar_conta("poupar", "100.00", produto="poupanca", taxa_juros="0.10")

        _, corpo = self.pedir("GET", "/contas/poupar")

        self.assertEqual((corpo["produto"], corpo["taxa_juros"]), ("poupanca", "0.100000"))

    def teste_tick_de_juros_nao_diverge_a_auditoria(self):
        self.criar_conta("poupar", "1000000.00", produto="poupanca", taxa_juros="0.10")

        estado, _ = self.pedir("POST", "/admin/juros")
        _, corpo = self.pedir("GET", "/auditoria")

        self.assertEqual((estado, corpo["divergente"]), (200, False))


@exige_pilha
@exige_base
class TesteTransferenciaExterna(CasoComServidor):

    def setUp(self) -> None:
        super().setUp()
        self.criar_conta("alice", "100.00")
        self.addCleanup(os.environ.pop, "BANCO_GATEWAY", None)

    def enviar(self, op_id: str, valor: str = "25.00") -> tuple[int, dict]:
        return self.pedir("POST", "/transferencias/externa", {
            "de": "alice", "sistema_externo_id": "banco-externo",
            "valor": valor, "op_id": op_id})

    def teste_confirmada_debita(self):
        os.environ["BANCO_GATEWAY"] = "confirma"

        estado, corpo = self.enviar("op-externa-01")

        self.assertEqual((estado, corpo["estado"], corpo["saldo_centavos"]),
                         (200, "confirmada", 7500))

    def teste_rejeitada_devolve(self):
        os.environ["BANCO_GATEWAY"] = "rejeita"

        _, corpo = self.enviar("op-externa-02")

        self.assertEqual((corpo["estado"], corpo["saldo_centavos"]), ("rejeitada", 10000))

    def teste_repetir_depois_de_confirmada_nao_devolve_mesmo_que_o_outro_banco_mude(self):
        # O desfecho fica gravado: a segunda vez não se volta a perguntar.
        os.environ["BANCO_GATEWAY"] = "confirma"
        self.enviar("op-externa-03")
        os.environ["BANCO_GATEWAY"] = "rejeita"

        _, corpo = self.enviar("op-externa-03")

        self.assertEqual((corpo["estado"], corpo["saldo_centavos"]), ("confirmada", 7500))

    def teste_sem_saldo_nem_chega_ao_outro_banco(self):
        os.environ["BANCO_GATEWAY"] = "confirma"

        estado, _ = self.enviar("op-externa-04", valor="999.00")
        _, conta = self.pedir("GET", "/contas/alice")

        self.assertEqual((estado, conta["saldo_centavos"]), (422, 10000))

    def teste_sistema_desconhecido_e_404(self):
        estado, corpo = self.pedir("POST", "/transferencias/externa", {
            "de": "alice", "sistema_externo_id": "nao-existe", "valor": "1.00",
            "op_id": "op-externa-05"})

        self.assertEqual((estado, corpo["erro"]), (404, "sistema_externo_inexistente"))

    def teste_auditoria_conta_o_que_saiu_e_o_que_voltou(self):
        os.environ["BANCO_GATEWAY"] = "confirma"
        self.enviar("op-externa-06", valor="10.00")
        os.environ["BANCO_GATEWAY"] = "rejeita"
        self.enviar("op-externa-07", valor="20.00")

        _, corpo = self.pedir("GET", "/auditoria")

        linha = self.em_reais(corpo)
        self.assertEqual((linha["total_centavos"], linha["divergencia_centavos"]),
                         (9000, 0))


if __name__ == "__main__":
    unittest.main()
