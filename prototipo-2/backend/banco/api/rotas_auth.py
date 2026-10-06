"""Registo e início de sessão — RF-26, CU-17."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from banco.api.dependencias import obter_servico_de_autenticacao

router = APIRouter(prefix="/auth")


class PedidoDeRegisto(BaseModel):
    nome: str
    email: str
    senha: str


class PedidoDeLogin(BaseModel):
    email: str
    senha: str


@router.post("/registo")
def registar(pedido: PedidoDeRegisto,
             servico=Depends(obter_servico_de_autenticacao)) -> dict:
    return servico.registar_usuario(pedido.nome, pedido.email, pedido.senha)


@router.post("/login")
def iniciar_sessao(pedido: PedidoDeLogin,
                   servico=Depends(obter_servico_de_autenticacao)) -> dict:
    return {"token": servico.iniciar_sessao(pedido.email, pedido.senha)}
