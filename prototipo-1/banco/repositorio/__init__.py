"""Acesso ao PostgreSQL deste nó.

Este pacote não sabe nada de replicação: lê e escreve na base local deste
processo, e mais nada.
"""

from banco.repositorio.conexao import obter_conexao
from banco.repositorio.contas import RepositorioContas
from banco.repositorio.operacoes import RepositorioOperacoes

__all__ = ["obter_conexao", "RepositorioContas", "RepositorioOperacoes"]
