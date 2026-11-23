"""As rotas entre nós e as de operador, recusadas a quem vem de fora."""

import os
import unittest
from unittest import mock

from tests.ajudas import CasoComServidor, exige_base, exige_pilha


@exige_pilha
@exige_base
class TesteRotasProtegidas(CasoComServidor):

    REPLICACAO_FORJADA = {"epoch": 999, "id_lider": "X", "indice_anterior": 0,
                          "epoch_anterior": 0, "commit_lider": 1,
                          "entradas": [{"indice": 1, "epoch": 999, "op_id": "forjada",
                                        "tipo": "deposito", "instante": 0,
                                        "dados": {"conta": "x", "valor_centavos": 10**9}}]}

    def teste_replicacao_forjada_e_403_e_nao_muda_o_epoch(self):
        _, antes = self.pedir("GET", "/interno/estado")
        estado, corpo = self.pedir("POST", "/interno/replicar", self.REPLICACAO_FORJADA)
        _, depois = self.pedir("GET", "/interno/estado")

        self.assertEqual((estado, corpo["erro"]), (403, "nao_e_par_do_cluster"))
        self.assertEqual(depois["epoch"], antes["epoch"])

    def teste_voto_e_log_sem_chave_sao_403(self):
        estado_voto, _ = self.pedir("POST", "/interno/votar", {
            "epoch": 999, "id_candidato": "X", "ultimo_indice": 0, "ultimo_epoch": 0})
        estado_log, _ = self.pedir("GET", "/interno/log")

        self.assertEqual((estado_voto, estado_log), (403, 403))

    def teste_auditoria_exige_sessao(self):
        estado, corpo = self.pedir("GET", "/auditoria", token=None)
        self.assertEqual((estado, corpo["erro"]), (401, "sem_sessao"))

    def teste_estado_continua_publico(self):
        # O balanceador e o painel precisam dele, e não revela movimentos.
        estado, _ = self.pedir("GET", "/interno/estado", token=None)
        self.assertEqual(estado, 200)

    def teste_injecao_de_falhas_desligada_por_omissao(self):
        with mock.patch.dict(os.environ, {"FALHAS_ATIVAS": "0"}):
            estado, corpo = self.pedir("POST", "/admin/falha", {"tipo": "derrubar"})

        self.assertEqual((estado, corpo["erro"]), (403, "falhas_desativadas"))


if __name__ == "__main__":
    unittest.main()
