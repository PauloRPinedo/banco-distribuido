"""Junta as tabelas de rotas e encontra quem atende um pedido.

Existe para que `servidor_http` não precise de saber quantos ficheiros de rotas
há. Acrescentar uma família de rotas é acrescentar um import a esta lista.

A ordem da composição importa menos do que a ordem **dentro** de cada tabela: os
padrões de famílias diferentes não se sobrepõem, mas `/contas/{id}/extrato` e
`/contas/{id}` sim.
"""

from typing import Callable

from banco.interface import rotas, rotas_admin, rotas_internas
from banco.interface.pedido import Rota

TODAS: list[Rota] = [*rotas.ROTAS, *rotas_internas.ROTAS,
                     *rotas_admin.ROTAS]


def encontrar(metodo: str, caminho: str) -> tuple[Callable, tuple] | None:
    for metodo_da_rota, padrao, funcao in TODAS:
        correspondencia = padrao.match(caminho)
        if correspondencia and metodo_da_rota == metodo:
            return funcao, correspondencia.groups()
    return None


def caminho_existe(caminho: str) -> bool:
    """Se algum método serve este caminho.

    Distingue "essa rota não existe" de "essa rota existe mas não com esse
    método" — e é o que permite responder ao *preflight* do navegador sem dizer
    que sim a tudo.
    """
    return any(padrao.match(caminho) for _, padrao, _ in TODAS)
