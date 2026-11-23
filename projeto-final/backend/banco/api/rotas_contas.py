"""As rotas de uma conta.

As rotas não têm `try/except`: os erros sobem e são traduzidos pelos tratadores
registados em `app.py`. O que fica aqui é só o que é desta camada — ler o
corpo, converter o dinheiro na fronteira, saber quem pede, e chamar o serviço.

Quem exige sessão: abrir, listar, consultar, sacar e extrato. O depósito fica
aberto — qualquer pessoa pode pôr dinheiro numa conta alheia, como num balcão.
"""

from fastapi import APIRouter, Depends

from banco.api.dependencias import (obter_servico_de_consultas,
                                    obter_servico_de_escrita)
from banco.api.pedidos import (PedidoDeCriacao, PedidoDeValor, em_centavos,
                               em_milionesimos, validar_op_id)
from banco.api.respostas import de_conta, de_escrita, de_movimento
from banco.api.seguranca import exigir_dono, usuario_autenticado, usuario_opcional
from banco.dominio import numero_conta
from banco.dominio.contas import validar_id
from banco.dominio.erros import NumeroOcupado
from banco.dominio.operacoes import CriarConta, Deposito, Saque

router = APIRouter()


_TENTATIVAS_DE_NUMERO = 5


def _sortear_numero_livre(consultas) -> str:
    """Um número que ninguém tem agora. O serviço volta a verificar dentro do
    lock de escrita; isto só evita um 409 no caso normal."""
    for _ in range(_TENTATIVAS_DE_NUMERO):
        numero = numero_conta.sortear()
        if consultas.numero_livre(numero):
            return numero
    raise NumeroOcupado("não foi possível sortear um número livre; tente de novo")


@router.post("/contas")
def criar_conta(pedido: PedidoDeCriacao,
                usuario_id: str = Depends(usuario_autenticado),
                consultas=Depends(obter_servico_de_consultas),
                servico=Depends(obter_servico_de_escrita)) -> dict:
    """RF-01, RF-19 e RF-23/24. O dono vem do token, nunca do corpo; o número
    decide-o este nó (o primário) e viaja na entrada do log."""
    numero = _sortear_numero_livre(consultas)
    identificador = pedido.conta or f"conta-{numero}"
    operacao = CriarConta(validar_id(identificador),
                          em_centavos(pedido.saldo_inicial), dono=usuario_id,
                          moeda=pedido.moeda, produto=pedido.produto,
                          taxa_juros_milionesimos=em_milionesimos(pedido.taxa_juros),
                          prazo_dias=pedido.prazo_dias, numero=numero)
    return de_escrita(servico.aplicar(operacao, validar_op_id(pedido.op_id)))


@router.get("/contas")
def listar_contas(usuario_id: str = Depends(usuario_autenticado),
                  servico=Depends(obter_servico_de_consultas)) -> dict:
    """As contas de quem pede — é o que o painel mostra depois do login."""
    return {"contas": [de_conta(conta)
                       for conta in servico.contas_do_dono(usuario_id)]}


@router.get("/contas/por-numero/{numero}")
def procurar_por_numero(numero: str,
                        _usuario_id: str = Depends(usuario_autenticado),
                        consultas=Depends(obter_servico_de_consultas)) -> dict:
    """Quem é o titular de `0001 / 12345678-9`, antes de lhe transferir.

    Pede sessão, e devolve só o nome e a moeda: nunca o saldo nem o email.
    """
    encontrada = consultas.conta_por_numero(numero)
    return {"conta": encontrada["id"], "agencia": encontrada["agencia"],
            "numero": encontrada["numero"], "moeda": encontrada["moeda"],
            "titular": encontrada["titular"]}


@router.get("/contas/{identificador}")
def consultar_saldo(identificador: str,
                    usuario_id: str = Depends(usuario_autenticado),
                    servico=Depends(obter_servico_de_consultas)) -> dict:
    """RF-02."""
    conta = servico.saldo(identificador)
    exigir_dono(conta.dono, usuario_id, identificador)
    return de_conta(conta)


@router.post("/contas/{identificador}/deposito")
def depositar(identificador: str, pedido: PedidoDeValor,
              usuario_id: str | None = Depends(usuario_opcional),
              consultas=Depends(obter_servico_de_consultas),
              servico=Depends(obter_servico_de_escrita)) -> dict:
    """RF-03. Aberto a todos, como um balcão; mas o saldo que fica só o vê o
    dono. Sem isto, depositar 0,01 numa conta qualquer dava a conhecer o saldo."""
    operacao = Deposito(validar_id(identificador), em_centavos(pedido.valor))
    resposta = de_escrita(servico.aplicar(operacao, validar_op_id(pedido.op_id)))
    if consultas.saldo(identificador).dono != usuario_id:
        resposta = {chave: valor for chave, valor in resposta.items()
                    if chave not in ("saldo", "saldo_centavos")}
    return resposta


@router.post("/contas/{identificador}/saque")
def sacar(identificador: str, pedido: PedidoDeValor,
          usuario_id: str = Depends(usuario_autenticado),
          servico=Depends(obter_servico_de_escrita)) -> dict:
    """RF-03, e RF-06 quando o saldo não chega."""
    operacao = Saque(validar_id(identificador), em_centavos(pedido.valor))
    return de_escrita(servico.aplicar(operacao, validar_op_id(pedido.op_id),
                                      usuario_id, exige_dono=(identificador,)))


@router.get("/contas/{identificador}/extrato")
def consultar_extrato(identificador: str,
                      usuario_id: str = Depends(usuario_autenticado),
                      servico=Depends(obter_servico_de_consultas)) -> dict:
    """F-05."""
    conta = servico.saldo(identificador)
    exigir_dono(conta.dono, usuario_id, identificador)
    movimentos = servico.extrato(identificador)
    return {"conta": identificador, "moeda": conta.moeda,
            "movimentos": [de_movimento(movimento, conta.moeda)
                           for movimento in movimentos]}
