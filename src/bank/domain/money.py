"""Representacao monetaria do sistema.

Todo valor em dinheiro trafega e e armazenado como um inteiro de **centavos**.
Nunca usar ``float``: a soma de todos os saldos e uma invariante do sistema
(RNF-01) e o arredondamento binario de ponto flutuante a violaria silenciosamente.
"""

from __future__ import annotations

from .errors import InvalidAmount

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
    if not isinstance(raw, str):
        raise ValueError(f"quantia deve ser texto, veio {type(raw).__name__}")

    text = raw.strip().replace(",", ".")
    if not text:
        raise ValueError("quantia vazia")
    if text.startswith("-"):
        raise ValueError("quantia negativa nao e aceita")
    if text.count(".") > 1:
        raise ValueError(f"quantia malformada: {raw!r}")

    whole, _, frac = text.partition(".")
    whole = whole or "0"
    if not whole.isdigit() or (frac and not frac.isdigit()):
        raise ValueError(f"quantia malformada: {raw!r}")
    if len(frac) > 2:
        raise ValueError(f"quantia com mais de duas casas decimais: {raw!r}")

    cents = int(whole) * 100 + int((frac + "00")[:2])
    if cents > MAX_AMOUNT_CENTS:
        raise ValueError(f"quantia acima do teto permitido: {raw!r}")
    return cents


def format_amount(cents: Cents) -> str:
    """Formata centavos para exibicao no CLI (ex.: ``1234`` -> ``"12.34"``)."""
    sign = "-" if cents < 0 else ""
    value = abs(int(cents))
    return f"{sign}{value // 100}.{value % 100:02d}"


def validate_amount(cents: Cents) -> None:
    """Valida uma quantia recebida pela API.

    Raises:
        InvalidAmount: se nao for inteiro, se for <= 0 ou se exceder o teto.
    """
    # bool e subclasse de int: aceitar True como "1 centavo" seria um bug silencioso.
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise InvalidAmount(f"quantia deve ser inteiro de centavos, veio {type(cents).__name__}")
    if cents <= 0:
        raise InvalidAmount("quantia deve ser positiva")
    if cents > MAX_AMOUNT_CENTS:
        raise InvalidAmount("quantia acima do teto permitido")
