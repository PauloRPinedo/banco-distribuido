"""A aplicação: as rotas de cliente, as internas e a tradução uniforme dos erros."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from banco.api import (rotas_admin, rotas_auditoria, rotas_auth, rotas_contas,
                       rotas_internas, rotas_transferencias, traducao)
from banco.api.dependencias import fechar_no_do_processo, no_do_processo
from banco.dominio.erros import ErroDoBanco


@asynccontextmanager
async def ciclo_de_vida(_aplicacao: FastAPI):
    """Cria o nó, recupera o que ficou por aplicar, e começa a bater o coração."""
    no_do_processo().arrancar()
    yield
    fechar_no_do_processo()


def criar_app() -> FastAPI:
    aplicacao = FastAPI(title="Banco distribuído — Protótipo 2", version="0.3.0",
                        lifespan=ciclo_de_vida)

    # Registados por classe raiz: o Starlette procura pela hierarquia, por isso
    # um `SaldoInsuficiente` ou um `NaoSouPrimario` cai aqui sem estar listado.
    aplicacao.add_exception_handler(ErroDoBanco, traducao.erro_do_banco)
    aplicacao.add_exception_handler(RequestValidationError, traducao.corpo_invalido)

    aplicacao.include_router(rotas_auth.router)
    aplicacao.include_router(rotas_contas.router)
    aplicacao.include_router(rotas_transferencias.router)
    aplicacao.include_router(rotas_auditoria.router)
    aplicacao.include_router(rotas_admin.router)
    aplicacao.include_router(rotas_internas.router)

    @aplicacao.get("/saude")
    def saude() -> dict:
        """Diz que o processo está de pé, sem tocar na base."""
        no = no_do_processo()
        return {"no": no.id, "estado": "de pé",
                "papel": no.estado_do_no()["papel"]}

    return aplicacao


app = criar_app()
