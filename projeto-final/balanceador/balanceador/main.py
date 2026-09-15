"""Expone las mismas rutas públicas que un nodo — el cliente/frontend le
habla solo a esto, nunca directo a un nodo (ver diagrama-de-despliegue.md).

Regla de enrutamiento: GET es lectura (cualquier nodo), todo lo demás
(POST/PUT/DELETE) es escritura (al primario) — coincide con cómo está
diseñada la API en banco/api/ (ninguna escritura usa GET).
"""

import logging

from fastapi import FastAPI, Request, Response

from balanceador.config import cargar_nodos, url_base
from balanceador.enrutador import Enrutador

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Balanceador — banco distribuido")
enrutador = Enrutador(cargar_nodos(), url_base)

_RUTAS_INTERNAS = ("/interno/", "/docs", "/openapi.json", "/redoc")


@app.get("/salud")
def salud():
    return {"balanceador": "activo"}


@app.api_route("/{ruta:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(ruta: str, request: Request):
    cuerpo = await request.body()
    es_escritura = request.method != "GET"
    respuesta = enrutador.reenviar(
        request.method, f"/{ruta}", es_escritura,
        content=cuerpo,
        headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
        params=dict(request.query_params),
    )
    return Response(content=respuesta.content, status_code=respuesta.status_code,
                     media_type=respuesta.headers.get("content-type"))


# Handler de AWS Lambda — mismo `app` de FastAPI, sin duplicar rutas ni
# lógica. Mangum traduce el evento de Lambda Function URL a una petición
# ASGI normal; `enrutador` no sabe ni le importa si lo invocó uvicorn o
# Lambda. Ver GUIA-DESPLIEGUE.md, sección "Balanceador en Lambda".
try:
    from mangum import Mangum

    handler = Mangum(app)
except ImportError:
    # mangum no es dependencia de banco/backend ni de docker-compose local
    # (solo hace falta en el paquete que se sube a Lambda) — no debe romper
    # `uvicorn balanceador.main:app` en desarrollo si no está instalado.
    handler = None
