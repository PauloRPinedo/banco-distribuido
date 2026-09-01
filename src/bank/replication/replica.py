"""Lado da replica: recebe AppendEntries, valida, grava e aplica.

Ordem das checagens (nao pode ser trocada):

1. ``epoch < meu_epoch``  -> rejeita e devolve o proprio epoch. E o fencing: um
   primario antigo que voltou a si descobre assim que perdeu o mandato.
2. ``epoch > meu_epoch``  -> adota o epoch novo e se rebaixa a replica.
3. Reinicia o temporizador de eleicao (a mensagem prova que ha um primario vivo).
4. Log matching em ``prev_idx``/``prev_epoch``: se nao bate, rejeita com uma dica
   de retrocesso.
5. Grava as entradas de forma duravel, truncando divergencias nao confirmadas.
6. Aplica ao estado ate ``leader_commit``.
7. Responde ACK com o ``match_idx``.

O ACK so sai depois do fsync do passo 5. Confirmar antes de estar duravel
quebraria RNF-02 exatamente no caso que o projeto se propoe a testar.
"""

from __future__ import annotations

import threading

from ..domain.accounts import AccountStore
from .log import ReplicatedLog
from .protocol import AppendAck, AppendEntries


class ReplicaApplier:
    """Trata AppendEntries e heartbeats recebidos."""

    def __init__(
        self,
        node_state: "object",
        log: ReplicatedLog,
        store: AccountStore,
        election_timer: "object | None" = None,
        logger: "object | None" = None,
        store_lock: threading.RLock | None = None,
    ) -> None:
        self.node_state = node_state
        self.log = log
        self.store = store
        self.election_timer = election_timer
        self.logger = logger
        # Serializa a gravacao e a aplicacao. E o **mesmo** lock usado pelo
        # PrimaryReplicator e pelas leituras: um no troca de papel sem parar, e
        # dois locks distintos deixariam uma janela de corrida na transicao.
        self._lock = store_lock if store_lock is not None else threading.RLock()

    def _log_event(self, name: str, **fields) -> None:
        if self.logger is not None:
            self.logger.event(name, **fields)

    def handle_append_entries(self, message: AppendEntries) -> AppendAck:
        """Executa a sequencia descrita no cabecalho do modulo."""
        node_id = self.node_state.node_id

        # 1. Fencing: mensagem de um primario que ja perdeu o mandato.
        if message.epoch < self.node_state.epoch:
            self._log_event(
                "append_rejected",
                reason="stale_epoch",
                from_=message.leader_id,
                epoch=message.epoch,
            )
            return AppendAck(self.node_state.epoch, False, self.log.last_idx, node_id)

        # 2. Epoch novo (ou igual): reconhecer este lider.
        self.node_state.observe_epoch(message.epoch, leader_id=message.leader_id)

        # 3. Ha um primario vivo: nao iniciar eleicao.
        if self.election_timer is not None:
            self.election_timer.reset()

        with self._lock:
            # 4. Log matching.
            if not self.log.matches(message.prev_idx, message.prev_epoch):
                # A dica acelera o retrocesso do primario.
                hint = min(message.prev_idx - 1, self.log.last_idx)
                self._log_event(
                    "append_rejected",
                    reason="log_mismatch",
                    prev_idx=message.prev_idx,
                    my_last_idx=self.log.last_idx,
                )
                return AppendAck(self.node_state.epoch, False, max(hint, 0), node_id)

            # 5. Gravar de forma duravel (o WAL faz fsync antes de retornar).
            try:
                match_idx = self.log.append_from_leader(message.prev_idx, message.entries)
            except ValueError as exc:
                # Conflito com algo ja confirmado: nao truncar, recusar.
                self._log_event("append_rejected", reason="conflict_committed", error=str(exc))
                return AppendAck(self.node_state.epoch, False, self.log.commit_index, node_id)

            # 6. Aplicar ate onde o primario confirmou.
            self.log.set_commit(message.leader_commit)
            self.apply_committed()

        # 7. ACK, ja duravel.
        return AppendAck(self.node_state.epoch, True, match_idx, node_id)

    def apply_committed(self) -> int:
        """Aplica ao ``AccountStore`` tudo que ja esta confirmado e ainda nao aplicado.

        Returns:
            O novo ``last_applied_idx``.
        """
        with self._lock:
            while self.store.last_applied_idx < self.log.commit_index:
                entry = self.log.wal.entry_at(self.store.last_applied_idx + 1)
                if entry is None:
                    break
                self.store.apply(entry)
            return self.store.last_applied_idx
