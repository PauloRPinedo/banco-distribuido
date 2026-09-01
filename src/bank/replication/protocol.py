"""Mensagens trocadas entre os servidores.

Sao apenas dois RPCs, ambos POST JSON em ``/internal/*``:

- ``AppendEntries``: o primario envia entradas as replicas. Com ``entries``
  vazio, e o heartbeat -- o mesmo RPC serve para replicar e para provar que o
  primario esta vivo, o que evita dois caminhos de codigo divergirem.
- ``RequestVote``: um candidato pede votos para se promover.

Toda mensagem carrega ``epoch``. Um receptor com epoch maior sempre rejeita, e
quem tem epoch menor sempre se rebaixa a replica: e o mecanismo de fencing que
impede um primario antigo, que so estava lento, de confirmar escritas depois de
o cluster ter seguido em frente (split-brain).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..domain.operations import LogEntry


@dataclass
class AppendEntries:
    """Replicacao e heartbeat, do primario para uma replica."""

    epoch: int
    leader_id: str
    prev_idx: int
    """Indice da entrada imediatamente anterior a ``entries[0]``."""

    prev_epoch: int
    """Epoch daquela entrada. Junto com ``prev_idx``, e a checagem de log matching:
    se a replica nao tiver exatamente essa entrada, o log dela divergiu."""

    entries: list[LogEntry] = field(default_factory=list)
    """Vazio em heartbeat."""

    leader_commit: int = 0
    """Ate onde o primario ja confirmou; a replica pode aplicar ate aqui."""

    def to_json(self) -> dict[str, Any]:
        return {
            "epoch": self.epoch,
            "leader_id": self.leader_id,
            "prev_idx": self.prev_idx,
            "prev_epoch": self.prev_epoch,
            "entries": [e.to_json() for e in self.entries],
            "leader_commit": self.leader_commit,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "AppendEntries":
        return cls(
            epoch=int(data["epoch"]),
            leader_id=str(data["leader_id"]),
            prev_idx=int(data["prev_idx"]),
            prev_epoch=int(data["prev_epoch"]),
            entries=[LogEntry.from_json(e) for e in (data.get("entries") or [])],
            leader_commit=int(data.get("leader_commit", 0)),
        )


@dataclass
class AppendAck:
    """Resposta a ``AppendEntries``."""

    epoch: int
    """Epoch do respondente. Se for maior que o do primario, ele se rebaixa."""

    success: bool
    match_idx: int
    """Se ``success``, o maior indice que a replica tem igual ao do primario.
    Se nao, uma dica de ate onde o primario deve retroceder para reenviar."""

    node_id: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "epoch": self.epoch,
            "success": self.success,
            "match_idx": self.match_idx,
            "node_id": self.node_id,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "AppendAck":
        return cls(
            epoch=int(data["epoch"]),
            success=bool(data["success"]),
            match_idx=int(data["match_idx"]),
            node_id=str(data.get("node_id", "")),
        )


@dataclass
class RequestVote:
    """Pedido de voto de um candidato."""

    epoch: int
    candidate_id: str
    last_idx: int
    last_epoch: int
    """O log do candidato. O eleitor so vota se este log estiver **pelo menos tao
    atualizado** quanto o seu: e essa restricao que garante que nenhuma operacao
    ja confirmada seja perdida."""

    def to_json(self) -> dict[str, Any]:
        return {
            "epoch": self.epoch,
            "candidate_id": self.candidate_id,
            "last_idx": self.last_idx,
            "last_epoch": self.last_epoch,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "RequestVote":
        return cls(
            epoch=int(data["epoch"]),
            candidate_id=str(data["candidate_id"]),
            last_idx=int(data["last_idx"]),
            last_epoch=int(data["last_epoch"]),
        )


@dataclass
class VoteReply:
    """Resposta ao pedido de voto."""

    epoch: int
    granted: bool
    voter_id: str = ""
    reason: str = ""
    """Motivo da recusa (``stale_epoch``, ``already_voted``, ``log_behind``), so
    para o log estruturado e para depurar os testes de failover."""

    def to_json(self) -> dict[str, Any]:
        return {
            "epoch": self.epoch,
            "granted": self.granted,
            "voter_id": self.voter_id,
            "reason": self.reason,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "VoteReply":
        return cls(
            epoch=int(data["epoch"]),
            granted=bool(data["granted"]),
            voter_id=str(data.get("voter_id", "")),
            reason=str(data.get("reason", "")),
        )
