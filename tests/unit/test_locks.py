"""Locks por conta (RF-08)."""

from __future__ import annotations

import threading
import time

import pytest

from bank.concurrency.locks import AccountLockManager


def test_contas_diferentes_nao_se_bloqueiam():
    """Se bloqueassem, o throughput cairia ao de um lock global (RNF-04)."""
    manager = AccountLockManager()

    def segura(nome):
        with manager.acquire([nome]):
            time.sleep(0.2)

    threads = [threading.Thread(target=segura, args=(f"c{i}",)) for i in range(4)]
    inicio = time.monotonic()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert time.monotonic() - inicio < 0.5, "contas diferentes foram serializadas"


def test_mesma_conta_serializa():
    manager = AccountLockManager()
    ordem = []

    def trabalha(marca):
        with manager.acquire(["alice"]):
            ordem.append(("entrou", marca))
            time.sleep(0.05)
            ordem.append(("saiu", marca))

    threads = [threading.Thread(target=trabalha, args=(i,)) for i in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    # Nunca dois "entrou" seguidos: a secao critica nao se sobrepoe.
    marcas = [evento for evento, _ in ordem]
    assert all(marcas[i] != marcas[i + 1] for i in range(len(marcas) - 1))


def test_transferencias_cruzadas_nao_travam():
    """A->B e B->A ao mesmo tempo: a ordem crescente de id impede o deadlock."""
    manager = AccountLockManager()
    erros = []

    def cruza(x, y):
        for _ in range(200):
            try:
                with manager.acquire([x, y]):
                    pass
            except Exception as exc:  # noqa: BLE001
                erros.append(exc)

    a = threading.Thread(target=cruza, args=("alice", "bob"))
    b = threading.Thread(target=cruza, args=("bob", "alice"))
    a.start()
    b.start()
    a.join(timeout=15)
    b.join(timeout=15)
    assert not a.is_alive() and not b.is_alive(), "DEADLOCK entre transferencias cruzadas"
    assert not erros


def test_timeout_solta_os_locks_ja_tomados():
    manager = AccountLockManager()
    with manager.acquire(["z"]):
        with pytest.raises(TimeoutError):
            with manager.acquire(["z"], timeout_s=0.1):
                pass
    # Depois do timeout e da saida, a conta tem de estar livre de novo.
    with manager.acquire(["z"], timeout_s=0.1):
        pass
    assert manager.held_count() == 0


def test_duplicatas_nao_travam_duas_vezes():
    manager = AccountLockManager()
    with manager.acquire(["a", "a", "a"]):
        pass
