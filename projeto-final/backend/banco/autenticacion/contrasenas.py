"""Hash de contraseña — RN-15.

Nunca reversible: PBKDF2-HMAC-SHA256 con sal, de la librería estándar
(`hashlib`, sin dependencia nueva). No es cifrado, es un hash de un solo
sentido — no existe una función "descifrar_contrasena".
"""

import hashlib
import hmac
import os

_ALGORITMO = "pbkdf2_sha256"
_ITERACIONES = 260_000


def calcular_hash(contrasena: str) -> str:
    sal = os.urandom(16)
    derivado = hashlib.pbkdf2_hmac("sha256", contrasena.encode("utf-8"), sal, _ITERACIONES)
    return f"{_ALGORITMO}${_ITERACIONES}${sal.hex()}${derivado.hex()}"


def verificar_contrasena(contrasena: str, password_hash: str) -> bool:
    try:
        algoritmo, iteraciones, sal_hex, derivado_hex = password_hash.split("$")
        if algoritmo != _ALGORITMO:
            return False
        sal = bytes.fromhex(sal_hex)
        esperado = bytes.fromhex(derivado_hex)
    except ValueError:
        return False

    calculado = hashlib.pbkdf2_hmac(
        "sha256", contrasena.encode("utf-8"), sal, int(iteraciones))
    # comparación en tiempo constante — evita filtrar por temporización
    # cuánto del hash coincide
    return hmac.compare_digest(calculado, esperado)
