"""Maquina de estados das contas: invariantes de dinheiro (RNF-01, RF-06, RF-08)."""

from __future__ import annotations

import random

import pytest

from bank.domain.accounts import AccountStore
from bank.domain.errors import InsufficientFunds, UnknownAccount
from bank.domain.operations import LogEntry, Operation, OperationResult, OpType


def make_store(**saldos: int) -> AccountStore:
    """Store com as contas pedidas ja criadas, aplicando entradas de verdade."""
    store = AccountStore()
    for i, (nome, saldo) in enumerate(saldos.items(), start=1):
        store.apply(
            LogEntry(i, 1, Operation(f"c{i}", OpType.CREATE_ACCOUNT, account_id=nome, amount_cents=saldo))
        )
    return store


def apply_next(store: AccountStore, operation: Operation, epoch: int = 1) -> OperationResult:
    return store.apply(LogEntry(store.last_applied_idx + 1, epoch, operation))


class TestSaldoNuncaNegativo:
    """RF-06: nenhuma operacao pode deixar um saldo negativo."""

    def test_saque_acima_do_saldo_e_rejeitado(self):
        store = make_store(alice=1000)
        with pytest.raises(InsufficientFunds):
            store.check(Operation("s1", OpType.WITHDRAW, account_id="alice", amount_cents=1001))
        assert store.get_balance("alice") == 1000

    def test_transferencia_acima_do_saldo_nao_move_nada(self):
        """Nem debita a origem nem credita o destino -- rejeicao e tudo ou nada."""
        store = make_store(alice=1000, bob=500)
        operacao = Operation(
            "t1", OpType.TRANSFER, from_account="alice", to_account="bob", amount_cents=5000
        )
        with pytest.raises(InsufficientFunds):
            store.check(operacao)
        assert (store.get_balance("alice"), store.get_balance("bob")) == (1000, 500)
        # Mesmo se a entrada chegasse ao log por um bug, apply tambem recusa.
        with pytest.raises(InsufficientFunds):
            apply_next(store, operacao)

    def test_conta_inexistente_e_recusada(self):
        store = make_store(alice=100)
        with pytest.raises(UnknownAccount):
            store.check(Operation("d", OpType.DEPOSIT, account_id="ninguem", amount_cents=1))


class TestInvarianteDaSoma:
    """RNF-01: a soma de todos os saldos nunca muda com transferencias."""

    def test_transferencia_preserva_o_total(self):
        store = make_store(alice=10000, bob=0)
        total = store.total_cents()
        apply_next(
            store,
            Operation("t", OpType.TRANSFER, from_account="alice", to_account="bob", amount_cents=2500),
        )
        assert store.total_cents() == total
        assert (store.get_balance("alice"), store.get_balance("bob")) == (7500, 2500)

    def test_sequencia_aleatoria_preserva_o_total(self):
        """Milhares de operacoes sorteadas com semente fixa; o total tem de bater."""
        rng = random.Random(42)  # semente fixa: mesma execucao, mesmo resultado (RNF-06)
        nomes = [f"c{i}" for i in range(10)]
        store = make_store(**{nome: 100_000 for nome in nomes})
        total = store.total_cents()

        for n in range(3000):
            origem, destino = rng.sample(nomes, 2)
            operacao = Operation(
                f"op{n}",
                OpType.TRANSFER,
                from_account=origem,
                to_account=destino,
                amount_cents=rng.randint(1, 5000),
            )
            try:
                store.check(operacao)
            except InsufficientFunds:
                continue
            apply_next(store, operacao)

        assert store.total_cents() == total, "uma transferencia criou ou destruiu dinheiro"
        assert all(c.balance_cents >= 0 for c in store.accounts.values())

    def test_deposito_e_saque_mudam_o_total_na_medida_exata(self):
        store = make_store(alice=1000)
        apply_next(store, Operation("d", OpType.DEPOSIT, account_id="alice", amount_cents=250))
        assert store.total_cents() == 1250
        apply_next(store, Operation("s", OpType.WITHDRAW, account_id="alice", amount_cents=50))
        assert store.total_cents() == 1200


class TestAplicacaoDeEntradas:
    def test_reaplicar_o_mesmo_op_id_nao_move_dinheiro_duas_vezes(self):
        """Idempotencia: e o que torna seguro o cliente repetir apos um failover."""
        store = make_store(alice=10000, bob=0)
        operacao = Operation(
            "mesmo-id", OpType.TRANSFER, from_account="alice", to_account="bob", amount_cents=3000
        )
        primeiro = apply_next(store, operacao)
        for _ in range(4):
            repetido = apply_next(store, operacao)
            assert repetido == primeiro
        assert (store.get_balance("alice"), store.get_balance("bob")) == (7000, 3000)
        assert store.total_cents() == 10000

    def test_entrada_fora_de_ordem_e_recusada(self):
        """Aplicar salteado corromperia o estado em silencio."""
        store = make_store(alice=100)
        with pytest.raises(ValueError, match="fora de ordem"):
            store.apply(LogEntry(99, 1, Operation("x", OpType.DEPOSIT, account_id="alice", amount_cents=1)))

    def test_noop_avanca_o_indice_sem_mexer_em_saldos(self):
        store = make_store(alice=100)
        total = store.total_cents()
        idx = store.last_applied_idx
        apply_next(store, Operation("n", OpType.NOOP))
        assert store.last_applied_idx == idx + 1 and store.total_cents() == total

    def test_extrato_lista_apenas_as_entradas_da_conta(self):
        store = make_store(alice=1000, bob=1000, carol=1000)
        apply_next(
            store,
            Operation("t1", OpType.TRANSFER, from_account="alice", to_account="bob", amount_cents=10),
        )
        apply_next(store, Operation("d1", OpType.DEPOSIT, account_id="carol", amount_cents=10))
        contas_no_extrato = [e.operation.touched_accounts() for e in store.statement("alice")]
        assert all("alice" in c for c in contas_no_extrato)
        assert len(store.statement("carol")) == 2  # criacao + deposito
