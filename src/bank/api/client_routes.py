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

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from ..domain.errors import NotPrimary
from ..domain.operations import Operation, OperationResult, OpType

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


def _ctx(request: Request):
    return request.app.state.ctx


def _write(request: Request, operation: Operation) -> OperationResponse:
    """Caminho comum de toda escrita: exige primario e quorum, depois submete."""
    ctx = _ctx(request)
    ctx.logger.event("op_received", op_id=operation.op_id, type=operation.type.value)
    ctx.primary.ensure_writable()
    result: OperationResult = ctx.primary.submit(operation)
    ctx.maybe_snapshot()
    return OperationResponse(
        op_id=result.op_id, applied_idx=result.applied_idx, balances=result.balances
    )


def _read_guard(request: Request, stale: bool) -> bool:
    """Leituras vao ao primario, salvo ``?stale=true`` explicito.

    Devolve ``True`` se a resposta pode estar atrasada.
    """
    ctx = _ctx(request)
    if ctx.node_state.is_primary():
        return False
    if not stale:
        raise NotPrimary(ctx.primary_hint())
    return True


@router.post("/accounts", response_model=OperationResponse)
def create_account(request: Request, body: CreateAccountRequest) -> OperationResponse:
    """RF-01: cria uma conta com saldo inicial."""
    return _write(
        request,
        Operation(
            op_id=body.op_id,
            type=OpType.CREATE_ACCOUNT,
            account_id=body.account_id,
            amount_cents=body.initial_balance_cents,
        ),
    )


@router.get("/accounts/{account_id}", response_model=BalanceResponse)
def get_balance(
    request: Request, account_id: str, stale: bool = Query(False)
) -> BalanceResponse:
    """RF-02: consulta o saldo."""
    ctx = _ctx(request)
    is_stale = _read_guard(request, stale)
    with ctx.store_lock:
        return BalanceResponse(
            account_id=account_id,
            balance_cents=ctx.store.get_balance(account_id),
            applied_idx=ctx.store.last_applied_idx,
            stale=is_stale,
        )


@router.post("/accounts/{account_id}/deposit", response_model=OperationResponse)
def deposit(request: Request, account_id: str, body: AmountRequest) -> OperationResponse:
    """RF-03: deposito."""
    return _write(
        request,
        Operation(
            op_id=body.op_id,
            type=OpType.DEPOSIT,
            account_id=account_id,
            amount_cents=body.amount_cents,
        ),
    )


@router.post("/accounts/{account_id}/withdraw", response_model=OperationResponse)
def withdraw(request: Request, account_id: str, body: AmountRequest) -> OperationResponse:
    """RF-03: saque. Rejeitado se deixaria o saldo negativo (RF-06)."""
    return _write(
        request,
        Operation(
            op_id=body.op_id,
            type=OpType.WITHDRAW,
            account_id=account_id,
            amount_cents=body.amount_cents,
        ),
    )


@router.post("/transfers", response_model=OperationResponse)
def transfer(request: Request, body: TransferRequest) -> OperationResponse:
    """RF-04 e RF-05: transferencia atomica entre contas."""
    return _write(
        request,
        Operation(
            op_id=body.op_id,
            type=OpType.TRANSFER,
            from_account=body.from_account,
            to_account=body.to_account,
            amount_cents=body.amount_cents,
        ),
    )


@router.get("/accounts/{account_id}/statement")
def statement(
    request: Request,
    account_id: str,
    limit: int = Query(50, ge=1, le=500),
    stale: bool = Query(False),
) -> dict:
    """RF-05: extrato das operacoes que tocaram a conta."""
    ctx = _ctx(request)
    is_stale = _read_guard(request, stale)
    with ctx.store_lock:
        entries = ctx.store.statement(account_id, limit=limit)
        return {
            "account_id": account_id,
            "balance_cents": ctx.store.get_balance(account_id),
            "applied_idx": ctx.store.last_applied_idx,
            "stale": is_stale,
            "entries": [e.to_json() for e in entries],
        }


@router.get("/audit", response_model=AuditResponse)
def audit(request: Request, stale: bool = Query(True)) -> AuditResponse:
    """RF-14: total de dinheiro em circulacao.

    Aceita leitura em replica por padrao, porque o uso principal e justamente
    comparar o total entre os tres nos.
    """
    ctx = _ctx(request)
    _read_guard(request, stale)
    # Sob o lock: a soma tem de ser tirada de um estado inteiro, nunca de uma
    # transferencia pela metade -- e exatamente esta soma que os testes comparam.
    with ctx.store_lock:
        return AuditResponse(
            total_cents=ctx.store.total_cents(),
            account_count=len(ctx.store.accounts),
            applied_idx=ctx.store.last_applied_idx,
            node_id=ctx.config.self_id,
            epoch=ctx.node_state.epoch,
        )
