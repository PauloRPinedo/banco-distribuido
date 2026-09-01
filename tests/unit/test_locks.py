"""Locks por conta (RF-08)."""

from __future__ import annotations

import pytest


def test_contas_diferentes_nao_se_bloqueiam():
    """Se bloqueassem, o throughput cairia ao de um lock global (RNF-04)."""
    pytest.skip("fase 2")


def test_transferencias_cruzadas_nao_travam():
    """A->B e B->A ao mesmo tempo: a ordem crescente de id impede o deadlock."""
    pytest.skip("fase 2")


def test_timeout_solta_os_locks_ja_tomados():
    pytest.skip("fase 2")
