"""Caminho feliz ponta a ponta, com o cluster no ar (RF-01..RF-05, RF-14)."""

from __future__ import annotations

import uuid

import httpx
import pytest


def test_criar_consultar_depositar_sacar(banco):
    banco.create_account("alice", 10000)
    assert banco.get_balance("alice")["balance_cents"] == 10000
    banco.deposit("alice", 2500)
    assert banco.get_balance("alice")["balance_cents"] == 12500
    banco.withdraw("alice", 500)
    assert banco.get_balance("alice")["balance_cents"] == 12000


def test_transferencia_entre_contas(banco):
    banco.create_account("alice", 10000)
    banco.create_account("bob", 0)
    resultado = banco.transfer("alice", "bob", 2500)
    assert resultado["balances"] == {"alice": 7500, "bob": 2500}


def test_saldo_negativo_e_rejeitado(banco):
    """RF-06: a rejeicao nao pode mover nem um centavo."""
    from banco_cli import BankError

    banco.create_account("alice", 100)
    banco.create_account("bob", 0)
    with pytest.raises(BankError, match="saldo insuficiente"):
        banco.transfer("alice", "bob", 999999)
    assert banco.get_balance("alice")["balance_cents"] == 100
    assert banco.get_balance("bob")["balance_cents"] == 0


def test_extrato_lista_as_operacoes_da_conta(banco):
    banco.create_account("alice", 10000)
    banco.create_account("bob", 0)
    banco.transfer("alice", "bob", 100)
    banco.deposit("alice", 50)
    extrato = banco.statement("alice")
    tipos = [e["type"] for e in extrato["entries"]]
    assert "transfer" in tipos and "deposit" in tipos
    assert all("noop" != t for t in tipos), "o NOOP interno nao pertence ao extrato do cliente"


def test_auditoria_bate_nos_tres_nos(banco, live_cluster):
    """Com o mesmo applied_idx, o total tem de ser identico em A, B e C.
    Divergencia aqui e bug de replicacao, e nao de arredondamento: o dinheiro
    e inteiro."""
    banco.create_account("alice", 10000)
    banco.create_account("bob", 5000)
    for _ in range(10):
        banco.transfer("alice", "bob", 123)

    totais = live_cluster.esperar_convergencia()
    assert len(totais) == 3
    assert set(totais.values()) == {15000}, totais


def test_replica_recusa_escrita_e_indica_o_primario(live_cluster):
    primario = live_cluster.esperar_primario()
    replicas = [n for n in live_cluster.vivos() if n.id != primario.id]
    replica = replicas[0]

    resposta = httpx.post(
        f"{replica.url}/transfers",
        json={"op_id": str(uuid.uuid4()), "from_account": "a", "to_account": "b", "amount_cents": 1},
        timeout=5.0,
    )
    assert resposta.status_code == 409
    corpo = resposta.json()
    assert corpo["error"] == "not_primary"
    assert corpo["primary_hint"] == primario.url, "a dica tem de apontar ao primario real"


def test_leitura_em_replica_exige_stale_explicito(banco, live_cluster):
    banco.create_account("alice", 700)
    live_cluster.esperar_convergencia()
    primario = live_cluster.esperar_primario()
    replica = [n for n in live_cluster.vivos() if n.id != primario.id][0]

    assert httpx.get(f"{replica.url}/accounts/alice", timeout=5.0).status_code == 409
    resposta = httpx.get(f"{replica.url}/accounts/alice", params={"stale": True}, timeout=5.0)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["balance_cents"] == 700 and corpo["stale"] is True
