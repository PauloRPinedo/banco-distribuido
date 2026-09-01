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
from . import snapshot as snapshot_module
from .wal import WriteAheadLog


@dataclass
class RecoveredState:
    """Resultado do replay."""

    store: AccountStore
    wal: WriteAheadLog
    last_idx: int
    commit_index: int
    """Conservador: ate onde e seguro considerar confirmado sem falar com os pares."""


def recover(
    data_dir: Path, fsync_mode: str = "batch", group_commit_window_ms: int = 5
) -> RecoveredState:
    """Reconstroi o estado do no a partir de ``data_dir``.

    Um diretorio vazio produz um estado inicial valido (zero contas), que e o
    caminho normal do primeiro boot.
    """
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    loaded = snapshot_module.load(data_dir / "snapshot.json")
    if loaded is None:
        store = AccountStore()
        snapshot_idx = 0
    else:
        store, meta = loaded
        snapshot_idx = meta.last_included_idx

    wal = WriteAheadLog(
        data_dir / "wal.jsonl",
        fsync_mode=fsync_mode,
        group_commit_window_ms=group_commit_window_ms,
    )

    for entry in wal.iter_all():
        if entry.idx <= snapshot_idx:
            continue
        store.apply(entry)

    # Conservador de proposito: o que este no gravou sozinho pode nao ter
    # alcancado a maioria. Quem decide o commit real e o primario, via
    # leader_commit no proximo AppendEntries.
    return RecoveredState(
        store=store,
        wal=wal,
        last_idx=wal.last_idx,
        commit_index=snapshot_idx,
    )
