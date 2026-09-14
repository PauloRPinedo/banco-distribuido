"""TransferenciaController — ver diagrama-de-clases-interfaz.md.

Las tres exigen sesión y dueño de la cuenta origen (mismo criterio que
docs/entregables/02-casos-de-uso/acciones-del-sistema.md).

`/transferencias/conversion` y `/transferencias/externa` están declaradas
(para que el contrato HTTP ya exista) pero devuelven 501 — ver
banco/dominio/PENDIENTE.md.
"""

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from banco.api.dependencias import obtener_servicio_cuentas, obtener_servicio_transferencias
from banco.api.errores import traducir
from banco.api.seguridad import exigir_dueno, usuario_autenticado

router = APIRouter(prefix="/transferencias", tags=["transferencias"])


class TransferenciaRequest(BaseModel):
    cuenta_origen_id: str
    cuenta_destino_id: str
    monto_centavos: int


@router.post("")
def transferir(req: TransferenciaRequest, x_op_id: str = Header(...),
                usuario_id: str = Depends(usuario_autenticado),
                servicio=Depends(obtener_servicio_transferencias),
                servicio_cuentas=Depends(obtener_servicio_cuentas)):
    try:
        exigir_dueno(servicio_cuentas.consultar_saldo(req.cuenta_origen_id), usuario_id)
        return servicio.transferir(req.cuenta_origen_id, req.cuenta_destino_id,
                                    req.monto_centavos, x_op_id)
    except Exception as error:
        raise traducir(error)


@router.post("/conversion")
def transferir_con_conversion(req: TransferenciaRequest, x_op_id: str = Header(...),
                                usuario_id: str = Depends(usuario_autenticado),
                                servicio=Depends(obtener_servicio_transferencias),
                                servicio_cuentas=Depends(obtener_servicio_cuentas)):
    try:
        exigir_dueno(servicio_cuentas.consultar_saldo(req.cuenta_origen_id), usuario_id)
        return servicio.transferir_con_conversion(req.cuenta_origen_id, req.cuenta_destino_id,
                                                    req.monto_centavos, x_op_id)
    except Exception as error:
        raise traducir(error)


@router.post("/autotransferencia")
def autotransferir(req: TransferenciaRequest, x_op_id: str = Header(...),
                     usuario_id: str = Depends(usuario_autenticado),
                     servicio=Depends(obtener_servicio_transferencias),
                     servicio_cuentas=Depends(obtener_servicio_cuentas)):
    try:
        exigir_dueno(servicio_cuentas.consultar_saldo(req.cuenta_origen_id), usuario_id)
        return servicio.autotransferir(req.cuenta_origen_id, req.cuenta_destino_id,
                                        req.monto_centavos, x_op_id)
    except Exception as error:
        raise traducir(error)
