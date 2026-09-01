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
from contextlib import contextmanager
from typing import Iterator, Sequence


class AccountLockManager:
    """Fabrica de locks por conta, criados sob demanda."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    @contextmanager
    def acquire(self, account_ids: Sequence[str], timeout_s: float = 5.0) -> Iterator[None]:
        """Toma os locks das contas em ordem crescente e os solta ao sair.

        Deve ordenar e remover duplicatas antes de travar. Se o timeout estourar,
        solta o que ja pegou e levanta ``TimeoutError`` -- prender locks em uma
        falha parcial travaria as contas para todos os outros clientes.
        """
        raise NotImplementedError

    def held_count(self) -> int:
        """Quantidade de locks tomados no momento, exposta em ``/admin/metrics``."""
        raise NotImplementedError
