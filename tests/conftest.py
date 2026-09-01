"""Fixtures compartilhadas.

Duas formas de montar um cluster nos testes:

- ``in_memory_cluster``: nos ligados por ``InMemoryPeerClient``, sem HTTP nem
  processos. Rapido e deterministico -- e onde ficam os testes de protocolo.
- ``live_cluster``: tres processos de verdade, para exercitar SIGKILL e reinicio,
  que sao o ponto do projeto e nao dao para simular de forma honesta em memoria.
"""

from __future__ import annotations

import pytest

SEED = 42
"""Semente fixa: a mesma execucao produz o mesmo resultado (RNF-06)."""


@pytest.fixture
def in_memory_cluster():
    """Cluster de 3 nos ligados em memoria, com perda e atraso controlados."""
    pytest.skip("fase 3 do plano: depende de InMemoryPeerClient")


@pytest.fixture
def live_cluster(tmp_path):
    """Cluster de 3 processos reais em portas livres, derrubado ao fim do teste."""
    pytest.skip("fase 4 do plano: depende de bank.server")
