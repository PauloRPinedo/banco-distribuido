"""Recuperacao de estado ao reiniciar um servidor (RF-12).

Sequencia: carregar o snapshot (se houver) -> reproduzir as entradas do WAL a
partir dai -> devolver o estado pronto. Nenhuma intervencao manual, nenhuma perda
de operacao ja confirmada.

Uma sutileza importante: o WAL pode conter entradas gravadas mas **nao
confirmadas** (o no caiu entre o append e o quorum). O replay as aplica ao estado
local, e o log matching com o novo primario decide depois se elas sao confirmadas
ou truncadas. Por isso ``commit_index`` recuperado e conservador.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..domain.accounts import AccountStore
from .wal import WriteAheadLog


@dataclass
class RecoveredState:
    """Resultado do replay."""

    store: AccountStore
    wal: WriteAheadLog
    last_idx: int
    commit_index: int
    """Conservador: ate onde e seguro considerar confirmado sem falar com os pares."""


def recover(data_dir: Path, fsync_mode: str = "batch", group_commit_window_ms: int = 5) -> RecoveredState:
    """Reconstroi o estado do no a partir de ``data_dir``.

    Um diretorio vazio produz um estado inicial valido (zero contas), que e o
    caminho normal do primeiro boot.
    """
    raise NotImplementedError
