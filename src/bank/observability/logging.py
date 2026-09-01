"""Log estruturado, uma linha JSON por evento (RNF-07).

Formato fixo para que os testes possam correlacionar o que aconteceu nos tres
servidores em uma unica linha do tempo:

``{"ts": ..., "node_id": "A", "role": "primary", "epoch": 7, "event": "commit",
   "op_id": "...", "idx": 42, ...}``

``node_id``, ``role`` e ``epoch`` aparecem em **todo** evento: sem eles, um log
de failover e ilegivel. Grava em ``data_dir/<node_id>/server.log`` e, opcional,
no stderr.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from typing import Any


class StructuredLogger:
    """Escritor de log JSONL, seguro entre threads."""

    def __init__(self, node_id: str, path: Path, also_stderr: bool = True) -> None:
        self.node_id = node_id
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.also_stderr = also_stderr
        self._lock = threading.Lock()
        self._bound: dict[str, Any] = {}
        self._handle = open(self.path, "a", encoding="utf-8")

    def bind(self, **fields: Any) -> None:
        """Fixa campos incluidos em todos os eventos seguintes (``role``, ``epoch``)."""
        with self._lock:
            self._bound.update(fields)

    def event(self, name: str, **fields: Any) -> None:
        """Registra um evento. Nomes usados pelos testes de integracao:

        ``op_received``, ``op_validated``, ``entry_appended``, ``replicate_sent``,
        ``ack_received``, ``commit``, ``op_applied``, ``op_rejected``,
        ``heartbeat_missed``, ``election_started``, ``vote_granted``,
        ``vote_denied``, ``became_primary``, ``stepped_down``, ``log_truncated``,
        ``snapshot_saved``, ``recovered``, ``fault_injected``.
        """
        record = {"ts": round(time.time(), 6), "node_id": self.node_id}
        with self._lock:
            record.update(self._bound)
            record["event"] = name
            record.update({k.rstrip("_"): v for k, v in fields.items()})
            line = json.dumps(record, separators=(",", ":"), default=str)
            try:
                self._handle.write(line + "\n")
                self._handle.flush()
            except ValueError:
                return  # arquivo ja fechado no encerramento
            if self.also_stderr:
                print(line, file=sys.stderr, flush=True)

    def close(self) -> None:
        with self._lock:
            if not self._handle.closed:
                self._handle.close()
