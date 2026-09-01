"""Estado do log replicado, visto por um no.

Junta o WAL duravel com o que so existe em memoria: ate onde esta confirmado e o
quanto cada replica ja acompanhou.
"""

from __future__ import annotations

import threading

from ..domain.operations import LogEntry, Operation
from ..storage.wal import WriteAheadLog


class ReplicatedLog:
    """O log deste no, com os indices de acompanhamento dos pares."""

    def __init__(self, wal: WriteAheadLog, node_ids: list[str], self_id: str) -> None:
        self.wal = wal
        self.self_id = self_id
        self.node_ids = list(node_ids)
        self._lock = threading.RLock()
        self._commit_index = 0
        # Quanto cada replica confirmou ter gravado, e de onde mandar em seguida.
        self.match_idx: dict[str, int] = {n: 0 for n in node_ids if n != self_id}
        self.next_idx: dict[str, int] = {n: wal.last_idx + 1 for n in node_ids if n != self_id}

    # -- indices ------------------------------------------------------------

    @property
    def last_idx(self) -> int:
        """Ultima entrada gravada localmente (confirmada ou nao)."""
        return self.wal.last_idx

    @property
    def last_epoch(self) -> int:
        """Epoch da ultima entrada gravada."""
        return self.wal.last_epoch

    @property
    def commit_index(self) -> int:
        """Ate onde se sabe que a maioria gravou. Tudo ate aqui e irrevogavel."""
        with self._lock:
            return self._commit_index

    def reset_tracking(self) -> None:
        """Reinicia os indices dos pares. Chamado ao assumir como primario:
        o novo lider nao sabe o que cada replica tem, entao parte do proprio fim
        do log e retrocede conforme os ACKs negativos."""
        with self._lock:
            for node_id in self.match_idx:
                self.match_idx[node_id] = 0
                self.next_idx[node_id] = self.wal.last_idx + 1

    # -- lado do primario ---------------------------------------------------

    def append_local(self, operation: Operation, epoch: int) -> LogEntry:
        """Cria a proxima entrada e a grava de forma duravel no WAL."""
        entry = self.append_local_buffered(operation, epoch)
        self.wal.wait_durable(entry.idx)
        return entry

    def append_local_buffered(self, operation: Operation, epoch: int) -> LogEntry:
        """Atribui o proximo ``idx`` e escreve, **sem** esperar o fsync.

        Quem chama tem de esperar ``wait_durable`` antes de replicar ou
        confirmar. Ver ``storage.wal.append_buffered`` para o porque.
        """
        with self._lock:
            entry = LogEntry(idx=self.wal.last_idx + 1, epoch=epoch, operation=operation)
            self.wal.append_buffered([entry])
        return entry

    def wait_durable(self, idx: int) -> None:
        """Espera o fsync alcancar ``idx``."""
        self.wal.wait_durable(idx)

    def record_match(self, node_id: str, match_idx: int) -> None:
        """Registra ate onde uma replica confirmou ter gravado."""
        with self._lock:
            if node_id in self.match_idx:
                self.match_idx[node_id] = max(self.match_idx[node_id], match_idx)
                self.next_idx[node_id] = self.match_idx[node_id] + 1

    def advance_commit(self, current_epoch: int) -> int:
        """Recalcula o ``commit_index`` a partir dos ``match_idx`` da maioria.

        Regra critica herdada do Raft: so se confirma diretamente uma entrada do
        **epoch corrente**. Uma entrada de epoch anterior replicada na maioria
        ainda nao pode ser confirmada por contagem; ela e confirmada por arraste
        quando uma entrada do epoch atual (na pratica, o no-op da promocao)
        alcanca a maioria. Ignorar isso permite reverter uma operacao ja
        confirmada -- ou seja, perder dinheiro.

        Returns:
            O novo ``commit_index``.
        """
        with self._lock:
            quorum = len(self.node_ids) // 2 + 1
            for candidate in range(self.wal.last_idx, self._commit_index, -1):
                entry = self.wal.entry_at(candidate)
                if entry is None or entry.epoch != current_epoch:
                    # Entradas de epochs anteriores nao contam por si; serao
                    # confirmadas por arraste junto com uma do epoch atual.
                    continue
                replicas = sum(1 for m in self.match_idx.values() if m >= candidate)
                if replicas + 1 >= quorum:  # +1 = o proprio primario
                    self._commit_index = candidate
                    break
            return self._commit_index

    def next_batch_for(
        self, node_id: str, max_entries: int = 64
    ) -> tuple[int, int, list[LogEntry]]:
        """Monta ``(prev_idx, prev_epoch, entries)`` para o proximo AppendEntries."""
        with self._lock:
            next_index = max(self.next_idx.get(node_id, 1), 1)
            prev_idx = next_index - 1
            previous = self.wal.entry_at(prev_idx) if prev_idx > 0 else None
            prev_epoch = previous.epoch if previous else 0
            entries = self.wal.read_from(next_index, limit=max_entries)
            return prev_idx, prev_epoch, entries

    def back_off(self, node_id: str, hint_idx: int) -> None:
        """Retrocede o ponto de envio a uma replica que rejeitou por divergencia."""
        with self._lock:
            if node_id not in self.next_idx:
                return
            # A dica da replica acelera a convergencia; sem ela seria de 1 em 1.
            candidate = min(self.next_idx[node_id] - 1, hint_idx + 1)
            self.next_idx[node_id] = max(1, candidate)

    # -- lado da replica ----------------------------------------------------

    def matches(self, prev_idx: int, prev_epoch: int) -> bool:
        """Checagem de log matching contra a entrada local em ``prev_idx``."""
        if prev_idx == 0:
            return True
        entry = self.wal.entry_at(prev_idx)
        return entry is not None and entry.epoch == prev_epoch

    def append_from_leader(self, prev_idx: int, entries: list[LogEntry]) -> int:
        """Grava entradas vindas do primario, truncando o que divergir.

        So trunca em conflito real (mesmo ``idx``, ``epoch`` diferente) e nunca
        abaixo do ``commit_index``.

        Returns:
            O novo ``match_idx`` desta replica.
        """
        with self._lock:
            if not entries:
                return prev_idx

            to_write: list[LogEntry] = []
            for entry in entries:
                existing = self.wal.entry_at(entry.idx)
                if existing is None:
                    to_write.append(entry)
                elif existing.epoch != entry.epoch:
                    if entry.idx <= self._commit_index:
                        raise ValueError(
                            f"conflito em idx={entry.idx}, ja confirmado ate {self._commit_index}"
                        )
                    self.wal.truncate_from(entry.idx)
                    to_write.append(entry)
                # existing com mesmo epoch: ja temos essa entrada, nada a fazer.

            if to_write:
                # Reenvios podem trazer entradas que ja temos; so grava a cauda nova.
                start = self.wal.last_idx + 1
                self.wal.append_many([e for e in to_write if e.idx >= start])
            return entries[-1].idx

    def set_commit(self, leader_commit: int) -> int:
        """Avanca o commit local ate ``min(leader_commit, last_idx)``."""
        with self._lock:
            self._commit_index = max(self._commit_index, min(leader_commit, self.wal.last_idx))
            return self._commit_index

    def force_commit(self, idx: int) -> int:
        """Fixa o commit local (usado na recuperacao). Nunca retrocede."""
        with self._lock:
            self._commit_index = max(self._commit_index, min(idx, self.wal.last_idx))
            return self._commit_index
