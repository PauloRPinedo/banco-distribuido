"""Erros de dominio e de cluster.

Cada erro carrega um ``code`` estavel, usado como corpo JSON da API e nos logs
estruturados, para que o CLI e os testes possam reagir sem depender de mensagens.
"""

from __future__ import annotations


class BankError(Exception):
    """Base de todos os erros do sistema."""

    code: str = "bank_error"
    http_status: int = 400


class UnknownAccount(BankError):
    """Conta inexistente."""

    code = "unknown_account"
    http_status = 404


class AccountAlreadyExists(BankError):
    """Tentativa de criar uma conta com id ja usado."""

    code = "account_already_exists"
    http_status = 409


class InsufficientFunds(BankError):
    """Operacao deixaria o saldo negativo (RF-06)."""

    code = "insufficient_funds"
    http_status = 422


class InvalidAmount(BankError):
    """Quantia nao positiva, nao inteira ou acima do teto."""

    code = "invalid_amount"
    http_status = 422


class SameAccountTransfer(BankError):
    """Transferencia com origem igual ao destino."""

    code = "same_account_transfer"
    http_status = 422


class NotPrimary(BankError):
    """Escrita recebida por uma replica.

    A resposta inclui ``primary_hint`` para que o CLI siga direto ao primario
    atual em vez de percorrer a lista inteira (RF-11, historia de usuario 8).
    """

    code = "not_primary"
    http_status = 409

    def __init__(self, primary_hint: str | None = None) -> None:
        super().__init__("este no nao e o primario")
        self.primary_hint = primary_hint


class NoQuorum(BankError):
    """O primario nao conseguiu ACK da maioria dentro do timeout.

    A operacao **nao** foi confirmada ao cliente; ela pode ou nao estar no log.
    O cliente deve repetir com o mesmo ``op_id`` (RF-13).
    """

    code = "no_quorum"
    http_status = 503


class ReadOnlyMode(BankError):
    """Menos da maioria dos nos esta viva: leituras seguem, escritas param.

    E o modo degradado que preserva a invariante de dinheiro quando 2 de 3 nos
    caem (ver "Desvios da proposta" em docs/arquitetura.md).
    """

    code = "read_only"
    http_status = 503
