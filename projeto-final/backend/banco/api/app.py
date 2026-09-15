"""Ensambla la app FastAPI — cada router es un *controller* de
diagrama-de-clases-interfaz.md.
"""

from fastapi import FastAPI

from banco.api import rutas_auditoria, rutas_auth, rutas_cuentas, rutas_internas, rutas_transferencias


def crear_app() -> FastAPI:
    app = FastAPI(title="Banco distribuido", version="0.1.0")
    app.include_router(rutas_cuentas.router)
    app.include_router(rutas_transferencias.router)
    app.include_router(rutas_auditoria.router)
    app.include_router(rutas_auth.router)
    app.include_router(rutas_internas.router)
    return app


app = crear_app()
