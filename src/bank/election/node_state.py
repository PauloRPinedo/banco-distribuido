"""Papel e epoch do no -- o pouco de estado que **precisa** sobreviver a um crash.

``epoch`` e ``voted_for`` sao gravados em disco com fsync **antes** de serem
usados em qualquer mensagem. Se um no votasse, caisse e esquecesse o voto, ele
poderia votar de novo no mesmo epoch e eleger dois primarios simultaneos.
"""

from __future__ import annotations

import threading
from enum import Enum
from pathlib import Path


class NodeRole(str, Enum):
    """Papel atual do no."""

    REPLICA = "replica"
    CANDIDATE = "candidate"
    PRIMARY = "primary"


class NodeState:
    """Papel, epoch e voto, com persistencia e acesso seguro entre threads."""

    def __init__(self, node_id: str, state_path: Path) -> None:
        self.node_id = node_id
        self.lock = threading.RLock()
        raise NotImplementedError

    # -- leitura ------------------------------------------------------------

    @property
    def role(self) -> NodeRole:
        raise NotImplementedError

    @property
    def epoch(self) -> int:
        raise NotImplementedError

    @property
    def leader_id(self) -> str | None:
        """Ultimo primario conhecido, usado no ``primary_hint`` devolvido ao CLI."""
        raise NotImplementedError

    # -- transicoes ---------------------------------------------------------

    def observe_epoch(self, epoch: int, leader_id: str | None = None) -> bool:
        """Reage a um epoch visto em uma mensagem recebida.

        Se ``epoch`` for maior que o atual, adota-o, limpa o voto, vira replica e
        persiste antes de retornar.

        Returns:
            ``True`` se houve rebaixamento (este no era primario ou candidato).
        """
        raise NotImplementedError

    def start_candidacy(self) -> int:
        """Incrementa o epoch, vota em si mesmo, persiste e vira CANDIDATE.

        Returns:
            O novo epoch.
        """
        raise NotImplementedError

    def grant_vote(self, epoch: int, candidate_id: str) -> bool:
        """Concede o voto se ainda nao votou neste epoch. Persiste antes de responder."""
        raise NotImplementedError

    def become_primary(self) -> None:
        """Assume o papel de primario no epoch corrente."""
        raise NotImplementedError

    def step_down(self, epoch: int | None = None) -> None:
        """Rebaixa a replica, opcionalmente adotando um epoch maior."""
        raise NotImplementedError

    def snapshot(self) -> dict:
        """Estado resumido para ``/admin/status`` e para o log estruturado."""
        raise NotImplementedError
