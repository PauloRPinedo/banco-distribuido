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

from fastapi import APIRouter

router = APIRouter(prefix="/internal", tags=["interno"])


def register(router_: APIRouter) -> None:
    """Registra os handlers, delegando a ``ReplicaApplier`` e ``ElectionManager``."""
    raise NotImplementedError
