"""API do cliente do banco.

Rotas:

===================================  ======  ==============================
Rota                                 Metodo  Requisito
===================================  ======  ==============================
``/accounts``                        POST    RF-01 criar conta
``/accounts/{id}``                   GET     RF-02 consultar saldo
``/accounts/{id}/deposit``           POST    RF-03 deposito
``/accounts/{id}/withdraw``          POST    RF-03 saque
``/transfers``                       POST    RF-04, RF-05 transferencia
``/accounts/{id}/statement``         GET     RF-05 extrato
``/audit``                           GET     RF-14 total em circulacao
===================================  ======  ==============================

Toda escrita exige ``op_id`` no corpo -- um UUID gerado pelo cliente e mantido
entre retentativas. Sem ele nao ha como distinguir "repetir porque o primario
caiu" de "transferir de novo", e a historia de usuario 4 nao teria resposta correta.

Escritas so sao aceitas pelo primario. Uma replica responde 409 com
``{"error": "not_primary", "primary_hint": "http://host:port"}``.

Leituras sao servidas pelo primario por padrao. Uma replica aceita leitura apenas
com ``?stale=true`` explicito, e a resposta traz ``stale: true`` e o
``applied_idx`` para o cliente saber o quanto o dado pode estar atrasado.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["cliente"])


class CreateAccountRequest(BaseModel):
    """Corpo de ``POST /accounts`` (RF-01)."""

    op_id: str = Field(..., description="UUID de idempotencia gerado pelo cliente")
    account_id: str
    initial_balance_cents: int = Field(0, ge=0)


class AmountRequest(BaseModel):
    """Corpo de deposito e saque (RF-03)."""

    op_id: str
    amount_cents: int = Field(..., gt=0, description="Quantia em centavos, sempre positiva")


class TransferRequest(BaseModel):
    """Corpo de ``POST /transfers`` (RF-04, RF-05)."""

    op_id: str
    from_account: str
    to_account: str
    amount_cents: int = Field(..., gt=0)


class BalanceResponse(BaseModel):
    """Saldo de uma conta, com o indice em que foi lido."""

    account_id: str
    balance_cents: int
    applied_idx: int
    stale: bool = False


class OperationResponse(BaseModel):
    """Resultado de uma escrita confirmada."""

    op_id: str
    applied_idx: int
    balances: dict[str, int]


class AuditResponse(BaseModel):
    """Auditoria do dinheiro em circulacao (RF-14).

    Comparada entre os tres nos nos testes: com o mesmo ``applied_idx``,
    ``total_cents`` tem de ser identico em todos.
    """

    total_cents: int
    account_count: int
    applied_idx: int
    node_id: str
    epoch: int


def register(router_: APIRouter) -> None:
    """Registra os handlers. A implementacao vive na fase 2 do plano."""
    raise NotImplementedError
