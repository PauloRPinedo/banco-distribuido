"""Locks por conta (RF-08).

Um lock global serializaria o banco inteiro e inviabilizaria RNF-04. Locks por
conta deixam operacoes sobre contas diferentes correrem em paralelo, e so
serializam quem realmente disputa a mesma conta.

Com locks por conta surge o risco de deadlock: uma transferencia A->B e outra
B->A tomando os locks em ordens opostas travariam para sempre. A solucao aqui e
ordem total -- os locks sao **sempre** adquiridos em ordem crescente de id de
conta, o que torna o deadlock impossivel por construcao (ver
``Operation.touched_accounts``, que ja devolve a tupla ordenada).
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Iterator, Sequence


class AccountLockManager:
    """Fabrica de locks por conta, criados sob demanda."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}
        self._held = 0

    def _lock_for(self, account_id: str) -> threading.Lock:
        # Caminho quente sem mutex: ler um dict e atomico sob o GIL, e o lock de
        # uma conta ja vista e o caso comum. O mutex global so entra na primeira
        # vez que a conta aparece -- com 32 threads, toma-lo a cada operacao era
        # contencao pura, sem proteger nada.
        lock = self._locks.get(account_id)
        if lock is not None:
            return lock
        with self._guard:
            return self._locks.setdefault(account_id, threading.Lock())

    @contextmanager
    def acquire(self, account_ids: Sequence[str], timeout_s: float = 5.0) -> Iterator[None]:
        """Toma os locks das contas em ordem crescente e os solta ao sair.

        Deve ordenar e remover duplicatas antes de travar. Se o timeout estourar,
        solta o que ja pegou e levanta ``TimeoutError`` -- prender locks em uma
        falha parcial travaria as contas para todos os outros clientes.
        """
        ordered = sorted(set(account_ids))
        taken: list[threading.Lock] = []
        deadline = time.monotonic() + timeout_s
        try:
            for account_id in ordered:
                lock = self._lock_for(account_id)
                remaining = max(deadline - time.monotonic(), 0.0)
                if not lock.acquire(timeout=remaining):
                    raise TimeoutError(f"timeout ao travar a conta {account_id}")
                taken.append(lock)
            # Contador so para /admin/metrics: += sob o GIL e suficiente aqui e
            # nao justifica um mutex no caminho de toda escrita.
            self._held += len(taken)
            yield
        finally:
            if taken:
                self._held -= len(taken)
            # Soltar na ordem inversa da aquisicao.
            for lock in reversed(taken):
                lock.release()

    def held_count(self) -> int:
        """Quantidade de locks tomados no momento, exposta em ``/admin/metrics``.

        Aproximado de proposito: e uma metrica, nao uma decisao de corretude.
        """
        return self._held
