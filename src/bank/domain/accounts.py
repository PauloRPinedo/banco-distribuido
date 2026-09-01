"""Maquina de estados deterministica das contas.

Este modulo e o coracao da corretude: e a **unica** parte que muda saldos.
E puro e deterministico -- nao faz I/O, nao conhece rede nem disco. Aplicar a
mesma sequencia de entradas de log em qualquer no produz exatamente o mesmo
estado, que e o que permite replicar por log e recuperar por replay.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import (
    AccountAlreadyExists,
    InsufficientFunds,
    UnknownAccount,
)
from .money import Cents
from .operations import LogEntry, Operation, OperationResult, OpType


@dataclass
class Account:
    """Uma conta. O saldo nunca pode ficar negativo (RF-06)."""

    id: str
    balance_cents: Cents = 0


@dataclass
class AccountStore:
    """Estado das contas em memoria, mais o extrato e a deduplicacao.

    Attributes:
        accounts: contas por id.
        history: entradas ja aplicadas, na ordem, base do extrato (RF-05).
        applied: ``op_id -> OperationResult`` das operacoes ja aplicadas.
            Garante que reaplicar a mesma entrada (retentativa do cliente ou
            reenvio do primario) nao mova dinheiro duas vezes.
        last_applied_idx: indice da ultima entrada aplicada.
    """

    accounts: dict[str, Account] = field(default_factory=dict)
    history: list[LogEntry] = field(default_factory=list)
    applied: dict[str, OperationResult] = field(default_factory=dict)
    last_applied_idx: int = 0

    # -- consultas (nao alteram estado) ------------------------------------

    def get_balance(self, account_id: str) -> Cents:
        """Saldo atual de uma conta (RF-02).

        Raises:
            UnknownAccount: se a conta nao existe.
        """
        account = self.accounts.get(account_id)
        if account is None:
            raise UnknownAccount(f"conta inexistente: {account_id}")
        return account.balance_cents

    def total_cents(self) -> Cents:
        """Soma de todos os saldos -- a invariante do sistema (RF-14, RNF-01).

        Usada pela auditoria e comparada entre os nos nos testes: se dois nos
        com o mesmo ``last_applied_idx`` divergirem aqui, ha um bug de replicacao.
        """
        return sum(a.balance_cents for a in self.accounts.values())

    def statement(self, account_id: str, limit: int = 50) -> list[LogEntry]:
        """Extrato: entradas confirmadas que tocaram a conta, mais recentes primeiro."""
        if account_id not in self.accounts:
            raise UnknownAccount(f"conta inexistente: {account_id}")
        found: list[LogEntry] = []
        for entry in reversed(self.history):
            if account_id in entry.operation.touched_accounts():
                found.append(entry)
                if len(found) >= limit:
                    break
        return found

    # -- validacao e aplicacao ---------------------------------------------

    def check(self, operation: Operation) -> None:
        """Verifica se a operacao pode ser aplicada ao estado atual.

        Chamada pelo primario **antes** de gravar no log, com os locks das contas
        ja tomados, para nao replicar uma operacao que sera rejeitada.

        Raises:
            UnknownAccount, AccountAlreadyExists, InsufficientFunds: conforme o caso.
        """
        operation.validate()

        if operation.type is OpType.NOOP:
            return

        if operation.type is OpType.CREATE_ACCOUNT:
            if operation.account_id in self.accounts:
                raise AccountAlreadyExists(f"conta ja existe: {operation.account_id}")
            return

        for account_id in operation.touched_accounts():
            if account_id not in self.accounts:
                raise UnknownAccount(f"conta inexistente: {account_id}")

        if operation.type is OpType.WITHDRAW:
            if self.accounts[operation.account_id].balance_cents < operation.amount_cents:
                raise InsufficientFunds(f"saldo insuficiente em {operation.account_id}")
        elif operation.type is OpType.TRANSFER:
            if self.accounts[operation.from_account].balance_cents < operation.amount_cents:
                raise InsufficientFunds(f"saldo insuficiente em {operation.from_account}")

    def apply(self, entry: LogEntry) -> OperationResult:
        """Aplica uma entrada **ja confirmada** ao estado.

        Deve ser idempotente por ``op_id`` e recusar entradas fora de ordem
        (``entry.idx != last_applied_idx + 1``), porque aplicar salteado
        corromperia o estado silenciosamente.

        A transferencia debita e credita aqui dentro, em uma unica chamada: e
        assim que RF-05 (atomicidade) e satisfeito sem 2PC.
        """
        if entry.idx != self.last_applied_idx + 1:
            raise ValueError(
                f"entrada fora de ordem: idx={entry.idx}, esperado {self.last_applied_idx + 1}"
            )

        op = entry.operation

        # Idempotencia: a mesma operacao logica so move dinheiro uma vez, mesmo
        # que apareca de novo no log apos uma retentativa do cliente.
        previous = self.applied.get(op.op_id)
        if previous is not None and op.type is not OpType.NOOP:
            self.last_applied_idx = entry.idx
            self.history.append(entry)
            return previous

        if op.type is OpType.NOOP:
            self.last_applied_idx = entry.idx
            self.history.append(entry)
            return OperationResult(op_id=op.op_id, applied_idx=entry.idx)

        if op.type is OpType.CREATE_ACCOUNT:
            self.accounts[op.account_id] = Account(op.account_id, op.amount_cents)
        elif op.type is OpType.DEPOSIT:
            self.accounts[op.account_id].balance_cents += op.amount_cents
        elif op.type is OpType.WITHDRAW:
            account = self.accounts[op.account_id]
            if account.balance_cents < op.amount_cents:
                raise InsufficientFunds(f"saldo insuficiente em {op.account_id}")
            account.balance_cents -= op.amount_cents
        elif op.type is OpType.TRANSFER:
            source = self.accounts[op.from_account]
            target = self.accounts[op.to_account]
            if source.balance_cents < op.amount_cents:
                raise InsufficientFunds(f"saldo insuficiente em {op.from_account}")
            # Debito e credito na mesma chamada: nao existe estado intermediario
            # em que o dinheiro saiu de uma conta e ainda nao entrou na outra.
            source.balance_cents -= op.amount_cents
            target.balance_cents += op.amount_cents
        else:
            raise ValueError(f"tipo de operacao desconhecido: {op.type}")

        result = OperationResult(
            op_id=op.op_id,
            applied_idx=entry.idx,
            balances={a: self.accounts[a].balance_cents for a in op.touched_accounts()},
        )
        self.applied[op.op_id] = result
        self.history.append(entry)
        self.last_applied_idx = entry.idx
        return result
