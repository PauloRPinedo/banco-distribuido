"""RPCs entre servidores. Nao fazem parte da API do cliente.

- ``POST /internal/append_entries`` -- replicacao e heartbeat;
- ``POST /internal/request_vote``   -- eleicao;
- ``GET  /internal/snapshot``       -- transferencia de estado completo para um no
  muito atrasado, cujo ponto de partida ja nao existe no log do primario;
- ``GET  /internal/status``         -- sondagem leve usada pelos scripts de teste.

Fora de escopo do projeto (dito na proposta): autenticacao e criptografia. Estas
rotas assumem uma rede confiavel e nos que falham por parada, nunca de forma
maliciosa.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..replication.protocol import AppendEntries, RequestVote, VoteReply

router = APIRouter(prefix="/internal", tags=["interno"])


def _ctx(request: Request):
    return request.app.state.ctx


@router.post("/append_entries")
def append_entries(request: Request, body: dict) -> JSONResponse:
    """Replicacao e heartbeat. Ver replication/replica.py para a ordem das checagens."""
    ctx = _ctx(request)
    if ctx.faults.is_frozen():
        # No congelado: vivo mas mudo. E o cenario que so o fencing por epoch
        # resolve com seguranca.
        return JSONResponse(status_code=503, content={"error": "frozen"})
    ctx.faults.maybe_delay()
    ack = ctx.replica.handle_append_entries(AppendEntries.from_json(body))
    return JSONResponse(content=ack.to_json())


@router.post("/request_vote")
def request_vote(request: Request, body: dict) -> JSONResponse:
    """Eleicao. Ver election/election.py para as tres condicoes do voto."""
    ctx = _ctx(request)
    if ctx.faults.is_frozen():
        return JSONResponse(status_code=503, content={"error": "frozen"})
    ctx.faults.maybe_delay()
    message = RequestVote.from_json(body)
    if ctx.faults.config.reject_votes:
        reply = VoteReply(ctx.node_state.epoch, False, ctx.config.self_id, "fault_injected")
        ctx.logger.event("fault_injected", kind="reject_votes", candidate=message.candidate_id)
        return JSONResponse(content=reply.to_json())
    reply = ctx.election.handle_request_vote(message)
    return JSONResponse(content=reply.to_json())


@router.get("/snapshot")
def snapshot(request: Request) -> dict:
    """Estado completo, para um no atrasado demais para acompanhar pelo log."""
    ctx = _ctx(request)
    return {
        "applied_idx": ctx.store.last_applied_idx,
        "epoch": ctx.node_state.epoch,
        "total_cents": ctx.store.total_cents(),
        "accounts": {a.id: a.balance_cents for a in ctx.store.accounts.values()},
    }


@router.get("/status")
def status(request: Request) -> dict:
    """Sondagem leve, usada pelos scripts e pelo CLI."""
    return _ctx(request).status()
