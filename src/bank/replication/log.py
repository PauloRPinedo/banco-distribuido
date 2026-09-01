"""Estado do log replicado, visto por um no.

Junta o WAL duravel com o que so existe em memoria: ate onde esta confirmado e o
quanto cada replica ja acompanhou.
"""

from __future__ import annotations

from ..domain.operations import LogEntry, Operation
from ..storage.wal import WriteAheadLog


class ReplicatedLog:
    """O log deste no, com os indices de acompanhamento dos pares."""

    def __init__(self, wal: WriteAheadLog, node_ids: list[str], self_id: str) -> None:
        raise NotImplementedError

    # -- indices ------------------------------------------------------------

    @property
    def last_idx(self) -> int:
        """Ultima entrada gravada localmente (confirmada ou nao)."""
        raise NotImplementedError

    @property
    def last_epoch(self) -> int:
        """Epoch da ultima entrada gravada."""
        raise NotImplementedError

    @property
    def commit_index(self) -> int:
        """Ate onde se sabe que a maioria gravou. Tudo ate aqui e irrevogavel."""
        raise NotImplementedError

    # -- lado do primario ---------------------------------------------------

    def append_local(self, operation: Operation, epoch: int) -> LogEntry:
        """Cria a proxima entrada e a grava de forma duravel no WAL."""
        raise NotImplementedError

    def record_match(self, node_id: str, match_idx: int) -> None:
        """Registra ate onde uma replica confirmou ter gravado."""
        raise NotImplementedError

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
        raise NotImplementedError

    def next_batch_for(self, node_id: str, max_entries: int = 64) -> tuple[int, int, list[LogEntry]]:
        """Monta ``(prev_idx, prev_epoch, entries)`` para o proximo AppendEntries."""
        raise NotImplementedError

    def back_off(self, node_id: str, hint_idx: int) -> None:
        """Retrocede o ponto de envio a uma replica que rejeitou por divergencia."""
        raise NotImplementedError

    # -- lado da replica ----------------------------------------------------

    def matches(self, prev_idx: int, prev_epoch: int) -> bool:
        """Checagem de log matching contra a entrada local em ``prev_idx``."""
        raise NotImplementedError

    def append_from_leader(self, prev_idx: int, entries: list[LogEntry]) -> int:
        """Grava entradas vindas do primario, truncando o que divergir.

        So trunca em conflito real (mesmo ``idx``, ``epoch`` diferente) e nunca
        abaixo do ``commit_index``.

        Returns:
            O novo ``match_idx`` desta replica.
        """
        raise NotImplementedError

    def set_commit(self, leader_commit: int) -> int:
        """Avanca o commit local ate ``min(leader_commit, last_idx)``."""
        raise NotImplementedError
