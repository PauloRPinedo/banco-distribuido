"""Representacao monetaria do sistema.

Todo valor em dinheiro trafega e e armazenado como um inteiro de **centavos**.
Nunca usar ``float``: a soma de todos os saldos e uma invariante do sistema
(RNF-01) e o arredondamento binario de ponto flutuante a violaria silenciosamente.
"""

from __future__ import annotations

Cents = int
"""Alias semantico: valor monetario em centavos (inteiro, pode ser negativo em deltas)."""

MAX_AMOUNT_CENTS: Cents = 10**15
"""Teto defensivo por operacao, para detectar entradas absurdas antes de replicar."""


def parse_amount(raw: str) -> Cents:
    """Converte uma quantia digitada pelo usuario (ex.: ``"12.34"``) em centavos.

    Aceita ``"12"``, ``"12.3"``, ``"12.34"`` e o separador ``,``. Rejeita valores
    negativos, com mais de duas casas decimais ou acima de ``MAX_AMOUNT_CENTS``.

    Raises:
        ValueError: se a string nao for uma quantia valida.
    """
    raise NotImplementedError


def format_amount(cents: Cents) -> str:
    """Formata centavos para exibicao no CLI (ex.: ``1234`` -> ``"12.34"``)."""
    raise NotImplementedError


def validate_amount(cents: Cents) -> None:
    """Valida uma quantia recebida pela API.

    Raises:
        InvalidAmount: se nao for inteiro, se for <= 0 ou se exceder o teto.
    """
    raise NotImplementedError
