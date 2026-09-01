"""Rotas de administracao e teste.

- ``GET  /admin/status``  -- papel, epoch, ``commit_index``, ``applied_idx`` e
  quais pares respondem. E o painel pedido pela historia de usuario 11 e o que os
  scripts consultam para descobrir quem e o primario.
- ``GET  /admin/metrics`` -- contadores, TPS e p50/p99 (RF-15).
- ``POST /admin/fault``   -- liga ou desliga falhas injetadas (RF-16).
"""

from __future__ import annotations

from fastapi import APIRouter
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


def register(router_: APIRouter) -> None:
    raise NotImplementedError
