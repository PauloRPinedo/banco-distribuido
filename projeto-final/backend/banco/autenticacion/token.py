"""Token de sesión firmado con llave simétrica — RN-16.

La llave (`SECRET_KEY`) es la misma en los 3 nodos (mismo valor de entorno,
igual que `config/cluster.json` es igual en todos) — por eso cualquier nodo
valida un token emitido por otro, sin llamarlo. No es JWT completo (sin
cabecera ni librería externa) — mismo principio de "sin dependencia nueva"
que ya usa `dinheiro.py`.
"""

import base64
import hashlib
import hmac
import json
import os
import time

_SEGUNDOS_DE_VIDA = 8 * 60 * 60  # 8 horas


def _llave() -> bytes:
    llave = os.environ.get("SECRET_KEY")
    if not llave:
        raise RuntimeError(
            "SECRET_KEY no configurada — debe ser igual en todos los nodos")
    return llave.encode("utf-8")


def _codificar(payload: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def _decodificar(texto: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(texto.encode("ascii")))


def emitir_token(usuario_id: str) -> str:
    payload = {"usuario_id": usuario_id, "expira": int(time.time()) + _SEGUNDOS_DE_VIDA}
    cuerpo = _codificar(payload)
    firma = hmac.new(_llave(), cuerpo.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{cuerpo}.{firma}"


def validar_token(token: str) -> str | None:
    """Devuelve el usuario_id si el token es válido y no expiró, si no None."""
    try:
        cuerpo, firma = token.split(".")
    except ValueError:
        return None

    firma_esperada = hmac.new(_llave(), cuerpo.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(firma, firma_esperada):
        return None

    payload = _decodificar(cuerpo)
    if payload["expira"] < int(time.time()):
        return None
    return payload["usuario_id"]
