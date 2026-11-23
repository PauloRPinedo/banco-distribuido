"""A auditoria do total em circulação.

Exige sessão: não mostra contas, mas mostra quanto dinheiro há no banco em cada
moeda, e isso não é para quem passa na rua.
"""

from fastapi import APIRouter, Depends

from banco.api.dependencias import obter_servico_de_consultas
from banco.api.respostas import de_auditoria
from banco.api.seguranca import usuario_autenticado

router = APIRouter()


@router.get("/auditoria", dependencies=[Depends(usuario_autenticado)])
def auditar(servico=Depends(obter_servico_de_consultas)) -> dict:
    """RF-14. `divergencia_centavos` diferente de zero é dinheiro perdido."""
    return de_auditoria(servico.auditoria())
