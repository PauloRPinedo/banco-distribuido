"""As entradas do log que não movem dinheiro.

Tudo o que muda o estado de um nó tem de passar pelo log, senão as três bases
divergem: um utilizador registado só no primário não conseguiria entrar depois
de um failover, e uma taxa registada só lá daria câmbios diferentes em cada nó.

Por isso estas três operações têm o mesmo formato das do domínio — `tipo`,
`contas_tocadas`, `validar`, `aplicar`, `para_dados` — e viajam no log como
elas. Quem as escreve nas tabelas é o `Aplicador`.

O que não é determinista decide-se no primário e vai nos dados: o id e o hash
da senha (com o seu sal) do utilizador, o instante de uma taxa.
"""

from dataclasses import dataclass
from typing import ClassVar

from banco.dominio.contas import Livro
from banco.dominio.operacoes import Operacao
from banco.dominio.operacoes import de_dados as de_dados_do_dominio

REGISTAR_USUARIO = "registar_usuario"
REGISTAR_TAXA = "registar_taxa"
NOOP = "noop"


@dataclass(frozen=True)
class RegistarUsuario(Operacao):
    tipo: ClassVar[str] = REGISTAR_USUARIO
    id: str
    nome: str
    email: str
    hash_senha: str

    def contas_tocadas(self) -> tuple[str, ...]:
        return ()

    def validar(self, livro: Livro, instante: float) -> None:
        pass  # o email repetido verifica-o o serviço, contra a tabela

    def aplicar(self, livro: Livro, indice: int, instante: float) -> dict:
        return {"id": self.id, "email": self.email}

    def para_dados(self) -> dict:
        return {"id": self.id, "nome": self.nome, "email": self.email,
                "hash_senha": self.hash_senha}


@dataclass(frozen=True)
class RegistarTaxa(Operacao):
    tipo: ClassVar[str] = REGISTAR_TAXA
    moeda_origem: str
    moeda_destino: str
    taxa_milionesimos: int

    def contas_tocadas(self) -> tuple[str, ...]:
        return ()

    def validar(self, livro: Livro, instante: float) -> None:
        pass

    def aplicar(self, livro: Livro, indice: int, instante: float) -> dict:
        return {"moeda_origem": self.moeda_origem,
                "moeda_destino": self.moeda_destino,
                "taxa_milionesimos": self.taxa_milionesimos,
                "vigente_desde": instante}

    def para_dados(self) -> dict:
        return {"moeda_origem": self.moeda_origem,
                "moeda_destino": self.moeda_destino,
                "taxa_milionesimos": self.taxa_milionesimos}


@dataclass(frozen=True)
class Noop(Operacao):
    """Escrita pelo primário ao assumir o mandato.

    Uma entrada herdada do primário anterior não pode ser confirmada por
    contagem de réplicas; confirmando primeiro esta, do epoch novo, tudo o que
    vem antes fica confirmado por arrasto.
    """

    tipo: ClassVar[str] = NOOP

    def contas_tocadas(self) -> tuple[str, ...]:
        return ()

    def validar(self, livro: Livro, instante: float) -> None:
        pass

    def aplicar(self, livro: Livro, indice: int, instante: float) -> dict:
        return {}

    def para_dados(self) -> dict:
        return {}


_DE_SISTEMA: dict[str, type[Operacao]] = {
    REGISTAR_USUARIO: RegistarUsuario,
    REGISTAR_TAXA: RegistarTaxa,
    NOOP: Noop,
}


def de_dados(tipo: str, dados: dict) -> Operacao:
    """Reconstrói qualquer operação do log, de dinheiro ou de sistema."""
    classe = _DE_SISTEMA.get(tipo)
    if classe is not None:
        return classe(**dados)
    return de_dados_do_dominio(tipo, dados)


def move_dinheiro(operacao: Operacao) -> bool:
    return type(operacao) not in _DE_SISTEMA.values()
