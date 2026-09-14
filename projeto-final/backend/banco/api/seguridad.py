"""Dependencia de FastAPI para exigir sesión — RF-26, RN-16.

Separado de `autenticacion/` a propósito: ese módulo solo sabe de hash y
firma, no conoce HTTP; este sí conoce el encabezado `Authorization`, es la
frontera entre los dos (mismo principio de capas que ya usa `errores.py`).
"""

from fastapi import Header, HTTPException

from banco.autenticacion import validar_token


def usuario_autenticado(authorization: str | None = Header(default=None)) -> str:
    """Devuelve el `usuario_id` del token, o rechaza con 401.

    Cualquier nodo valida el token con la llave simétrica compartida — no
    hace ninguna llamada de red ni a la base de datos (ver RN-16).
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"erro": "sin_sesion",
                    "mensagem": "falta el encabezado Authorization: Bearer <token>"})

    token = authorization.removeprefix("Bearer ").strip()
    usuario_id = validar_token(token)
    if usuario_id is None:
        raise HTTPException(
            status_code=401,
            detail={"erro": "sesion_invalida", "mensagem": "token inválido o expirado"})
    return usuario_id


def exigir_dueno(cuenta: dict, usuario_id: str) -> None:
    """RN: una acción sobre una cuenta que exige dueño solo la puede hacer
    el usuario autenticado que es dueño de esa cuenta (ver la columna
    "requiere autenticación de dueño" en
    docs/entregables/02-casos-de-uso/acciones-del-sistema.md).
    """
    if cuenta["usuario_id"] != usuario_id:
        raise HTTPException(
            status_code=403,
            detail={"erro": "prohibido", "mensagem": "esta cuenta no te pertenece"})
