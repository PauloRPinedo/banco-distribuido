"""ManejadorDeErrores — traduce una excepción de dominio a un código HTTP y
un cuerpo JSON, en un solo sitio (mismo principio que
`servidor_http.py._responder_erro` de Prototipo 1: cada `ErroDoBanco` ya
carga su propio `codigo` y `estado_http`, no hay que enumerarlos aquí).
"""

from fastapi import HTTPException

from banco.dominio.erros import ErroDoBanco
from banco.servicio.autenticacion import CredencialesInvalidas


def traducir(error: Exception) -> HTTPException:
    if isinstance(error, HTTPException):
        # ya viene traducido (ej. banco.api.seguridad) — no lo reescribas a 500
        return error
    if isinstance(error, ErroDoBanco):
        return HTTPException(status_code=error.estado_http, detail=error.para_json())
    if isinstance(error, ValueError):
        return HTTPException(status_code=404, detail={"erro": "no_encontrado", "mensagem": str(error)})
    if isinstance(error, CredencialesInvalidas):
        return HTTPException(status_code=401, detail={"erro": "credenciales_invalidas", "mensagem": str(error)})
    if isinstance(error, RuntimeError) and str(error) == "sin_quorum":
        return HTTPException(status_code=503, detail={"erro": "sin_quorum",
                                                        "mensagem": "reintentar con el mismo op_id"})
    if isinstance(error, NotImplementedError):
        return HTTPException(status_code=501, detail={"erro": "no_implementado", "mensagem": str(error)})
    return HTTPException(status_code=500, detail={"erro": "error_interno", "mensagem": str(error)})
