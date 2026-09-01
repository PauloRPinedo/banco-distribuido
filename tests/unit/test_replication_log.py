"""Log matching e regra de confirmacao (o nucleo da corretude do failover)."""

from __future__ import annotations

import pytest


class TestLogMatching:
    def test_prev_idx_divergente_e_rejeitado_com_dica_de_retrocesso(self):
        pytest.skip("fase 3")

    def test_conflito_de_epoch_no_mesmo_idx_trunca_a_cauda(self):
        pytest.skip("fase 3")

    def test_entradas_repetidas_nao_duplicam_o_log(self):
        pytest.skip("fase 3")


class TestAvancoDoCommit:
    def test_maioria_confirma_entrada_do_epoch_corrente(self):
        pytest.skip("fase 3")

    def test_entrada_de_epoch_anterior_nao_e_confirmada_por_contagem(self):
        """Regra sutil do Raft: confirmar por contagem uma entrada herdada permite
        reverte-la depois. Ela so e confirmada por arraste, junto com o NOOP do
        epoch novo."""
        pytest.skip("fase 3")

    def test_sem_maioria_o_commit_index_nao_avanca(self):
        pytest.skip("fase 3")
