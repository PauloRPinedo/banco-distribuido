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

import json
import os
import threading
from pathlib import Path
from typing import Iterator

from ..domain.operations import LogEntry


class WriteAheadLog:
    """Log append-only duravel.

    Todos os metodos sao seguros para chamada concorrente por multiplas threads.
    """

    def __init__(
        self, path: Path, fsync_mode: str = "batch", group_commit_window_ms: int = 5
    ) -> None:
        if fsync_mode not in ("always", "batch", "off"):
            raise ValueError(f"fsync_mode invalido: {fsync_mode}")
        self.path = Path(path)
        self.fsync_mode = fsync_mode
        self.window_s = group_commit_window_ms / 1000.0

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        # Indice em memoria do arquivo inteiro: com o volume deste projeto cabe
        # folgado e evita reler o disco a cada checagem de log matching.
        self._entries: list[LogEntry] = self._read_file()
        self._file = open(self.path, "a", encoding="utf-8")
        self._synced_upto = len(self._entries)
        self._sync_generation = 0
        self._sync_cond = threading.Condition(self._lock)
        self._syncing = False

    # -- leitura do arquivo -------------------------------------------------

    def _read_file(self) -> list[LogEntry]:
        """Le o arquivo inteiro, descartando uma linha final truncada.

        Uma queda no meio de um append deixa meia linha; ela nao pode virar uma
        entrada valida nem impedir o servidor de subir.
        """
        if not self.path.exists():
            return []
        entries: list[LogEntry] = []
        with open(self.path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
        for position, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(LogEntry.from_json(json.loads(line)))
            except (json.JSONDecodeError, ValueError):
                # So a ultima linha pode estar truncada; corrupcao no meio e um
                # defeito real e nao deve ser silenciada.
                if position == len(lines) - 1:
                    break
                raise ValueError(f"WAL corrompido em {self.path}, linha {position + 1}")
        return entries

    # -- escrita ------------------------------------------------------------

    def append(self, entry: LogEntry) -> None:
        """Grava uma entrada e so retorna quando ela esta **duravel**.

        Em modo ``batch``, bloqueia ate o fsync do grupo. Deve recusar uma entrada
        cujo ``idx`` nao seja ``last_idx + 1``.
        """
        self.append_many([entry])

    def append_many(self, entries: list[LogEntry]) -> None:
        """Grava varias entradas contiguas e espera a durabilidade."""
        target = self.append_buffered(entries)
        self.wait_durable(target)

    def append_buffered(self, entries: list[LogEntry]) -> int:
        """Escreve as entradas no arquivo **sem** esperar o fsync.

        Devolve o indice ate onde e preciso sincronizar. Separar as duas metades
        e o que permite ao primario soltar o lock de ordenacao antes de bloquear
        no disco: assim N escritas concorrentes compartilham um unico fsync, em
        vez de enfileirar N fsyncs (a diferenca entre ~130 e ~1000 TPS aqui).

        Quem chama **tem** de chamar ``wait_durable`` antes de confirmar
        qualquer coisa ao cliente ou a um par.
        """
        if not entries:
            return self._synced_upto
        with self._lock:
            expected = len(self._entries) + 1
            for entry in entries:
                if entry.idx != expected:
                    raise ValueError(f"idx nao contiguo: {entry.idx}, esperado {expected}")
                expected += 1
            for entry in entries:
                self._file.write(json.dumps(entry.to_json(), separators=(",", ":")) + "\n")
                self._entries.append(entry)
            self._file.flush()
            return len(self._entries)

    def wait_durable(self, target: int) -> None:
        """Bloqueia ate as entradas ate ``target`` estarem em disco."""
        self._durable(target)

    def _durable(self, target: int) -> None:
        """Garante que as entradas ate ``target`` estao em disco.

        Em modo ``batch``, quem chega enquanto um fsync corre espera por ele em
        vez de disparar outro: e isso que faz varias escritas concorrentes
        dividirem o custo de uma unica sincronizacao.
        """
        if self.fsync_mode == "off":
            return
        with self._sync_cond:
            while self._synced_upto < target:
                if self._syncing:
                    self._sync_cond.wait(timeout=1.0)
                    continue
                self._syncing = True
                pending = len(self._entries)
                try:
                    if self.fsync_mode == "batch" and self.window_s > 0:
                        # Janela curta para que appends que chegam agora entrem
                        # no mesmo fsync.
                        self._sync_cond.wait(timeout=self.window_s)
                        pending = len(self._entries)
                    self._file.flush()
                    os.fsync(self._file.fileno())
                    self._synced_upto = max(self._synced_upto, pending)
                finally:
                    self._syncing = False
                    self._sync_cond.notify_all()

    def truncate_from(self, idx: int) -> None:
        """Remove as entradas com indice >= ``idx``, inclusive, e faz fsync.

        Usado quando o log matching detecta que esta replica tem entradas
        divergentes, **nao confirmadas**, de um primario antigo. Nunca e chamado
        para um ``idx`` menor ou igual ao ``commit_index``: apagar algo confirmado
        seria perder dinheiro.
        """
        with self._lock:
            if idx < 1:
                raise ValueError("truncate_from exige idx >= 1")
            if idx > len(self._entries):
                return
            kept = self._entries[: idx - 1]
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            with open(temporary, "w", encoding="utf-8") as handle:
                for entry in kept:
                    handle.write(json.dumps(entry.to_json(), separators=(",", ":")) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._file.close()
            os.replace(temporary, self.path)
            self._file = open(self.path, "a", encoding="utf-8")
            self._entries = kept
            self._synced_upto = len(kept)

    # -- leitura ------------------------------------------------------------

    def read_from(self, idx: int, limit: int | None = None) -> list[LogEntry]:
        """Entradas a partir de ``idx`` (inclusive), para alimentar AppendEntries."""
        with self._lock:
            start = max(idx, 1) - 1
            chunk = self._entries[start:]
            return chunk[:limit] if limit is not None else list(chunk)

    def iter_all(self) -> Iterator[LogEntry]:
        """Percorre o log inteiro, para o replay de recuperacao."""
        with self._lock:
            return iter(list(self._entries))

    def entry_at(self, idx: int) -> LogEntry | None:
        """Entrada em ``idx``, ou ``None``. Usado na checagem de ``prev_idx``."""
        with self._lock:
            if 1 <= idx <= len(self._entries):
                return self._entries[idx - 1]
            return None

    @property
    def last_idx(self) -> int:
        """Indice da ultima entrada gravada; 0 se o log esta vazio."""
        with self._lock:
            return len(self._entries)

    @property
    def last_epoch(self) -> int:
        """Epoch da ultima entrada; 0 se vazio. Usado na restricao de voto."""
        with self._lock:
            return self._entries[-1].epoch if self._entries else 0

    def close(self) -> None:
        """Faz flush do grupo pendente e fecha o arquivo."""
        with self._lock:
            if not self._file.closed:
                self._file.flush()
                if self.fsync_mode != "off":
                    os.fsync(self._file.fileno())
                self._file.close()
