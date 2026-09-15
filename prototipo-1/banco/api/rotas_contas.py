"""As rotas de uma conta.

As rotas não têm `try/except`: os erros do domínio sobem e são traduzidos pelos
tratadores registados em `app.py`. O que fica aqui é só o que é mesmo desta
camada — ler o corpo, converter o dinheiro na fronteira, e chamar o serviço.
"""

from fastapi import APIRouter, Depends

from banco.api.dependencias import (obter_servico_de_consultas,
                                    obter_servico_de_escrita)
from banco.api.pedidos import (PedidoDeCriacao, PedidoDeValor, em_centavos,
                               validar_op_id)
from banco.api.respostas import de_conta, de_escrita, de_movimento
from banco.dominio.contas import validar_id
from banco.dominio.operacoes import CriarConta, Deposito, Saque

router = APIRouter()


@router.post("/contas")
def criar_conta(pedido: PedidoDeCriacao,
                servico=Depends(obter_servico_de_escrita)) -> dict:
    """RF-01. O id vem do cliente: é ele que escolhe chamar-lhe `alice`."""
    operacao = CriarConta(validar_id(pedido.conta),
                          em_centavos(pedido.saldo_inicial))
    return de_escrita(servico.aplicar(operacao, validar_op_id(pedido.op_id)))


@router.get("/contas/{identificador}")
def consultar_saldo(identificador: str,
                    servico=Depends(obter_servico_de_consultas)) -> dict:
    """RF-02."""
    return de_conta(servico.saldo(identificador))


@router.post("/contas/{identificador}/deposito")
def depositar(identificador: str, pedido: PedidoDeValor,
              servico=Depends(obter_servico_de_escrita)) -> dict:
    """RF-03."""
    operacao = Deposito(validar_id(identificador), em_centavos(pedido.valor))
    return de_escrita(servico.aplicar(operacao, validar_op_id(pedido.op_id)))


@router.post("/contas/{identificador}/saque")
def sacar(identificador: str, pedido: PedidoDeValor,
          servico=Depends(obter_servico_de_escrita)) -> dict:
    """RF-03, e RF-06 quando o saldo não chega."""
    operacao = Saque(validar_id(identificador), em_centavos(pedido.valor))
    return de_escrita(servico.aplicar(operacao, validar_op_id(pedido.op_id)))


@router.get("/contas/{identificador}/extrato")
def consultar_extrato(identificador: str,
                      servico=Depends(obter_servico_de_consultas)) -> dict:
    """F-05."""
    movimentos = servico.extrato(identificador)
    return {"conta": identificador,
            "movimentos": [de_movimento(movimento) for movimento in movimentos]}
