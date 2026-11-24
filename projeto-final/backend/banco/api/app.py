"""A aplicação: as rotas de cliente, as internas e a tradução uniforme dos erros."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from banco.api import (externas, rotas_admin, rotas_auditoria, rotas_auth, rotas_contas,
                       rotas_internas, rotas_transferencias, traducao)
from banco.api.dependencias import fechar_no_do_processo, no_do_processo
from banco.dominio.erros import ErroDoBanco


@asynccontextmanager
async def ciclo_de_vida(_aplicacao: FastAPI):
    """Cria o nó, recupera o que ficou por aplicar, e começa a bater o coração.

    O reconciliador termina as transferências externas que ficaram a meio
    (`api/externas.py`); só trabalha enquanto este nó for o primário.
    """
    no_do_processo().arrancar()
    reconciliador = externas.Reconciliador()
    reconciliador.arrancar()
    yield
    reconciliador.parar()
    fechar_no_do_processo()


class DizSeEPrimario:
    """Acrescenta `X-Primario-Pronto: sim|nao` a todas as respostas.

    É o que deixa o balanceador confiar no primário em cache sem lhe perguntar
    antes de cada pedido: se a resposta diz `nao`, ele volta a procurar.
    ASGI puro, e não um `@middleware("http")`, para não custar quase nada.
    """

    def __init__(self, app) -> None:
        self.aplicacao = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.aplicacao(scope, receive, send)
            return

        async def enviar(mensagem):
            if mensagem["type"] == "http.response.start":
                no = no_do_processo()
                pronto = b"sim" if no.e_primario() and no.pronto() else b"nao"
                mensagem.setdefault("headers", []).append((b"x-primario-pronto", pronto))
            await send(mensagem)

        await self.aplicacao(scope, receive, enviar)


def criar_app() -> FastAPI:
    aplicacao = FastAPI(title="Banco distribuído — Projeto final", version="0.3.0",
                        lifespan=ciclo_de_vida)

    # Registados por classe raiz: o Starlette procura pela hierarquia, por isso
    # um `SaldoInsuficiente` ou um `NaoSouPrimario` cai aqui sem estar listado.
    aplicacao.add_exception_handler(ErroDoBanco, traducao.erro_do_banco)
    aplicacao.add_exception_handler(RequestValidationError, traducao.corpo_invalido)
    aplicacao.add_middleware(DizSeEPrimario)

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
