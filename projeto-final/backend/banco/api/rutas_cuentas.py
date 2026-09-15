"""CuentaController — ver diagrama-de-clases-interfaz.md.

Exige sesión exactamente donde ya lo dice
docs/entregables/02-casos-de-uso/acciones-del-sistema.md (columna "requiere
autenticación de dueño"): crear cuenta y depositar, no; consultar saldo,
retirar y extracto, sí — y además, dueño de esa cuenta puntual.
"""

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from banco.api.dependencias import obtener_servicio_cuentas
from banco.api.errores import traducir
from banco.api.seguridad import exigir_dueno, usuario_autenticado

router = APIRouter(prefix="/cuentas", tags=["cuentas"])


class CrearCuentaRequest(BaseModel):
    usuario_id: str
    moneda: str
    saldo_inicial_centavos: int = 0


class MontoRequest(BaseModel):
    monto_centavos: int


@router.post("")
def crear_cuenta(req: CrearCuentaRequest, x_op_id: str = Header(...),
                  servicio=Depends(obtener_servicio_cuentas)):
    try:
        return servicio.crear_cuenta(req.usuario_id, req.moneda,
                                      req.saldo_inicial_centavos, x_op_id)
    except Exception as error:
        raise traducir(error)


@router.get("/{cuenta_id}")
def consultar_saldo(cuenta_id: str, usuario_id: str = Depends(usuario_autenticado),
                     servicio=Depends(obtener_servicio_cuentas)):
    try:
        cuenta = servicio.consultar_saldo(cuenta_id)
        exigir_dueno(cuenta, usuario_id)
        return cuenta
    except Exception as error:
        raise traducir(error)


@router.post("/{cuenta_id}/deposito")
def depositar(cuenta_id: str, req: MontoRequest, x_op_id: str = Header(...),
               servicio=Depends(obtener_servicio_cuentas)):
    try:
        return servicio.depositar(cuenta_id, req.monto_centavos, x_op_id)
    except Exception as error:
        raise traducir(error)


@router.post("/{cuenta_id}/retiro")
def retirar(cuenta_id: str, req: MontoRequest, x_op_id: str = Header(...),
             usuario_id: str = Depends(usuario_autenticado),
             servicio=Depends(obtener_servicio_cuentas)):
    try:
        exigir_dueno(servicio.consultar_saldo(cuenta_id), usuario_id)
        return servicio.retirar(cuenta_id, req.monto_centavos, x_op_id)
    except Exception as error:
        raise traducir(error)


@router.get("/{cuenta_id}/extracto")
def consultar_extracto(cuenta_id: str, usuario_id: str = Depends(usuario_autenticado),
                        servicio=Depends(obtener_servicio_cuentas)):
    try:
        exigir_dueno(servicio.consultar_saldo(cuenta_id), usuario_id)
        return servicio.consultar_extracto(cuenta_id)
    except Exception as error:
        raise traducir(error)
