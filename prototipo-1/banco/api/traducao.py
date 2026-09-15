"""Tudo o que o banco recusa vira resposta HTTP aqui, e só aqui.

Cada `ErroDoBanco` já carrega o seu código e o seu estado, por isso esta
tradução não precisa de os enumerar: acrescentar um erro novo ao domínio não
obriga a mexer no servidor.

São tratadores registados na aplicação, e não `try/except` em cada rota. Com
`try/except` a tradução ficava repetida sete vezes e bastava esquecer um para
o cliente receber um 500 opaco no dia da demonstração.
"""

from fastapi import Request
from fastapi.responses import JSONResponse

from banco.dominio.erros import ErroDoBanco, ValorInvalido


async def erro_do_banco(pedido: Request, erro: ErroDoBanco) -> JSONResponse:
    """A forma de erro de SPECS 6: `{"erro": ..., "mensagem": ...}`, sem envelope."""
    return JSONResponse(status_code=erro.estado_http, content=erro.para_json())


async def corpo_invalido(pedido: Request, erro: Exception) -> JSONResponse:
    """Um corpo que o modelo recusa é `valor_invalido`, não o 422 do FastAPI.

    O 422 traz o formato de erro do framework, com uma lista de `loc`/`msg` que
    não é a de SPECS 6. Traduzir aqui mantém uma só forma de erro em toda a
    API — que é o que permite ao cliente ter um só caminho de tratamento.
    """
    campos = ", ".join(
        ".".join(str(parte) for parte in problema.get("loc", ()) if parte != "body")
        for problema in getattr(erro, "errors", list)()
    ) or "o corpo do pedido"
    recusa = ValorInvalido(f"corpo inválido: {campos}")
    return JSONResponse(status_code=recusa.estado_http, content=recusa.para_json())
