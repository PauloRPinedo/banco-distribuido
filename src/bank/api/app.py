"""Montagem da aplicacao FastAPI e do container de dependencias.

Tres grupos de rotas, separados de proposito:

- ``client_routes``   -- o que o cliente do banco usa (RF-01..RF-05, RF-14);
- ``internal_routes`` -- os RPCs entre servidores (nao sao API publica);
- ``admin_routes``    -- estado, metricas e injecao de falhas (RF-15, RF-16).
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI

from ..config import ClusterConfig


@dataclass
class ServerContext:
    """Tudo que as rotas precisam, montado uma vez no boot.

    Guardado em ``app.state.ctx``; as rotas o obtem por uma dependencia, para os
    testes poderem injetar um contexto falso.
    """

    config: ClusterConfig
    node_state: object
    store: object
    log: object
    primary: object
    replica: object
    election: object
    locks: object
    metrics: object
    logger: object
    faults: object


def build_context(config: ClusterConfig) -> ServerContext:
    """Recupera o estado do disco e monta todos os componentes do no.

    Ordem: recuperacao (snapshot + replay do WAL) -> estado do no -> log
    replicado -> replicador/aplicador -> eleicao. O no sempre sobe como REPLICA,
    mesmo que fosse primario antes de cair: quem decide quem manda e a eleicao.
    """
    raise NotImplementedError


def create_app(config: ClusterConfig) -> FastAPI:
    """Cria a aplicacao, registra as rotas e liga as threads de fundo."""
    raise NotImplementedError
