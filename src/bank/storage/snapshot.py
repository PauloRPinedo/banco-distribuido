"""Snapshots do estado das contas.

Sem snapshot, o replay de recuperacao teria de reler o log inteiro desde o inicio.
O snapshot guarda o estado completo em um ``idx`` conhecido; a recuperacao carrega
o snapshot e reproduz somente o que veio depois.

A gravacao e atomica: escreve em ``*.tmp``, faz fsync e so entao ``os.replace``.
Um snapshot pela metade e pior que nenhum snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..domain.accounts import AccountStore


@dataclass
class SnapshotMeta:
    """Cabecalho do snapshot."""

    last_included_idx: int
    """Indice da ultima entrada ja refletida no estado gravado."""

    last_included_epoch: int
    total_cents: int
    """Soma dos saldos no momento da gravacao, conferida ao carregar."""


def save(store: AccountStore, path: Path, last_included_epoch: int) -> SnapshotMeta:
    """Grava o estado de forma atomica e devolve o cabecalho gravado."""
    raise NotImplementedError


def load(path: Path) -> tuple[AccountStore, SnapshotMeta] | None:
    """Carrega o snapshot, ou ``None`` se nao existe.

    Deve conferir ``total_cents`` contra a soma reconstruida e recusar um arquivo
    corrompido, em vez de subir com um estado errado.
    """
    raise NotImplementedError
