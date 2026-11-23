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

    Recusa o que não for texto. O dinheiro viaja como texto JSON e um número
    é recusado com `valor_invalido`; sem esta guarda, `str(25.00)` daria "25.0"
    e o número passaria em silêncio, dentro do único módulo que existe para o
    impedir.
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


MOEDAS = ("BRL", "USD", "PEN")

_SIMBOLO = {"BRL": "R$", "USD": "US$", "PEN": "S/"}


def formatar(centavos: int, moeda: str = "BRL") -> str:
    """Devolve "R$ 1.234,56": ponto nos milhares, vírgula nos decimais."""
    sinal = "-" if centavos < 0 else ""
    inteiros, resto = divmod(abs(centavos), 100)
    milhares = f"{inteiros:,}".replace(",", ".")
    return f"{sinal}{_SIMBOLO.get(moeda, moeda)} {milhares},{resto:02d}"


# Taxas (de câmbio e de juros) em milionésimos inteiros: 5,4321 é 5_432_100.
# Pela mesma razão que o dinheiro é inteiro de centavos — uma taxa em float
# arredondaria de maneira diferente em máquinas diferentes, e três nós a
# reaplicar o mesmo log chegariam a saldos diferentes.
MILIONESIMOS = 1_000_000

_FORMATO_TAXA = re.compile(r"^\d{1,6}([.,]\d{1,6})?$")


def para_milionesimos(texto: str) -> int:
    """Converte "5.4321" em 5_432_100. Seis casas decimais no máximo."""
    if not isinstance(texto, str) or not _FORMATO_TAXA.match(texto.strip()):
        raise ValorInvalido(f"taxa mal formada: {texto!r} (até 6 casas decimais)")
    valor = int(Decimal(texto.strip().replace(",", ".")) * MILIONESIMOS)
    if valor <= 0:
        raise ValorInvalido("a taxa tem de ser maior do que zero")
    return valor


def formatar_taxa(milionesimos: int) -> str:
    inteiros, resto = divmod(milionesimos, MILIONESIMOS)
    return f"{inteiros}.{resto:06d}"


def converter(valor_centavos: int, taxa_milionesimos: int) -> int:
    """Valor na moeda de destino, arredondado para baixo ao centavo.

    Para baixo, e num só sítio: arredondar para cima daria ao cliente uma
    fração de centavo que o banco não tem. A fração que fica para trás não
    desaparece da auditoria — cada moeda é auditada separadamente.
    """
    return valor_centavos * taxa_milionesimos // MILIONESIMOS
