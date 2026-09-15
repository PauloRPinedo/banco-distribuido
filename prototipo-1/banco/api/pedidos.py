"""Os corpos que as rotas aceitam.

É aqui que o texto vira centavos, uma vez só, na fronteira. Daqui
para dentro só circulam inteiros.

Os campos chamam-se `valor` e `saldo_inicial`, sem unidade, porque é assim que
estão fixados no cabo. A regra de escrever sempre `valor_centavos` vale a
partir de `para_centavos()` para dentro.
"""

import re
from typing import Any

from pydantic import BaseModel

from banco.dominio.dinheiro import para_centavos
from banco.dominio.erros import ValorInvalido

# Um op_id como "3f1c8a2e" é válido e não é um UUID. Exigir um UUID seria
# apertar mais do que o necessário e rejeitar clientes válidos.
_OP_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def validar_op_id(op_id: Any) -> str:
    """Recusa um op_id mal formado antes de ele chegar à base.

    Sem isto, o driver rebenta contra a coluna e o cliente recebe um 500 opaco
    em vez de saber o que escreveu de errado.
    """
    if not isinstance(op_id, str) or not _OP_ID.match(op_id):
        raise ValorInvalido(
            f"op_id inválido: {op_id!r} (8 a 64 caracteres de A-Z, a-z, 0-9, _ ou -)")
    return op_id


def em_centavos(valor: Any) -> int:
    """O valor do corpo, em centavos. Recusa números, de propósito."""
    return para_centavos(valor)


class PedidoDeCriacao(BaseModel):
    conta: str
    op_id: str
    saldo_inicial: Any = "0"


class PedidoDeValor(BaseModel):
    valor: Any
    op_id: str


class PedidoDeTransferencia(BaseModel):
    de: str
    para: str
    valor: Any
    op_id: str
