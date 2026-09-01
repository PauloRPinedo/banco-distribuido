"""Operacoes concorrentes sobre as mesmas contas (RF-07, RF-08, historia 7)."""

from __future__ import annotations

import threading

import httpx


def test_saques_concorrentes_nao_estouram_o_saldo(banco, live_cluster):
    """N clientes sacando ao mesmo tempo de uma conta que so cobre alguns saques:
    o total sacado nao pode passar do saldo inicial, e o saldo final nao pode ser
    negativo."""
    banco.create_account("cofre", 1000)

    confirmados = []
    trava = threading.Lock()

    def saca() -> None:
        cliente = type(banco)(live_cluster.urls, timeout_s=5.0, max_retries=5)
        try:
            for _ in range(5):
                try:
                    cliente.withdraw("cofre", 100)
                    with trava:
                        confirmados.append(100)
                except Exception:  # noqa: BLE001 - saldo insuficiente e o esperado
                    pass
        finally:
            cliente.close()

    threads = [threading.Thread(target=saca) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    total_sacado = sum(confirmados)
    assert total_sacado <= 1000, f"sacou {total_sacado} de uma conta com 1000"
    assert banco.get_balance("cofre")["balance_cents"] == 1000 - total_sacado
    assert banco.get_balance("cofre")["balance_cents"] >= 0


def test_transferencias_cruzadas_concorrentes_preservam_o_total(banco, live_cluster):
    """alice->bob e bob->alice ao mesmo tempo: o par de locks e tomado em ordem
    crescente, entao nao ha deadlock, e o total nao pode mudar."""
    banco.create_account("alice", 50000)
    banco.create_account("bob", 50000)
    total = 100000

    def carga(origem: str, destino: str) -> None:
        cliente = type(banco)(live_cluster.urls, timeout_s=5.0, max_retries=5)
        try:
            for _ in range(20):
                try:
                    cliente.transfer(origem, destino, 100)
                except Exception:  # noqa: BLE001
                    pass
        finally:
            cliente.close()

    a = threading.Thread(target=carga, args=("alice", "bob"))
    b = threading.Thread(target=carga, args=("bob", "alice"))
    a.start()
    b.start()
    a.join(timeout=90)
    b.join(timeout=90)
    assert not a.is_alive() and not b.is_alive(), "DEADLOCK em transferencias cruzadas"

    assert set(live_cluster.esperar_convergencia().values()) == {total}


def test_leitura_ve_estado_consistente(banco, live_cluster):
    """RF-07: uma leitura nunca enxerga uma transferencia pela metade.

    Le a auditoria enquanto transferencias correm; a soma tem de ser sempre a
    mesma. Sem o lock de estado nas leituras, uma consulta feita entre o debito
    e o credito veria dinheiro sumido.
    """
    banco.create_account("alice", 30000)
    banco.create_account("bob", 30000)
    total = 60000
    primario = live_cluster.esperar_primario()

    parar = threading.Event()
    lidos: set[int] = set()

    def le() -> None:
        with httpx.Client(timeout=5.0) as cliente:
            while not parar.is_set():
                try:
                    lidos.add(cliente.get(f"{primario.url}/audit").json()["total_cents"])
                except (httpx.HTTPError, ValueError, KeyError):
                    pass

    leitor = threading.Thread(target=le)
    leitor.start()
    try:
        for _ in range(30):
            try:
                banco.transfer("alice", "bob", 137)
            except Exception:  # noqa: BLE001
                pass
    finally:
        parar.set()
        leitor.join(timeout=15)

    assert lidos, "o leitor nao conseguiu ler nada"
    assert lidos == {total}, f"uma leitura viu uma transferencia pela metade: {lidos}"
