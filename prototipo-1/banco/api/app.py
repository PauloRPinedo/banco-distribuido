"""A aplicação: as rotas de cliente e a tradução uniforme dos erros."""

import os

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from banco.api import (rotas_auditoria, rotas_contas, rotas_transferencias,
                       traducao)
from banco.dominio.erros import ErroDoBanco


def criar_app() -> FastAPI:
    aplicacao = FastAPI(title="Banco distribuído — Protótipo 1", version="1.0.0")

    # Registados por classe raiz: o Starlette procura pela hierarquia, por isso
    # um `SaldoInsuficiente` cai aqui sem ter de estar listado.
    aplicacao.add_exception_handler(ErroDoBanco, traducao.erro_do_banco)
    aplicacao.add_exception_handler(RequestValidationError, traducao.corpo_invalido)

    aplicacao.include_router(rotas_contas.router)
    aplicacao.include_router(rotas_transferencias.router)
    aplicacao.include_router(rotas_auditoria.router)

    @aplicacao.get("/saude")
    def saude() -> dict:
        """Diz que o processo está de pé, sem tocar na base.

        Serve o `healthcheck` do contentor e serve os testes, que esperam por
        esta rota a responder em vez de esperarem um número de segundos
        inventado.
        """
        return {"no": os.environ.get("NO_ID", "A"), "estado": "de pé"}

    return aplicacao


app = criar_app()
