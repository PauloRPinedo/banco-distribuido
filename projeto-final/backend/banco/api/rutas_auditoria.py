"""AuditoriaController — RF-14."""

from fastapi import APIRouter, Depends

from banco.api.dependencias import obtener_servicio_auditoria

router = APIRouter(tags=["auditoria"])


@router.get("/auditoria")
def auditar(servicio=Depends(obtener_servicio_auditoria)):
    return servicio.auditar()
