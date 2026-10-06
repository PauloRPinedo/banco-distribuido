"""Expõe as mesmas rotas públicas que um nó — o cliente/frontend fala só com
isto, nunca diretamente com um nó.

Regra de encaminhamento: tudo vai ao primário — as escritas porque só ele as
aceita, as leituras porque só ele está garantidamente em dia. As rotas
`/interno/*` também passam, para o painel poder mostrar o cluster.
"""

import logging

from fastapi import FastAPI, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from balanceador.config import carregar_nos, url_base
from balanceador.encaminhador import Encaminhador, SemPrimario

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Balanceador — banco distribuído")
encaminhador = Encaminhador(carregar_nos(), url_base)


@app.get("/saude")
def saude():
    return {"balanceador": "ativo"}


@app.api_route("/{caminho:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(caminho: str, request: Request):
    corpo = await request.body()
    try:
        # Numa thread: o httpx aqui é síncrono, e chamá-lo direto no laço
        # assíncrono atenderia um pedido de cada vez.
        resposta = await run_in_threadpool(
            encaminhador.reenviar, request.method, f"/{caminho}",
            content=corpo,
            headers={k: v for k, v in request.headers.items()
                     if k.lower() not in ("host", "content-length")},
            params=dict(request.query_params),
        )
    except SemPrimario as falha:
        # A mesma forma de erro do banco: o painel tem um só caminho de tratamento.
        return JSONResponse(status_code=503, content={
            "erro": "sem_primario",
            "mensagem": f"{falha} — há uma eleição a decorrer ou não há maioria; "
                        "repetir com o mesmo op_id"})
    return Response(content=resposta.content, status_code=resposta.status_code,
                    media_type=resposta.headers.get("content-type"))


# Handler do AWS Lambda — a mesma `app` do FastAPI, sem duplicar rotas nem
# lógica. O Mangum traduz o evento de uma Lambda Function URL num pedido ASGI
# normal; o `encaminhador` não sabe nem quer saber se foi chamado pelo uvicorn
# ou pelo Lambda. Ver GUIA-IMPLANTACAO.md, secção "Balanceador em Lambda".
try:
    from mangum import Mangum

    handler = Mangum(app)
except ImportError:
    # o mangum não é dependência do backend nem do docker-compose local (só
    # faz falta no pacote que sobe para o Lambda) — não deve partir
    # `uvicorn balanceador.main:app` em desenvolvimento se não estiver instalado.
    handler = None
