"""O número visível de uma conta: agência, oito dígitos e um dígito verificador.

O id interno (`conta.id`) continua a ser a chave de tudo — locks, log, URLs. O
número é o que o cliente lê e dita a outra pessoa para receber uma
transferência, como num banco a sério: `0001 / 12345678-9`.

A agência é `0001` para todo o banco: não há balcões. O dígito verificador é
módulo 11 com pesos 2 a 9, da direita para a esquerda; um dígito errado dá
outro dígito verificador, e o número é recusado antes de chegar à base.

Este módulo é puro. Quem escolhe o número de uma conta nova é o primário, antes
de propor a entrada: o número viaja dentro da entrada, e as réplicas guardam
exatamente o mesmo (um número sorteado em cada nó daria três bancos diferentes).
"""

import re
import secrets

from banco.dominio.erros import ValorInvalido

AGENCIA = "0001"
_PESOS = (2, 3, 4, 5, 6, 7, 8, 9)
_FORMATO = re.compile(r"^\d{8}-\d$")


def digito_verificador(corpo: str) -> str:
    """Módulo 11 sobre os oito dígitos; resto 0 ou 1 dá `0`."""
    if not (isinstance(corpo, str) and len(corpo) == 8 and corpo.isdigit()):
        raise ValorInvalido(f"o corpo do número tem de ter 8 dígitos: {corpo!r}")
    total = sum(int(d) * _PESOS[i % 8] for i, d in enumerate(reversed(corpo)))
    resto = total % 11
    return "0" if resto < 2 else str(11 - resto)


def de_corpo(corpo: str) -> str:
    return f"{corpo}-{digito_verificador(corpo)}"


def sortear() -> str:
    """Um número novo ao acaso. Só o primário o chama; ver o topo do módulo."""
    return de_corpo(f"{secrets.randbelow(100_000_000):08d}")


def e_valido(numero: str) -> bool:
    return (isinstance(numero, str) and bool(_FORMATO.match(numero))
            and digito_verificador(numero[:8]) == numero[9])


def validar(numero: str) -> str:
    if not e_valido(numero):
        raise ValorInvalido(f"número de conta inválido: {numero!r} "
                            "(8 dígitos, traço e dígito verificador)")
    return numero


def normalizar(texto: str) -> str:
    """Aceita o que uma pessoa escreve: com ou sem agência, pontos, espaços, barra.

    `0001 / 1234.5678-9`, `0001123456789` e `123456789` dão `12345678-9`.
    Recusa se o dígito verificador não bate.
    """
    digitos = "".join(ch for ch in str(texto) if ch.isdigit())
    if len(digitos) == 13 and digitos.startswith(AGENCIA):
        digitos = digitos[len(AGENCIA):]
    if len(digitos) != 9:
        raise ValorInvalido(f"número de conta inválido: {texto!r}")
    return validar(f"{digitos[:8]}-{digitos[8]}")


def parece_numero(texto: str) -> bool:
    """Se o texto se lê como um número de conta válido.

    `12345678-9` também seria um id aceitável, por isso quem chama confirma
    depois que existe uma conta com esse número antes de o tratar como tal.
    """
    try:
        normalizar(texto)
    except ValorInvalido:
        return False
    return True


def formatar(numero: str, agencia: str = AGENCIA) -> str:
    return f"{agencia} / {numero}"
