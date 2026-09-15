"""AuthController — RF-26, CU-17."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from banco.api.dependencias import obtener_servicio_autenticacion
from banco.api.errores import traducir

router = APIRouter(prefix="/auth", tags=["auth"])


class RegistroRequest(BaseModel):
    nombre: str
    email: str
    contrasena: str


class LoginRequest(BaseModel):
    email: str
    contrasena: str


@router.post("/registro")
def registrar(req: RegistroRequest, servicio=Depends(obtener_servicio_autenticacion)):
    try:
        return servicio.registrar_usuario(req.nombre, req.email, req.contrasena)
    except Exception as error:
        raise traducir(error)


@router.post("/login")
def iniciar_sesion(req: LoginRequest, servicio=Depends(obtener_servicio_autenticacion)):
    try:
        token = servicio.iniciar_sesion(req.email, req.contrasena)
        return {"token": token}
    except Exception as error:
        raise traducir(error)
