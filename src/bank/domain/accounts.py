"""Maquina de estados deterministica das contas.

Este modulo e o coracao da corretude: e a **unica** parte que muda saldos.
E puro e deterministico -- nao faz I/O, nao conhece rede nem disco. Aplicar a
mesma sequencia de entradas de log em qualquer no produz exatamente o mesmo
estado, que e o que permite replicar por log e recuperar por replay.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .money import Cents
from .operations import LogEntry, Operation, OperationResult


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
        raise NotImplementedError

    def total_cents(self) -> Cents:
        """Soma de todos os saldos -- a invariante do sistema (RF-14, RNF-01).

        Usada pela auditoria e comparada entre os nos nos testes: se dois nos
        com o mesmo ``last_applied_idx`` divergirem aqui, ha um bug de replicacao.
        """
        raise NotImplementedError

    def statement(self, account_id: str, limit: int = 50) -> list[LogEntry]:
        """Extrato: entradas confirmadas que tocaram a conta, mais recentes primeiro."""
        raise NotImplementedError

    # -- validacao e aplicacao ---------------------------------------------

    def check(self, operation: Operation) -> None:
        """Verifica se a operacao pode ser aplicada ao estado atual.

        Chamada pelo primario **antes** de gravar no log, com os locks das contas
        ja tomados, para nao replicar uma operacao que sera rejeitada.

        Raises:
            UnknownAccount, AccountAlreadyExists, InsufficientFunds: conforme o caso.
        """
        raise NotImplementedError

    def apply(self, entry: LogEntry) -> OperationResult:
        """Aplica uma entrada **ja confirmada** ao estado.

        Deve ser idempotente por ``op_id`` e recusar entradas fora de ordem
        (``entry.idx != last_applied_idx + 1``), porque aplicar salteado
        corromperia o estado silenciosamente.

        A transferencia debita e credita aqui dentro, em uma unica chamada: e
        assim que RF-05 (atomicidade) e satisfeito sem 2PC.
        """
        raise NotImplementedError
