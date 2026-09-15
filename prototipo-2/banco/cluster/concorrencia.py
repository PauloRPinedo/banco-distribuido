"""Locks por conta, sempre adquiridos por ordem crescente de id.

Um lock global serializaria o banco inteiro. Com um lock por conta,
transferências sobre contas diferentes podem correr em paralelo — o que na
etapa 1 ainda não se nota, porque o lock de estado do nó serializa a aplicação,
mas é a disciplina que a etapa 2 herda.

O risco que locks por conta criam é o deadlock clássico: alice->bob e bob->alice
ao mesmo tempo, cada uma a segurar um lock e à espera do outro. A solução é
**ordem total**: adquirem-se sempre por ordem crescente de id. Como todas as
operações seguem a mesma ordem, o ciclo de espera é impossível.

Quem chama não tem de se lembrar disto: `Operacao.contas_tocadas()` já devolve os
ids ordenados, e `adquirir` volta a ordená-los. A regra está em dois sítios de
propósito, porque esquecê-la produz um deadlock que só aparece sob carga.
"""

import threading
from contextlib import contextmanager
from typing import Iterator, Sequence


class RegistoDeLocks:

    def __init__(self) -> None:
        self._locks: dict[str, threading.Lock] = {}
        self._guarda = threading.Lock()

    @contextmanager
    def adquirir(self, contas: Sequence[str]) -> Iterator[None]:
        ordenadas = sorted(set(contas))
        locks = [self._lock_de(conta) for conta in ordenadas]
        adquiridos: list[threading.Lock] = []
        try:
            for lock in locks:
                lock.acquire()
                adquiridos.append(lock)
            yield
        finally:
            for lock in reversed(adquiridos):
                lock.release()

    def _lock_de(self, conta: str) -> threading.Lock:
        with self._guarda:
            lock = self._locks.get(conta)
            if lock is None:
                lock = threading.Lock()
                self._locks[conta] = lock
            return lock
