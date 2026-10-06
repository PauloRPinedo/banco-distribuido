"""Dependência do FastAPI para exigir sessão — RF-26, RN-16.

Separada de `autenticacao/` de propósito: esse módulo só sabe de hash e de
assinatura, não conhece HTTP; este conhece o cabeçalho `Authorization` e é a
fronteira entre os dois.
"""

from fastapi import Header

from banco.autenticacao import validar_token
from banco.servico.erros import SemPermissao, SemSessao


def usuario_autenticado(authorization: str | None = Header(default=None)) -> str:
    """Devolve o `usuario_id` do token, ou recusa com 401.

    Qualquer nó valida o token com a chave simétrica partilhada — sem chamada
    de rede nem à base de dados (RN-16).
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise SemSessao("falta o cabeçalho Authorization: Bearer <token>")
    usuario_id = validar_token(authorization.removeprefix("Bearer ").strip())
    if usuario_id is None:
        raise SemSessao("token inválido ou expirado")
    return usuario_id


def exigir_dono(dono: str | None, usuario_id: str, conta: str) -> None:
    """Uma conta só se consulta ou movimenta pelo seu dono."""
    if dono != usuario_id:
        raise SemPermissao(f"a conta {conta!r} não te pertence")
