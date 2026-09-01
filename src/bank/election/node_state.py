"""Papel e epoch do no -- o pouco de estado que **precisa** sobreviver a um crash.

``epoch`` e ``voted_for`` sao gravados em disco com fsync **antes** de serem
usados em qualquer mensagem. Se um no votasse, caisse e esquecesse o voto, ele
poderia votar de novo no mesmo epoch e eleger dois primarios simultaneos.
"""

from __future__ import annotations

import json
import os
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
        self._path = Path(state_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._role = NodeRole.REPLICA
        self._epoch = 0
        self._voted_for: str | None = None
        self._leader_id: str | None = None
        self._load()

    # -- persistencia -------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._epoch = int(data.get("epoch", 0))
            self._voted_for = data.get("voted_for")
        except (json.JSONDecodeError, ValueError, TypeError):
            # Estado ilegivel: comecar do epoch 0 e seguro, porque qualquer
            # mensagem de um par com epoch maior sera adotada de imediato.
            self._epoch = 0
            self._voted_for = None

    def _persist(self) -> None:
        """Grava epoch e voto de forma atomica e duravel.

        Chamado **antes** de responder qualquer mensagem que dependa deles.
        """
        temporary = self._path.with_suffix(".tmp")
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump({"epoch": self._epoch, "voted_for": self._voted_for}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self._path)

    # -- leitura ------------------------------------------------------------

    @property
    def role(self) -> NodeRole:
        with self.lock:
            return self._role

    @property
    def epoch(self) -> int:
        with self.lock:
            return self._epoch

    @property
    def voted_for(self) -> str | None:
        with self.lock:
            return self._voted_for

    @property
    def leader_id(self) -> str | None:
        """Ultimo primario conhecido, usado no ``primary_hint`` devolvido ao CLI."""
        with self.lock:
            return self._leader_id

    def is_primary(self) -> bool:
        with self.lock:
            return self._role is NodeRole.PRIMARY

    # -- transicoes ---------------------------------------------------------

    def observe_epoch(self, epoch: int, leader_id: str | None = None) -> bool:
        """Reage a um epoch visto em uma mensagem recebida.

        Se ``epoch`` for maior que o atual, adota-o, limpa o voto, vira replica e
        persiste antes de retornar.

        Returns:
            ``True`` se houve rebaixamento (este no era primario ou candidato).
        """
        with self.lock:
            demoted = False
            if epoch > self._epoch:
                self._epoch = epoch
                self._voted_for = None
                demoted = self._role is not NodeRole.REPLICA
                self._role = NodeRole.REPLICA
                self._persist()
            if leader_id is not None and epoch >= self._epoch:
                self._leader_id = leader_id
                if self._role is NodeRole.CANDIDATE:
                    # Ja existe primario neste epoch: desistir da candidatura.
                    self._role = NodeRole.REPLICA
                    demoted = True
            return demoted

    def start_candidacy(self) -> int:
        """Incrementa o epoch, vota em si mesmo, persiste e vira CANDIDATE.

        Returns:
            O novo epoch.
        """
        with self.lock:
            self._epoch += 1
            self._voted_for = self.node_id
            self._role = NodeRole.CANDIDATE
            self._leader_id = None
            self._persist()
            return self._epoch

    def grant_vote(self, epoch: int, candidate_id: str) -> bool:
        """Concede o voto se ainda nao votou neste epoch. Persiste antes de responder."""
        with self.lock:
            if epoch < self._epoch:
                return False
            if epoch > self._epoch:
                self._epoch = epoch
                self._voted_for = None
                self._role = NodeRole.REPLICA
            if self._voted_for is not None and self._voted_for != candidate_id:
                return False
            self._voted_for = candidate_id
            self._persist()
            return True

    def become_primary(self) -> None:
        """Assume o papel de primario no epoch corrente."""
        with self.lock:
            self._role = NodeRole.PRIMARY
            self._leader_id = self.node_id

    def step_down(self, epoch: int | None = None) -> None:
        """Rebaixa a replica, opcionalmente adotando um epoch maior."""
        with self.lock:
            if epoch is not None and epoch > self._epoch:
                self._epoch = epoch
                self._voted_for = None
                self._persist()
            self._role = NodeRole.REPLICA

    def snapshot(self) -> dict:
        """Estado resumido para ``/admin/status`` e para o log estruturado."""
        with self.lock:
            return {
                "node_id": self.node_id,
                "role": self._role.value,
                "epoch": self._epoch,
                "voted_for": self._voted_for,
                "leader_id": self._leader_id,
            }
