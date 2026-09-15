"""A auditoria do total em circulação (SPECS 6.1)."""

from fastapi import APIRouter, Depends

from banco.api.dependencias import obter_servico_de_consultas
from banco.api.respostas import de_auditoria

router = APIRouter()


@router.get("/auditoria")
def auditar(servico=Depends(obter_servico_de_consultas)) -> dict:
    """RF-14. `divergencia_centavos` diferente de zero é dinheiro perdido."""
    return de_auditoria(servico.auditoria())
