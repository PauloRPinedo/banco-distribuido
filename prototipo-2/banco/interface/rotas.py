"""As rotas de cliente.

Cada rota é uma função pura sobre o nó: recebe um `Pedido` e devolve um
dicionário. Não sabe de HTTP — quem traduz estados e erros é `servidor_http`,
num sítio só.

As rotas internas entre nós estão em `rotas_internas`, e as de administração em
`rotas_admin`. A divisão é por audiência, não por capricho: quem lê este
ficheiro está a perguntar o que o banco oferece a um cliente.
"""

import re

from banco.cluster.no import No
from banco.interface.pedido import Pedido, Rota
from banco.dominio.dinheiro import para_centavos
from banco.dominio.erros import ValorInvalido
from banco.dominio.operacoes import CriarConta, Deposito, Saque, Transferencia


def _op_id(corpo: dict) -> str:
    """Toda escrita exige um op_id, e é o cliente que o gera.

    É o que torna a retentativa segura: repetir com o mesmo op_id devolve o
    resultado guardado em vez de mover o dinheiro outra vez. Se o servidor o
    gerasse, a segunda tentativa seria uma operação nova (RF-13).
    """
    identificador = corpo.get("op_id")
    if not isinstance(identificador, str) or not identificador.strip():
        raise ValorInvalido("falta o op_id, que o cliente tem de gerar")
    return identificador.strip()


def _valor(corpo: dict, campo: str = "valor") -> int:
    """Lê um valor monetário, que tem de vir como texto.

    Recusar um número JSON é deliberado: `json.loads` devolveria um float, e um
    float em dinheiro é a origem do desvio de arredondamento que RNF-01 proíbe.
    Exigir texto mantém a conversão a acontecer num sítio só.
    """
    bruto = corpo.get(campo)
    if not isinstance(bruto, str):
        raise ValorInvalido(
            f"o campo {campo!r} tem de vir como texto, por exemplo \"25.00\"")
    return para_centavos(bruto)


def _texto(corpo: dict, campo: str) -> str:
    bruto = corpo.get(campo)
    if not isinstance(bruto, str) or not bruto.strip():
        raise ValorInvalido(f"falta o campo {campo!r}")
    return bruto.strip()


def criar_conta(no: No, pedido: Pedido) -> tuple[int, dict]:
    corpo = pedido.corpo
    operacao = CriarConta(_texto(corpo, "conta"), _valor(corpo, "saldo_inicial"))
    return 201, no.executar(_op_id(corpo), operacao)


def consultar_saldo(no: No, pedido: Pedido) -> tuple[int, dict]:
    return 200, no.saldo(pedido.partes[0])


def depositar(no: No, pedido: Pedido) -> tuple[int, dict]:
    corpo = pedido.corpo
    return 200, no.executar(_op_id(corpo),
                            Deposito(pedido.partes[0], _valor(corpo)))


def sacar(no: No, pedido: Pedido) -> tuple[int, dict]:
    corpo = pedido.corpo
    return 200, no.executar(_op_id(corpo),
                            Saque(pedido.partes[0], _valor(corpo)))


def transferir(no: No, pedido: Pedido) -> tuple[int, dict]:
    corpo = pedido.corpo
    operacao = Transferencia(_texto(corpo, "de"), _texto(corpo, "para"),
                             _valor(corpo))
    return 200, no.executar(_op_id(corpo), operacao)


def consultar_extrato(no: No, pedido: Pedido) -> tuple[int, dict]:
    return 200, no.extrato(pedido.partes[0])


def auditar(no: No, _pedido: Pedido) -> tuple[int, dict]:
    return 200, no.auditoria()


# A ordem importa: /contas/{id}/extrato tem de ser testada antes de /contas/{id}.
ROTAS: list[Rota] = [
    ("POST", re.compile(r"^/contas$"), criar_conta),
    ("POST", re.compile(r"^/contas/([^/]+)/deposito$"), depositar),
    ("POST", re.compile(r"^/contas/([^/]+)/saque$"), sacar),
    ("POST", re.compile(r"^/transferencias$"), transferir),
    ("GET", re.compile(r"^/contas/([^/]+)/extrato$"), consultar_extrato),
    ("GET", re.compile(r"^/contas/([^/]+)$"), consultar_saldo),
    ("GET", re.compile(r"^/auditoria$"), auditar),
]
