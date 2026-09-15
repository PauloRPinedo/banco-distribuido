"""Dinheiro em centavos inteiros.

Todo valor monetário do sistema é um `int` de centavos. A conversão a partir de
texto acontece uma única vez, aqui, na fronteira; daí para dentro só circulam
centavos.

Nunca `float`. RNF-01 exige que a soma de todos os saldos seja constante depois
de milhares de operações, e com ponto flutuante essa soma desvia-se por
arredondamento. O teste da invariante falharia a apontar para a replicação, que
estaria certa, e perder-se-iam dias no sítio errado.
"""

import re
from decimal import Decimal, InvalidOperation

from banco.dominio.erros import ValorInvalido

# Até 15 dígitos inteiros e no máximo duas casas decimais, com ponto ou vírgula.
# Recusar três casas é deliberado: "10.005" não tem representação em centavos, e
# aceitá-la obrigaria a arredondar dinheiro sem o cliente saber.
_FORMATO = re.compile(r"^\d{1,15}([.,]\d{1,2})?$")

_CEM = Decimal(100)


def para_centavos(texto: str) -> int:
    """Converte "123.45" ou "123,45" em 12345.

    Aceita as duas separações decimais porque o cliente escreve em português na
    linha de comando e em inglês no corpo JSON.

    Recusa o que não for texto. SPECS 6 exige que o dinheiro viaje como texto
    JSON e que um número seja recusado com `valor_invalido`; sem esta guarda,
    `str(25.00)` daria "25.0" e o número passaria em silêncio, dentro do único
    módulo que existe para o impedir.
    """
    if not isinstance(texto, str):
        raise ValorInvalido(
            f"o valor tem de vir como texto, não {type(texto).__name__}: {texto!r}")
    limpo = texto.strip()
    if not _FORMATO.match(limpo):
        raise ValorInvalido(f"valor mal formado: {texto!r}")
    try:
        valor = Decimal(limpo.replace(",", "."))
    except InvalidOperation:
        raise ValorInvalido(f"valor mal formado: {texto!r}") from None
    return int(valor * _CEM)


def formatar(centavos: int) -> str:
    """Devolve "R$ 1.234,56": ponto nos milhares, vírgula nos decimais."""
    sinal = "-" if centavos < 0 else ""
    inteiros, resto = divmod(abs(centavos), 100)
    milhares = f"{inteiros:,}".replace(",", ".")
    return f"{sinal}R$ {milhares},{resto:02d}"
