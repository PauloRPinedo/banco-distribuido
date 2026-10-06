"""As transferências: na mesma moeda, entre moedas, entre contas próprias e
para outro banco.

Todas exigem sessão e que quem pede seja o dono da conta de origem; a de
destino pode ser de qualquer pessoa, exceto na autotransferência.
"""

import time

from fastapi import APIRouter, Depends

from banco.api.dependencias import (obter_gateway, obter_servico_de_consultas,
                                    obter_servico_de_escrita, servico_de_escrita)
from banco.api.pedidos import (PedidoDeTransferencia,
                               PedidoDeTransferenciaExterna, em_centavos,
                               validar_op_id)
from banco.api.respostas import de_escrita
from banco.api.seguranca import usuario_autenticado
from banco.dominio.contas import validar_id
from banco.dominio.operacoes import (Cambio, DesfechoExterno, Transferencia,
                                     TransferenciaExterna)
from banco.servico.erros import SistemaExternoInexistente, TaxaIndisponivel

router = APIRouter()


def _cambio(consultas, de: str, para: str, valor_centavos: int) -> Cambio:
    """Um câmbio com a taxa em vigor agora, lida antes de entrar no domínio.

    A taxa fica dentro da operação: se o pedido for repetido com o mesmo op_id,
    devolve-se o resultado guardado, com a taxa de então, e não se volta a ler.
    """
    moeda_de = consultas.saldo(de).moeda
    moeda_para = consultas.saldo(para).moeda
    taxa = consultas.taxa(moeda_de, moeda_para, time.time())
    if taxa is None:
        raise TaxaIndisponivel(f"não há taxa de {moeda_de} para {moeda_para}")
    return Cambio(de, para, valor_centavos, taxa)


@router.post("/transferencias")
def transferir(pedido: PedidoDeTransferencia,
               usuario_id: str = Depends(usuario_autenticado),
               servico=Depends(obter_servico_de_escrita)) -> dict:
    """RF-04 e RF-05: ou as duas contas mudam, ou nenhuma muda."""
    operacao = Transferencia(validar_id(pedido.de), validar_id(pedido.para),
                             em_centavos(pedido.valor))
    return de_escrita(servico.aplicar(operacao, validar_op_id(pedido.op_id),
                                      usuario_id, exige_dono=(pedido.de,)))


@router.post("/transferencias/conversao")
def transferir_com_conversao(pedido: PedidoDeTransferencia,
                             usuario_id: str = Depends(usuario_autenticado),
                             consultas=Depends(obter_servico_de_consultas),
                             servico=Depends(obter_servico_de_escrita)) -> dict:
    """RF-20: de uma moeda para outra, à taxa em vigor (CU-05)."""
    operacao = _cambio(consultas, validar_id(pedido.de), validar_id(pedido.para),
                       em_centavos(pedido.valor))
    return de_escrita(servico.aplicar(operacao, validar_op_id(pedido.op_id),
                                      usuario_id, exige_dono=(pedido.de,)))


@router.post("/transferencias/autotransferencia")
def autotransferir(pedido: PedidoDeTransferencia,
                   usuario_id: str = Depends(usuario_autenticado),
                   consultas=Depends(obter_servico_de_consultas),
                   servico=Depends(obter_servico_de_escrita)) -> dict:
    """CU-06: entre duas contas do mesmo dono, com câmbio se as moedas diferem."""
    de, para = validar_id(pedido.de), validar_id(pedido.para)
    valor_centavos = em_centavos(pedido.valor)
    if consultas.saldo(de).moeda == consultas.saldo(para).moeda:
        operacao = Transferencia(de, para, valor_centavos)
    else:
        operacao = _cambio(consultas, de, para, valor_centavos)
    return de_escrita(servico.aplicar(operacao, validar_op_id(pedido.op_id),
                                      usuario_id, exige_dono=(de, para)))


@router.post("/transferencias/externa")
def transferir_para_fora(pedido: PedidoDeTransferenciaExterna,
                         usuario_id: str = Depends(usuario_autenticado),
                         consultas=Depends(obter_servico_de_consultas),
                         gateway=Depends(obter_gateway)) -> dict:
    """RF-25, em dois passos, cada um na sua transação.

    1. Debitar e confirmar o débito (`TransferenciaExterna`). O dinheiro sai já
       do banco; não se seguram locks enquanto se espera pelo outro banco.
    2. Perguntar ao outro banco, e gravar a resposta (`DesfechoExterno`):
       confirmada, fica assim; rejeitada, o valor volta à conta (RN-14).

    O desfecho tem op_id próprio, `<op_id>-desfecho`. Repetir o pedido depois
    de uma queda entre os dois passos encontra o débito já feito e, se o
    desfecho também já estiver gravado, devolve-o sem voltar a perguntar —
    assim nunca se devolve dinheiro que o outro banco já aceitou.
    """
    op_id = validar_op_id(pedido.op_id)
    de = validar_id(pedido.de)
    valor_centavos = em_centavos(pedido.valor)
    if not consultas.sistema_ativo(pedido.sistema_externo_id):
        raise SistemaExternoInexistente(
            f"sistema externo desconhecido: {pedido.sistema_externo_id!r}")

    with servico_de_escrita() as servico:
        servico.aplicar(TransferenciaExterna(de, pedido.sistema_externo_id,
                                             valor_centavos),
                        op_id, usuario_id, exige_dono=(de,))

    id_do_desfecho = f"{op_id}-desfecho"
    with servico_de_escrita() as servico:
        guardado = servico.ja_aplicada(id_do_desfecho)
    if guardado is not None:
        return de_escrita(guardado)

    decisao = gateway.confirmar(pedido.sistema_externo_id, valor_centavos, op_id)

    with servico_de_escrita() as servico:
        resposta = servico.aplicar(
            DesfechoExterno(de, valor_centavos, decisao["confirmada"],
                            decisao["referencia_externa"], op_id),
            id_do_desfecho)
    return de_escrita(resposta)
