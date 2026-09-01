"""Injecao de falhas e reprodutibilidade (RF-16, RNF-06)."""

from __future__ import annotations

import pytest


def test_perda_de_replicacao_nao_confirma_operacao(live_cluster):
    """Com drop_replication=1.0 nao ha quorum: a resposta e 503 e nada e aplicado."""
    pytest.skip("fase 5")


def test_atraso_nao_causa_divergencia(live_cluster):
    """Replicas lentas atrasam a confirmacao, mas nunca produzem estados diferentes."""
    pytest.skip("fase 5")


def test_mesma_semente_produz_a_mesma_execucao():
    """RNF-06: duas execucoes com a mesma semente dao a mesma sequencia de eventos."""
    pytest.skip("fase 5")
