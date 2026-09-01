"""Comandos, entradas de log e resultados.

Uma **operacao** e o comando logico pedido pelo cliente. Ela vira exatamente
**uma** entrada no log replicado: e dai que sai a atomicidade da transferencia
(RF-05) sem protocolo de duas fases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .money import Cents


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
        raise NotImplementedError

    def validate(self) -> None:
        """Valida a forma do comando, sem olhar o estado das contas.

        Raises:
            InvalidAmount, SameAccountTransfer: conforme o defeito encontrado.
        """
        raise NotImplementedError


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
    ts: float
    """Timestamp de criacao no primario, apenas informativo (extrato e logs)."""

    def to_json(self) -> dict[str, Any]:
        """Serializa para a linha do WAL e para o corpo de AppendEntries."""
        raise NotImplementedError

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "LogEntry":
        """Desserializa uma linha do WAL. Deve rejeitar entradas malformadas."""
        raise NotImplementedError


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
