"""Caminho feliz ponta a ponta, com o cluster no ar (RF-01..RF-05, RF-14)."""

from __future__ import annotations

import pytest


def test_criar_consultar_depositar_sacar(live_cluster):
    pytest.skip("fase 2")


def test_transferencia_entre_contas(live_cluster):
    pytest.skip("fase 2")


def test_extrato_lista_as_operacoes_da_conta(live_cluster):
    pytest.skip("fase 2")


def test_auditoria_bate_nos_tres_nos(live_cluster):
    """Com o mesmo applied_idx, o total tem de ser identico em A, B e C.
    Divergencia aqui e bug de replicacao, e nao de arredondamento: o dinheiro
    e inteiro."""
    pytest.skip("fase 3")


def test_replica_recusa_escrita_e_indica_o_primario(live_cluster):
    pytest.skip("fase 3")
