"""Comandos, entradas de log e resultados.

Uma **operacao** e o comando logico pedido pelo cliente. Ela vira exatamente
**uma** entrada no log replicado: e dai que sai a atomicidade da transferencia
(RF-05) sem protocolo de duas fases.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .errors import InvalidAmount, SameAccountTransfer
from .money import Cents, validate_amount


class OpType(str, Enum):
    """Tipos de entrada aceitos pela maquina de estados."""

    CREATE_ACCOUNT = "create_account"
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    TRANSFER = "transfer"
    NOOP = "noop"
    """Entrada vazia gravada por um primario recem-eleito no seu proprio epoch.

    Necessaria para que ele possa confirmar com seguranca entradas herdadas de
    epochs anteriores (ver docs/arquitetura.md, secao Eleicao).
    """


@dataclass(frozen=True)
class Operation:
    """Comando logico enviado pelo cliente.

    Attributes:
        op_id: UUID gerado **pelo cliente** e reutilizado em cada retentativa.
            E a chave de idempotencia que torna seguro repetir uma transferencia
            quando o primario cai no meio (RF-13, historia de usuario 4).
        type: tipo da operacao.
        account_id: conta alvo em deposito, saque e criacao.
        from_account / to_account: pontas de uma transferencia.
        amount_cents: quantia em centavos, sempre positiva.
    """

    op_id: str
    type: OpType
    account_id: str | None = None
    from_account: str | None = None
    to_account: str | None = None
    amount_cents: Cents = 0

    def touched_accounts(self) -> tuple[str, ...]:
        """Contas afetadas, **ordenadas**.

        A ordem e o que garante que dois primarios de transferencias cruzadas
        (A->B e B->A) peguem os locks na mesma sequencia e nao deem deadlock
        (ver concurrency/locks.py).
        """
        if self.type is OpType.TRANSFER:
            names = {self.from_account, self.to_account}
        elif self.type is OpType.NOOP:
            names = set()
        else:
            names = {self.account_id}
        return tuple(sorted(n for n in names if n))

    def validate(self) -> None:
        """Valida a forma do comando, sem olhar o estado das contas.

        Raises:
            InvalidAmount, SameAccountTransfer: conforme o defeito encontrado.
        """
        if self.type is OpType.NOOP:
            return

        if self.type is OpType.TRANSFER:
            if not self.from_account or not self.to_account:
                raise InvalidAmount("transferencia exige conta de origem e de destino")
            if self.from_account == self.to_account:
                raise SameAccountTransfer("origem e destino sao a mesma conta")
        elif not self.account_id:
            raise InvalidAmount(f"operacao {self.type.value} exige uma conta")

        # Criar conta com saldo inicial zero e legitimo; as demais exigem quantia > 0.
        if self.type is OpType.CREATE_ACCOUNT:
            if self.amount_cents < 0:
                raise InvalidAmount("saldo inicial nao pode ser negativo")
        else:
            validate_amount(self.amount_cents)

    def to_payload(self) -> dict[str, Any]:
        """Campos especificos do tipo, para o corpo da entrada de log."""
        if self.type is OpType.TRANSFER:
            return {
                "from_account": self.from_account,
                "to_account": self.to_account,
                "amount_cents": self.amount_cents,
            }
        if self.type is OpType.NOOP:
            return {}
        return {"account_id": self.account_id, "amount_cents": self.amount_cents}

    @classmethod
    def from_payload(cls, op_id: str, type_: str, payload: dict[str, Any]) -> "Operation":
        """Reconstroi a operacao a partir de uma entrada de log."""
        return cls(
            op_id=op_id,
            type=OpType(type_),
            account_id=payload.get("account_id"),
            from_account=payload.get("from_account"),
            to_account=payload.get("to_account"),
            amount_cents=int(payload.get("amount_cents", 0)),
        )


@dataclass(frozen=True)
class LogEntry:
    """Entrada do log replicado, unidade de replicacao e de durabilidade.

    Serializada como uma linha JSON no WAL:
    ``{"idx": 42, "epoch": 7, "op_id": "...", "type": "transfer", "payload": {...}, "ts": ...}``
    """

    idx: int
    """Indice global, 1-based e contiguo. ``idx == 0`` e a entrada sentinela vazia."""

    epoch: int
    """Epoch (mandato) do primario que criou a entrada. Usado no log matching."""

    operation: Operation
    ts: float = field(default_factory=time.time)
    """Timestamp de criacao no primario, apenas informativo (extrato e logs)."""

    def to_json(self) -> dict[str, Any]:
        """Serializa para a linha do WAL e para o corpo de AppendEntries."""
        return {
            "idx": self.idx,
            "epoch": self.epoch,
            "op_id": self.operation.op_id,
            "type": self.operation.type.value,
            "payload": self.operation.to_payload(),
            "ts": self.ts,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "LogEntry":
        """Desserializa uma linha do WAL. Deve rejeitar entradas malformadas."""
        try:
            return cls(
                idx=int(data["idx"]),
                epoch=int(data["epoch"]),
                operation=Operation.from_payload(
                    str(data["op_id"]), str(data["type"]), dict(data.get("payload") or {})
                ),
                ts=float(data.get("ts", 0.0)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"entrada de log malformada: {data!r}") from exc


@dataclass
class OperationResult:
    """Resultado aplicado de uma operacao, devolvido ao cliente e memorizado.

    Fica guardado na tabela de deduplicacao por ``op_id`` para que uma
    retentativa devolva o mesmo resultado em vez de aplicar duas vezes.
    """

    op_id: str
    applied_idx: int
    balances: dict[str, Cents] = field(default_factory=dict)
    """Saldos finais das contas tocadas, para o cliente conferir sem nova leitura."""
