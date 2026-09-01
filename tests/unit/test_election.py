"""Eleicao: restricao de voto e fencing por epoch (RF-09)."""

from __future__ import annotations

import pytest


class TestConcessaoDeVoto:
    def test_nao_vota_duas_vezes_no_mesmo_epoch(self):
        """Se votasse duas vezes, dois candidatos poderiam ter maioria."""
        pytest.skip("fase 4")

    def test_recusa_candidato_com_log_atrasado(self):
        """A garantia central: quem tem log atrasado nao pode virar primario,
        senao operacoes confirmadas sumiriam."""
        pytest.skip("fase 4")

    def test_voto_e_persistido_antes_da_resposta(self):
        """Votar, cair e esquecer o voto elegeria dois primarios."""
        pytest.skip("fase 4")


class TestFencing:
    def test_primario_antigo_com_epoch_menor_e_rejeitado(self):
        pytest.skip("fase 4")

    def test_epoch_maior_rebaixa_o_primario_atual(self):
        pytest.skip("fase 4")
