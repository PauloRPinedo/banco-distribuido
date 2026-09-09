"""As rotas de cliente da secção 6.1 de docs/SPECS.md.

Cada rota é uma função pura sobre o nó: recebe os pedaços do caminho e o corpo
já descodificado, e devolve um dicionário. Não sabe de HTTP — quem traduz
estados e erros é `servidor_http`, num sítio só.
"""

import re
from typing import Callable

from banco.cluster.no import No
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
    Exigir texto mantém a conversão a acontecer num sítio só (SPECS 3.1).
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


def criar_conta(no: No, _partes: tuple, corpo: dict) -> tuple[int, dict]:
    operacao = CriarConta(_texto(corpo, "conta"), _valor(corpo, "saldo_inicial"))
    return 201, no.executar(_op_id(corpo), operacao)


def consultar_saldo(no: No, partes: tuple, _corpo: dict) -> tuple[int, dict]:
    return 200, no.saldo(partes[0])


def depositar(no: No, partes: tuple, corpo: dict) -> tuple[int, dict]:
    return 200, no.executar(_op_id(corpo), Deposito(partes[0], _valor(corpo)))


def sacar(no: No, partes: tuple, corpo: dict) -> tuple[int, dict]:
    return 200, no.executar(_op_id(corpo), Saque(partes[0], _valor(corpo)))


def transferir(no: No, _partes: tuple, corpo: dict) -> tuple[int, dict]:
    operacao = Transferencia(_texto(corpo, "de"), _texto(corpo, "para"),
                             _valor(corpo))
    return 200, no.executar(_op_id(corpo), operacao)


def consultar_extrato(no: No, partes: tuple, _corpo: dict) -> tuple[int, dict]:
    return 200, no.extrato(partes[0])


def auditar(no: No, _partes: tuple, _corpo: dict) -> tuple[int, dict]:
    return 200, no.auditoria()


def estado(no: No, _partes: tuple, _corpo: dict) -> tuple[int, dict]:
    return 200, no.estado_do_no()


Rota = tuple[str, re.Pattern, Callable]

# A ordem importa: /contas/{id}/extrato tem de ser testada antes de /contas/{id}.
ROTAS: list[Rota] = [
    ("POST", re.compile(r"^/contas$"), criar_conta),
    ("POST", re.compile(r"^/contas/([^/]+)/deposito$"), depositar),
    ("POST", re.compile(r"^/contas/([^/]+)/saque$"), sacar),
    ("POST", re.compile(r"^/transferencias$"), transferir),
    ("GET", re.compile(r"^/contas/([^/]+)/extrato$"), consultar_extrato),
    ("GET", re.compile(r"^/contas/([^/]+)$"), consultar_saldo),
    ("GET", re.compile(r"^/auditoria$"), auditar),
    ("GET", re.compile(r"^/interno/estado$"), estado),
]


def encontrar(metodo: str, caminho: str) -> tuple[Callable, tuple] | None:
    for metodo_da_rota, padrao, funcao in ROTAS:
        correspondencia = padrao.match(caminho)
        if correspondencia and metodo_da_rota == metodo:
            return funcao, correspondencia.groups()
    return None
