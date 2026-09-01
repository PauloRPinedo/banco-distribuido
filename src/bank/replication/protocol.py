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
        raise NotImplementedError

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "AppendEntries":
        raise NotImplementedError


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
        raise NotImplementedError

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "AppendAck":
        raise NotImplementedError


@dataclass
class RequestVote:
    """Pedido de voto de um candidato."""

    epoch: int
    candidate_id: str
    last_idx: int
    last_epoch: int
    """O log do candidato. O eleitor so vota se este log estiver **pelo menos tao
    atualizado** quanto o seu: e essa restricao que garante que nenhuma operacao
    ja confirmada seja perdida na troca de primario."""

    def to_json(self) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "RequestVote":
        raise NotImplementedError


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
        raise NotImplementedError

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "VoteReply":
        raise NotImplementedError
