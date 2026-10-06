"""Token de sessão assinado com chave simétrica — RN-16.

A chave (`SECRET_KEY`) é a mesma nos 3 nós (o mesmo valor de ambiente, tal
como `config/cluster.json` é igual em todos) — por isso qualquer nó valida um
token emitido por outro, sem lhe telefonar. Não é um JWT completo (sem
cabeçalho nem biblioteca externa) — o mesmo princípio de "sem dependência
nova" de `dinheiro.py`.
"""

import base64
import hashlib
import hmac
import json
import os
import time

_SEGUNDOS_DE_VIDA = 8 * 60 * 60  # 8 horas


def _chave() -> bytes:
    chave = os.environ.get("SECRET_KEY")
    if not chave:
        raise RuntimeError(
            "SECRET_KEY não configurada — tem de ser igual em todos os nós")
    return chave.encode("utf-8")


def _codificar(carga: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(carga).encode("utf-8")).decode("ascii")


def _descodificar(texto: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(texto.encode("ascii")))


def emitir_token(usuario_id: str) -> str:
    carga = {"usuario_id": usuario_id, "expira": int(time.time()) + _SEGUNDOS_DE_VIDA}
    corpo = _codificar(carga)
    assinatura = hmac.new(_chave(), corpo.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{corpo}.{assinatura}"


def validar_token(token: str) -> str | None:
    """Devolve o usuario_id se o token for válido e não tiver expirado; senão None."""
    try:
        corpo, assinatura = token.split(".")
    except ValueError:
        return None

    assinatura_esperada = hmac.new(_chave(), corpo.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(assinatura, assinatura_esperada):
        return None

    carga = _descodificar(corpo)
    if carga["expira"] < int(time.time()):
        return None
    return carga["usuario_id"]
