"""A transferência.

Uma rota só. A conversão de moeda, a autotransferência e a transferência para
sistemas externos são do projeto final, e é lá que estão.
"""

from fastapi import APIRouter, Depends

from banco.api.dependencias import obter_servico_de_escrita
from banco.api.pedidos import PedidoDeTransferencia, em_centavos, validar_op_id
from banco.api.respostas import de_escrita
from banco.dominio.contas import validar_id
from banco.dominio.operacoes import Transferencia

router = APIRouter()


@router.post("/transferencias")
def transferir(pedido: PedidoDeTransferencia,
               servico=Depends(obter_servico_de_escrita)) -> dict:
    """RF-04 e RF-05: ou as duas contas mudam, ou nenhuma muda."""
    operacao = Transferencia(validar_id(pedido.de), validar_id(pedido.para),
                             em_centavos(pedido.valor))
    return de_escrita(servico.aplicar(operacao, validar_op_id(pedido.op_id)))
