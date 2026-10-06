"""Hash da senha — RN-15.

Nunca reversível: PBKDF2-HMAC-SHA256 com sal, da biblioteca padrão
(`hashlib`, sem dependência nova). Não é cifra, é um hash de sentido único —
não existe uma função "decifrar_senha".
"""

import hashlib
import hmac
import os

_ALGORITMO = "pbkdf2_sha256"
_ITERACOES = 260_000


def calcular_hash(senha: str) -> str:
    sal = os.urandom(16)
    derivado = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, _ITERACOES)
    return f"{_ALGORITMO}${_ITERACOES}${sal.hex()}${derivado.hex()}"


def verificar_senha(senha: str, hash_senha: str) -> bool:
    try:
        algoritmo, iteracoes, sal_hex, derivado_hex = hash_senha.split("$")
        if algoritmo != _ALGORITMO:
            return False
        sal = bytes.fromhex(sal_hex)
        esperado = bytes.fromhex(derivado_hex)
    except ValueError:
        return False

    calculado = hashlib.pbkdf2_hmac(
        "sha256", senha.encode("utf-8"), sal, int(iteracoes))
    # comparação em tempo constante — evita revelar, pelo tempo de resposta,
    # quanto do hash coincide
    return hmac.compare_digest(calculado, esperado)
