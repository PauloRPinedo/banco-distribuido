"""O número da conta pela API: abrir sem id, procurar o titular, transferir."""

import unittest

from banco.dominio import numero_conta
from tests.ajudas import CasoComServidor, exige_base, exige_pilha


@exige_pilha
@exige_base
class TesteNumeroDeConta(CasoComServidor):

    def abrir(self, op_id: str, token: str | None = "", **extra) -> dict:
        estado, corpo = self.pedir("POST", "/contas", {
            "saldo_inicial": "100.00", "op_id": op_id, **extra}, token)
        self.assertEqual(estado, 200, corpo)
        return corpo

    def teste_abrir_sem_id_da_numero_valido_e_id_derivado(self):
        corpo = self.abrir("abrir-conta-1")

        self.assertEqual(corpo["agencia"], "0001")
        self.assertTrue(numero_conta.e_valido(corpo["numero"]))
        self.assertEqual(corpo["conta"], f"conta-{corpo['numero']}")

        _, listadas = self.pedir("GET", "/contas")
        self.assertEqual(listadas["contas"][0]["numero"], corpo["numero"])

    def teste_repetir_o_op_id_devolve_o_mesmo_numero(self):
        primeiro = self.abrir("abrir-repetido")
        segundo = self.abrir("abrir-repetido")

        self.assertEqual(segundo["numero"], primeiro["numero"])
        _, listadas = self.pedir("GET", "/contas")
        self.assertEqual(len(listadas["contas"]), 1)

    def teste_contas_diferentes_tem_numeros_diferentes(self):
        numeros = {self.abrir(f"abrir-conta-{i}")["numero"] for i in range(10)}
        self.assertEqual(len(numeros), 10)

    def teste_procurar_por_numero_mostra_titular_sem_saldo(self):
        corpo = self.abrir("abrir-bia", token=self.entrar("bia@exemplo.pt"))

        estado, encontrada = self.pedir(
            "GET", f"/contas/por-numero/0001%20{corpo['numero']}")

        self.assertEqual(estado, 200, encontrada)
        self.assertEqual(encontrada["titular"], "bia")
        self.assertEqual(encontrada["conta"], corpo["conta"])
        self.assertNotIn("saldo", encontrada)
        self.assertNotIn("saldo_centavos", encontrada)

    def teste_procurar_exige_sessao_e_recusa_numero_invalido(self):
        corpo = self.abrir("abrir-conta-x")
        estado_sem_sessao, _ = self.pedir(
            "GET", f"/contas/por-numero/{corpo['numero']}", token=None)
        estado_invalido, erro = self.pedir("GET", "/contas/por-numero/12345678-0")
        estado_ausente, _ = self.pedir("GET", "/contas/por-numero/12345678-9")

        self.assertEqual(estado_sem_sessao, 401)
        self.assertEqual((estado_invalido, erro["erro"]), (400, "valor_invalido"))
        self.assertEqual(estado_ausente, 404)

    def teste_transferir_pelo_numero_do_destino(self):
        origem = self.abrir("abrir-origem")
        destino = self.abrir("abrir-destino", token=self.entrar("bia@exemplo.pt"))

        estado, corpo = self.pedir("POST", "/transferencias", {
            "de": origem["conta"], "para": f"0001 / {destino['numero']}",
            "valor": "30.00", "op_id": "transf-por-numero"})

        self.assertEqual(estado, 200, corpo)
        self.assertEqual(set(corpo["saldos_centavos"]), {origem["conta"]})
        _, saldo = self.pedir("GET", f"/contas/{origem['conta']}")
        self.assertEqual(saldo["saldo_centavos"], 7_000)

    def teste_conta_com_id_escolhido_tambem_recebe_numero(self):
        self.criar_conta("alice", "10.00")
        _, conta = self.pedir("GET", "/contas/alice")
        self.assertTrue(numero_conta.e_valido(conta["numero"]))


if __name__ == "__main__":
    unittest.main()
