"""Acesso ao PostgreSQL deste nó.

Cada nó tem o seu próprio Postgres, independente dos outros. Este pacote não
sabe nada de replicação: lê e escreve na base local deste processo, e mais nada.
"""

from banco.repositorio.conexao import obter_conexao
from banco.repositorio.contas import RepositorioContas
from banco.repositorio.operacoes import RepositorioOperacoes
from banco.repositorio.sistemas_externos import RepositorioSistemasExternos
from banco.repositorio.taxa_cambio import RepositorioTaxaCambio
from banco.repositorio.usuarios import RepositorioUsuarios

__all__ = [
    "obter_conexao",
    "RepositorioContas",
    "RepositorioOperacoes",
    "RepositorioSistemasExternos",
    "RepositorioTaxaCambio",
    "RepositorioUsuarios",
]
