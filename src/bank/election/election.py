"""Eleicao de primario por maioria (RF-09).

Uma replica que fica sem noticias do primario incrementa o epoch, vota em si e
pede votos. Vira primario com a maioria dos votos -- 2 de 3, ou 2 de 2 num
cluster de dois.

O eleitor so concede o voto se **todas** as condicoes valerem:

1. ``epoch`` do candidato >= o seu (se for maior, ele adota o epoch antes de decidir);
2. ainda nao votou neste epoch (ou ja votou neste mesmo candidato);
3. o log do candidato esta **pelo menos tao atualizado** quanto o seu, comparando
   primeiro ``last_epoch`` e, em empate, ``last_idx``.

A condicao 3 e o que garante a corretude do failover: como toda operacao
confirmada esta no log da maioria, e todo vencedor precisa da maioria, o novo
primario tem obrigatoriamente todas as operacoes confirmadas. Nenhuma some.

Ao vencer, o novo primario envia um heartbeat imediato (para calar candidatos
concorrentes) e grava um NOOP no seu epoch antes de aceitar escritas.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from ..replication.protocol import RequestVote, VoteReply
from .protocol_types import ElectionOutcome  # noqa: F401  (reexport para os testes)
from .node_state import NodeState


class ElectionManager:
    """Conduz a candidatura e responde a pedidos de voto."""

    def __init__(
        self,
        node_state: NodeState,
        log: "object",
        peers: "object",
        peer_ids: list[str],
        on_promoted: Callable[[], None],
        vote_timeout_s: float = 0.4,
        logger: "object | None" = None,
    ) -> None:
        self.node_state = node_state
        self.log = log
        self.peers = peers
        self.peer_ids = list(peer_ids)
        self.on_promoted = on_promoted
        self.vote_timeout_s = vote_timeout_s
        self.logger = logger
        self.quorum = (len(peer_ids) + 1) // 2 + 1

    def _log_event(self, name: str, **fields) -> None:
        if self.logger is not None:
            self.logger.event(name, **fields)

    def start_election(self) -> ElectionOutcome:
        """Concorre a primario no proximo epoch.

        Pede votos em paralelo e decide assim que a maioria responde. Se durante a
        apuracao chegar um epoch maior, desiste e se rebaixa.
        """
        epoch = self.node_state.start_candidacy()
        message = RequestVote(
            epoch=epoch,
            candidate_id=self.node_state.node_id,
            last_idx=self.log.last_idx,
            last_epoch=self.log.last_epoch,
        )
        self._log_event(
            "election_started",
            epoch=epoch,
            last_idx=message.last_idx,
            last_epoch=message.last_epoch,
        )

        granted = 1  # o proprio voto
        if self.peer_ids:
            with ThreadPoolExecutor(max_workers=len(self.peer_ids)) as pool:
                futures = {
                    pool.submit(self.peers.request_vote, node_id, message, self.vote_timeout_s): node_id
                    for node_id in self.peer_ids
                }
                for future in futures:
                    reply = future.result()
                    if reply is None:
                        continue
                    if reply.epoch > self.node_state.epoch:
                        self.node_state.step_down(reply.epoch)
                        self._log_event("stepped_down", epoch=reply.epoch, reason="vote_reply")
                        return ElectionOutcome.STEPPED_DOWN
                    if reply.granted:
                        granted += 1

        # Alguem pode ter virado primario enquanto apuravamos.
        if self.node_state.epoch != epoch or self.node_state.role.value != "candidate":
            self._log_event("stepped_down", epoch=epoch, reason="epoch_changed")
            return ElectionOutcome.STEPPED_DOWN

        if granted >= self.quorum:
            self.node_state.become_primary()
            self._log_event("became_primary", epoch=epoch, votes=granted, needed=self.quorum)
            self.on_promoted()
            return ElectionOutcome.WON

        self.node_state.step_down()
        self._log_event("election_lost", epoch=epoch, votes=granted, needed=self.quorum)
        return ElectionOutcome.LOST

    def handle_request_vote(self, message: RequestVote) -> VoteReply:
        """Decide um pedido de voto conforme as tres condicoes do cabecalho.

        Persiste o voto **antes** de responder.
        """
        node_id = self.node_state.node_id

        if message.epoch < self.node_state.epoch:
            return VoteReply(self.node_state.epoch, False, node_id, "stale_epoch")

        # Condicao 3: o log do candidato tem de estar pelo menos tao atualizado.
        # Sem ela, um no atrasado poderia virar primario e apagar operacoes
        # ja confirmadas -- ou seja, perder dinheiro.
        my_last_epoch = self.log.last_epoch
        my_last_idx = self.log.last_idx
        up_to_date = message.last_epoch > my_last_epoch or (
            message.last_epoch == my_last_epoch and message.last_idx >= my_last_idx
        )
        if not up_to_date:
            # Adota o epoch maior mesmo recusando o voto: o cluster seguiu adiante.
            self.node_state.observe_epoch(message.epoch)
            self._log_event(
                "vote_denied",
                epoch=message.epoch,
                candidate=message.candidate_id,
                reason="log_behind",
            )
            return VoteReply(self.node_state.epoch, False, node_id, "log_behind")

        if self.node_state.grant_vote(message.epoch, message.candidate_id):
            self._log_event("vote_granted", epoch=message.epoch, candidate=message.candidate_id)
            return VoteReply(self.node_state.epoch, True, node_id, "")

        self._log_event(
            "vote_denied", epoch=message.epoch, candidate=message.candidate_id, reason="already_voted"
        )
        return VoteReply(self.node_state.epoch, False, node_id, "already_voted")
