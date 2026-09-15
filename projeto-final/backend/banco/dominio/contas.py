"""As contas do banco e o extrato de cada uma.

O `Livro` é a única estrutura que guarda saldos. É puro: não sabe de onde vêm as
operações nem para onde vão. Reconstruí-lo pela mesma sequência de operações dá
sempre o mesmo resultado, e é essa propriedade que a etapa 2 vai usar para
replicar por log.
"""

import re
from dataclasses import dataclass, field

from banco.dominio.erros import ContaDuplicada, ContaInexistente, ValorInvalido

_ID_VALIDO = re.compile(r"^[a-z0-9_-]{1,32}$")


def validar_id(identificador: str) -> str:
    """Recusa ids fora de [a-z0-9_-]{1,32}.

    O formato é restrito de propósito: o id aparece em caminhos de URL, em nomes
    de ficheiro e em ordenação de locks. Aceitar espaços ou maiúsculas obrigaria
    a normalizar em cada um desses sítios, e um esquecimento dava dois locks
    diferentes para a mesma conta.
    """
    if not isinstance(identificador, str) or not _ID_VALIDO.match(identificador):
        raise ValorInvalido(
            f"id de conta inválido: {identificador!r} "
            "(1 a 32 caracteres de a-z, 0-9, _ ou -)"
        )
    return identificador


@dataclass
class Conta:
    id: str
    saldo_centavos: int
    criada_em: float


@dataclass(frozen=True)
class Movimento:
    """Uma linha do extrato, do ponto de vista de uma conta.

    Guarda o saldo depois do movimento porque o extrato é lido muito depois de
    a operação acontecer, e recalcular o saldo linha a linha obrigaria a
    reprocessar o log inteiro a cada consulta.
    """

    indice: int
    tipo: str
    valor_centavos: int
    contraparte: str | None
    saldo_depois_centavos: int
    instante: float


@dataclass
class Livro:
    contas: dict[str, Conta] = field(default_factory=dict)
    extratos: dict[str, list[Movimento]] = field(default_factory=dict)

    def existe(self, identificador: str) -> bool:
        return identificador in self.contas

    def obter(self, identificador: str) -> Conta:
        conta = self.contas.get(identificador)
        if conta is None:
            raise ContaInexistente(f"a conta {identificador!r} não existe")
        return conta

    def criar(self, identificador: str, saldo_centavos: int, instante: float) -> Conta:
        if identificador in self.contas:
            raise ContaDuplicada(f"a conta {identificador!r} já existe")
        conta = Conta(identificador, saldo_centavos, instante)
        self.contas[identificador] = conta
        self.extratos[identificador] = []
        return conta

    def registar(self, identificador: str, movimento: Movimento) -> None:
        self.extratos[identificador].append(movimento)

    def extrato(self, identificador: str) -> list[Movimento]:
        self.obter(identificador)
        return list(self.extratos[identificador])

    def total_centavos(self) -> int:
        """Soma de todos os saldos. É o lado esquerdo da auditoria (RF-14)."""
        return sum(conta.saldo_centavos for conta in self.contas.values())
