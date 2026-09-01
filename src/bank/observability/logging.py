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

from pathlib import Path
from typing import Any


class StructuredLogger:
    """Escritor de log JSONL, seguro entre threads."""

    def __init__(self, node_id: str, path: Path, also_stderr: bool = True) -> None:
        raise NotImplementedError

    def bind(self, **fields: Any) -> None:
        """Fixa campos incluidos em todos os eventos seguintes (``role``, ``epoch``)."""
        raise NotImplementedError

    def event(self, name: str, **fields: Any) -> None:
        """Registra um evento. Nomes usados pelos testes de integracao:

        ``op_received``, ``op_validated``, ``entry_appended``, ``replicate_sent``,
        ``ack_received``, ``commit``, ``op_applied``, ``op_rejected``,
        ``heartbeat_missed``, ``election_started``, ``vote_granted``,
        ``vote_denied``, ``became_primary``, ``stepped_down``, ``log_truncated``,
        ``snapshot_saved``, ``recovered``, ``fault_injected``.
        """
        raise NotImplementedError
