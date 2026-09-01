"""Snapshots do estado das contas.

Sem snapshot, o replay de recuperacao teria de reler o log inteiro desde o inicio.
O snapshot guarda o estado completo em um ``idx`` conhecido; a recuperacao carrega
o snapshot e reproduz somente o que veio depois.

A gravacao e atomica: escreve em ``*.tmp``, faz fsync e so entao ``os.replace``.
Um snapshot pela metade e pior que nenhum snapshot.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from ..domain.accounts import Account, AccountStore
from ..domain.operations import OperationResult


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
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = SnapshotMeta(
        last_included_idx=store.last_applied_idx,
        last_included_epoch=last_included_epoch,
        total_cents=store.total_cents(),
    )
    payload = {
        "meta": {
            "last_included_idx": meta.last_included_idx,
            "last_included_epoch": meta.last_included_epoch,
            "total_cents": meta.total_cents,
        },
        "accounts": {a.id: a.balance_cents for a in store.accounts.values()},
        # A tabela de deduplicacao faz parte do estado: sem ela, uma retentativa
        # apos reinicio reaplicaria uma operacao ja aplicada.
        "applied": {
            op_id: {"applied_idx": r.applied_idx, "balances": r.balances}
            for op_id, r in store.applied.items()
        },
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return meta


def load(path: Path) -> tuple[AccountStore, SnapshotMeta] | None:
    """Carrega o snapshot, ou ``None`` se nao existe.

    Deve conferir ``total_cents`` contra a soma reconstruida e recusar um arquivo
    corrompido, em vez de subir com um estado errado.
    """
    path = Path(path)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        raw_meta = payload["meta"]
        meta = SnapshotMeta(
            last_included_idx=int(raw_meta["last_included_idx"]),
            last_included_epoch=int(raw_meta["last_included_epoch"]),
            total_cents=int(raw_meta["total_cents"]),
        )
        store = AccountStore(
            accounts={
                aid: Account(aid, int(balance))
                for aid, balance in payload["accounts"].items()
            },
            applied={
                op_id: OperationResult(
                    op_id=op_id,
                    applied_idx=int(r["applied_idx"]),
                    balances={k: int(v) for k, v in (r.get("balances") or {}).items()},
                )
                for op_id, r in (payload.get("applied") or {}).items()
            },
            last_applied_idx=meta.last_included_idx,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"snapshot corrompido: {path}") from exc

    if store.total_cents() != meta.total_cents:
        raise ValueError(
            f"snapshot inconsistente: soma {store.total_cents()} != cabecalho {meta.total_cents}"
        )
    return store, meta
