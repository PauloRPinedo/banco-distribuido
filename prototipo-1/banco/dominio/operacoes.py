"""As quatro operações do banco, puras e determinísticas.

Cada operação sabe três coisas: que contas toca, se é válida, e como se aplica.
Separar `validar` de `aplicar` não é estilo — é a ordem obrigatória de uma
escrita: valida-se **antes** de gravar no WAL, para nunca se registar uma
operação que vai ser recusada.
"""

from dataclasses import dataclass
from typing import ClassVar

from banco.dominio.contas import Livro, Movimento, validar_id
from banco.dominio.dinheiro import formatar
from banco.dominio.erros import (ContaDuplicada, SaldoInsuficiente,
                                 ValorInvalido)

CRIAR_CONTA = "criar_conta"
DEPOSITO = "deposito"
SAQUE = "saque"
TRANSFERENCIA = "transferencia"


class Operacao:
    """Base das quatro operações."""

    tipo: ClassVar[str]

    def contas_tocadas(self) -> tuple[str, ...]:
        """Ids das contas envolvidas, **já ordenados**.

        A ordem total dos locks nasce aqui, e não no ponto de uso. Quem adquire
        os locks percorre esta tupla e pronto: não tem de se lembrar da regra,
        e por isso não a pode esquecer. É o que torna impossível o deadlock de
        alice->bob contra bob->alice.
        """
        raise NotImplementedError

    def validar(self, livro: Livro) -> None:
        raise NotImplementedError

    def aplicar(self, livro: Livro, indice: int, instante: float) -> dict:
        raise NotImplementedError

    def para_dados(self) -> dict:
        """Argumentos da operação, como vão para o campo `dados` do WAL."""
        raise NotImplementedError


def _validar_valor(valor_centavos: int) -> None:
    if not isinstance(valor_centavos, int) or isinstance(valor_centavos, bool):
        raise ValorInvalido("o valor tem de ser um inteiro de centavos")
    if valor_centavos <= 0:
        raise ValorInvalido("o valor tem de ser maior do que zero")


@dataclass(frozen=True)
class CriarConta(Operacao):
    tipo: ClassVar[str] = CRIAR_CONTA
    conta: str
    saldo_inicial_centavos: int

    def contas_tocadas(self) -> tuple[str, ...]:
        return (self.conta,)

    def validar(self, livro: Livro) -> None:
        validar_id(self.conta)
        if self.saldo_inicial_centavos < 0:
            raise ValorInvalido("o saldo inicial não pode ser negativo")
        if livro.existe(self.conta):
            raise ContaDuplicada(f"a conta {self.conta!r} já existe")

    def aplicar(self, livro: Livro, indice: int, instante: float) -> dict:
        self.validar(livro)
        conta = livro.criar(self.conta, self.saldo_inicial_centavos, instante)
        livro.registar(self.conta, Movimento(
            indice, CRIAR_CONTA, self.saldo_inicial_centavos, None,
            conta.saldo_centavos, instante))
        return {"conta": self.conta, "saldo_centavos": conta.saldo_centavos}

    def para_dados(self) -> dict:
        return {"conta": self.conta,
                "saldo_inicial_centavos": self.saldo_inicial_centavos}


@dataclass(frozen=True)
class Deposito(Operacao):
    tipo: ClassVar[str] = DEPOSITO
    conta: str
    valor_centavos: int

    def contas_tocadas(self) -> tuple[str, ...]:
        return (self.conta,)

    def validar(self, livro: Livro) -> None:
        _validar_valor(self.valor_centavos)
        livro.obter(self.conta)

    def aplicar(self, livro: Livro, indice: int, instante: float) -> dict:
        self.validar(livro)
        conta = livro.obter(self.conta)
        conta.saldo_centavos += self.valor_centavos
        livro.registar(self.conta, Movimento(
            indice, DEPOSITO, self.valor_centavos, None,
            conta.saldo_centavos, instante))
        return {"conta": self.conta, "saldo_centavos": conta.saldo_centavos}

    def para_dados(self) -> dict:
        return {"conta": self.conta, "valor_centavos": self.valor_centavos}


@dataclass(frozen=True)
class Saque(Operacao):
    tipo: ClassVar[str] = SAQUE
    conta: str
    valor_centavos: int

    def contas_tocadas(self) -> tuple[str, ...]:
        return (self.conta,)

    def validar(self, livro: Livro) -> None:
        _validar_valor(self.valor_centavos)
        conta = livro.obter(self.conta)
        if conta.saldo_centavos < self.valor_centavos:
            raise SaldoInsuficiente(_falta(self.conta, conta.saldo_centavos,
                                           self.valor_centavos))

    def aplicar(self, livro: Livro, indice: int, instante: float) -> dict:
        self.validar(livro)
        conta = livro.obter(self.conta)
        conta.saldo_centavos -= self.valor_centavos
        livro.registar(self.conta, Movimento(
            indice, SAQUE, -self.valor_centavos, None,
            conta.saldo_centavos, instante))
        return {"conta": self.conta, "saldo_centavos": conta.saldo_centavos}

    def para_dados(self) -> dict:
        return {"conta": self.conta, "valor_centavos": self.valor_centavos}


@dataclass(frozen=True)
class Transferencia(Operacao):
    """Debita e credita numa só função, sem estado intermédio (RF-05).

    Não existe instante nenhum em que o dinheiro tenha saído de uma conta e
    ainda não tenha entrado na outra. É daqui, e só daqui, que vem a atomicidade
    da transferência — sem commit em duas fases, porque as duas contas estão
    sempre no mesmo nó.
    """

    tipo: ClassVar[str] = TRANSFERENCIA
    de: str
    para: str
    valor_centavos: int

    def contas_tocadas(self) -> tuple[str, ...]:
        return tuple(sorted((self.de, self.para)))

    def validar(self, livro: Livro) -> None:
        _validar_valor(self.valor_centavos)
        if self.de == self.para:
            raise ValorInvalido("a origem e o destino são a mesma conta")
        origem = livro.obter(self.de)
        livro.obter(self.para)
        if origem.saldo_centavos < self.valor_centavos:
            raise SaldoInsuficiente(_falta(self.de, origem.saldo_centavos,
                                           self.valor_centavos))

    def aplicar(self, livro: Livro, indice: int, instante: float) -> dict:
        self.validar(livro)
        origem = livro.obter(self.de)
        destino = livro.obter(self.para)

        origem.saldo_centavos -= self.valor_centavos
        destino.saldo_centavos += self.valor_centavos

        livro.registar(self.de, Movimento(
            indice, TRANSFERENCIA, -self.valor_centavos, self.para,
            origem.saldo_centavos, instante))
        livro.registar(self.para, Movimento(
            indice, TRANSFERENCIA, self.valor_centavos, self.de,
            destino.saldo_centavos, instante))
        return {"de": self.de, "para": self.para,
                "saldos_centavos": {self.de: origem.saldo_centavos,
                                    self.para: destino.saldo_centavos}}

    def para_dados(self) -> dict:
        return {"de": self.de, "para": self.para,
                "valor_centavos": self.valor_centavos}


_POR_TIPO: dict[str, type[Operacao]] = {
    CRIAR_CONTA: CriarConta,
    DEPOSITO: Deposito,
    SAQUE: Saque,
    TRANSFERENCIA: Transferencia,
}


def de_dados(tipo: str, dados: dict) -> Operacao:
    """Reconstrói uma operação a partir de uma entrada do WAL."""
    classe = _POR_TIPO.get(tipo)
    if classe is None:
        raise ValorInvalido(f"tipo de operação desconhecido: {tipo!r}")
    return classe(**dados)


def total_esperado(operacoes: list[Operacao]) -> int:
    """Total em circulação calculado só a partir das operações.

    É o lado direito da auditoria (F-06). Criar conta e depósito acrescentam
    dinheiro, saque retira, e a transferência é neutra por construção.

    Este cálculo não olha para os saldos: é justamente por ser independente que
    compará-lo com `Livro.total_centavos()` verifica alguma coisa. Somar duas
    vezes a mesma estrutura não auditaria nada.
    """
    total = 0
    for operacao in operacoes:
        if isinstance(operacao, CriarConta):
            total += operacao.saldo_inicial_centavos
        elif isinstance(operacao, Deposito):
            total += operacao.valor_centavos
        elif isinstance(operacao, Saque):
            total -= operacao.valor_centavos
    return total


def _falta(conta: str, saldo_centavos: int, pedido_centavos: int) -> str:
    return (f"{conta} tem {formatar(saldo_centavos)} e a operação pede "
            f"{formatar(pedido_centavos)}")
