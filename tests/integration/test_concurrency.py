"""Operacoes concorrentes sobre as mesmas contas (RF-07, RF-08, historia 7)."""

from __future__ import annotations

import pytest


def test_saques_concorrentes_nao_estouram_o_saldo(live_cluster):
    """N clientes sacando ao mesmo tempo de uma conta que so cobre alguns saques:
    o total sacado nao pode passar do saldo inicial, e o saldo final nao pode ser
    negativo."""
    pytest.skip("fase 3")


def test_transferencias_cruzadas_concorrentes_preservam_o_total(live_cluster):
    pytest.skip("fase 3")


def test_leitura_ve_estado_consistente(live_cluster):
    """RF-07: uma leitura nunca enxerga uma transferencia pela metade."""
    pytest.skip("fase 3")
