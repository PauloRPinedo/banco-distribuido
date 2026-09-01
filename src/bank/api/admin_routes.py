"""Rotas de administracao e teste.

- ``GET  /admin/status``  -- papel, epoch, ``commit_index``, ``applied_idx`` e
  quais pares respondem. E o painel pedido pela historia de usuario 11 e o que os
  scripts consultam para descobrir quem e o primario.
- ``GET  /admin/metrics`` -- contadores, TPS e p50/p99 (RF-15).
- ``POST /admin/fault``   -- liga ou desliga falhas injetadas (RF-16).
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/admin", tags=["admin"])


class StatusResponse(BaseModel):
    """Painel de saude do no."""

    node_id: str
    role: str
    epoch: int
    leader_id: str | None
    commit_index: int
    applied_idx: int
    last_idx: int
    peers_alive: dict[str, bool]
    quorum_size: int
    write_available: bool
    """``False`` quando a maioria esta inalcancavel: o no aceita leitura e recusa escrita."""

    faults_active: bool


class FaultRequest(BaseModel):
    """Falhas a injetar. Campos omitidos ficam como estao."""

    drop_replication: float | None = None
    delay_ms: int | None = None
    reject_votes: bool | None = None
    freeze: bool | None = None
    seed: int | None = None


def _ctx(request: Request):
    return request.app.state.ctx


@router.get("/status", response_model=StatusResponse)
def status(request: Request) -> StatusResponse:
    """Historia de usuario 11: qual no esta ativo e quem e o primario."""
    return StatusResponse(**_ctx(request).status())


@router.get("/metrics")
def metrics(request: Request) -> dict:
    """RF-15: metricas de desempenho e estado."""
    ctx = _ctx(request)
    data = ctx.metrics.snapshot()
    data.update(
        {
            "node_id": ctx.config.self_id,
            "role": ctx.node_state.role.value,
            "epoch": ctx.node_state.epoch,
            "commit_index": ctx.log.commit_index,
            "applied_idx": ctx.store.last_applied_idx,
            "locks_held": ctx.locks.held_count(),
        }
    )
    return data


@router.post("/fault")
def inject_fault(request: Request, body: FaultRequest) -> dict:
    """RF-16: injeta falhas em tempo de execucao, para os testes de tolerancia."""
    ctx = _ctx(request)
    config = ctx.faults.configure(**body.model_dump())
    ctx.logger.event("fault_injected", **config.__dict__)
    return {"faults": config.__dict__, "active": ctx.faults.active}
