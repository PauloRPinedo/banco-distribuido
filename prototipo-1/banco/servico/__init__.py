"""A ponte entre o domínio puro e o PostgreSQL.

Carrega as contas envolvidas, corre a operação do domínio sobre elas e guarda
o resultado. O domínio continua a não saber que o PostgreSQL existe.
"""

from banco.servico.consultas import Auditoria, ServicoDeConsultas
from banco.servico.escrita import ServicoDeEscrita

__all__ = ["Auditoria", "ServicoDeConsultas", "ServicoDeEscrita"]
