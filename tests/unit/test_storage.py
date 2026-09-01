"""WAL, snapshot e recuperacao (RF-12, RNF-02)."""

from __future__ import annotations

import pytest


class TestWal:
    def test_append_e_releitura_preservam_a_ordem(self):
        pytest.skip("fase 2")

    def test_linha_final_truncada_e_descartada_na_leitura(self):
        """Uma queda no meio de um append deixa meia linha; ela nao pode virar
        uma entrada valida nem impedir o servidor de subir."""
        pytest.skip("fase 2")

    def test_truncate_from_remove_apenas_do_indice_em_diante(self):
        pytest.skip("fase 3")

    def test_truncate_abaixo_do_commit_index_e_recusado(self):
        """Apagar algo ja confirmado seria perder dinheiro confirmado."""
        pytest.skip("fase 3")


class TestRecuperacao:
    def test_replay_reconstroi_o_estado_exato(self):
        pytest.skip("fase 2")

    def test_snapshot_mais_wal_equivale_ao_wal_completo(self):
        pytest.skip("fase 2")

    def test_snapshot_corrompido_e_recusado(self):
        pytest.skip("fase 2")
