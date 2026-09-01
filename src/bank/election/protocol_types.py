"""Tipos auxiliares da eleicao."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ElectionOutcome(str, Enum):
    """Como terminou uma candidatura."""

    WON = "won"
    LOST = "lost"
    """Nao alcancou a maioria dentro do tempo; nova rodada sera sorteada."""

    STEPPED_DOWN = "stepped_down"
    """Chegou um epoch maior durante a apuracao: outro no ja e primario."""


@dataclass
class VoteTally:
    """Contagem parcial de votos, exposta em ``/admin/status`` durante uma eleicao."""

    epoch: int
    granted: int
    needed: int
    """Maioria simples: ``len(nodes) // 2 + 1``."""
