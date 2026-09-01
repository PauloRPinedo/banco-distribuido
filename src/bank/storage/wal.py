"""Write-ahead log: um arquivo JSONL append-only por servidor.

Cada linha e uma ``LogEntry`` serializada, em ordem de ``idx``. O WAL e ao mesmo
tempo (a) o mecanismo de durabilidade local e (b) a unidade de replicacao: mandar
dados para uma replica e mandar um trecho deste arquivo.

Modos de fsync (``fsync_mode`` na configuracao):

- ``always``: fsync a cada append. Maxima durabilidade, menor throughput.
- ``batch``:  group commit -- appends concorrentes compartilham um unico fsync
              dentro de uma janela de ``group_commit_window_ms``. E o padrao e o
              que viabiliza RNF-04 (500 TPS).
- ``off``:    sem fsync. **Somente para benchmark**; perde dados em queda de maquina.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from ..domain.operations import LogEntry


class WriteAheadLog:
    """Log append-only duravel.

    Todos os metodos sao seguros para chamada concorrente por multiplas threads.
    """

    def __init__(self, path: Path, fsync_mode: str = "batch", group_commit_window_ms: int = 5) -> None:
        raise NotImplementedError

    # -- escrita ------------------------------------------------------------

    def append(self, entry: LogEntry) -> None:
        """Grava uma entrada e so retorna quando ela esta **duravel**.

        Em modo ``batch``, bloqueia ate o fsync do grupo. Deve recusar uma entrada
        cujo ``idx`` nao seja ``last_idx + 1``.
        """
        raise NotImplementedError

    def truncate_from(self, idx: int) -> None:
        """Remove as entradas com indice >= ``idx``, inclusive, e faz fsync.

        Usado quando o log matching detecta que esta replica tem entradas
        divergentes, **nao confirmadas**, de um primario antigo. Nunca e chamado
        para um ``idx`` menor ou igual ao ``commit_index``: apagar algo confirmado
        seria perder dinheiro.
        """
        raise NotImplementedError

    # -- leitura ------------------------------------------------------------

    def read_from(self, idx: int, limit: int | None = None) -> list[LogEntry]:
        """Entradas a partir de ``idx`` (inclusive), para alimentar AppendEntries."""
        raise NotImplementedError

    def iter_all(self) -> Iterator[LogEntry]:
        """Percorre o log inteiro, para o replay de recuperacao."""
        raise NotImplementedError

    def entry_at(self, idx: int) -> LogEntry | None:
        """Entrada em ``idx``, ou ``None``. Usado na checagem de ``prev_idx``."""
        raise NotImplementedError

    @property
    def last_idx(self) -> int:
        """Indice da ultima entrada gravada; 0 se o log esta vazio."""
        raise NotImplementedError

    @property
    def last_epoch(self) -> int:
        """Epoch da ultima entrada; 0 se vazio. Usado na restricao de voto."""
        raise NotImplementedError

    def close(self) -> None:
        """Faz flush do grupo pendente e fecha o arquivo."""
        raise NotImplementedError
