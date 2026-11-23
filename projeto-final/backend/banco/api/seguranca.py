"""Dependência do FastAPI para exigir sessão — RF-26, RN-16.

Separada de `autenticacao/` de propósito: esse módulo só sabe de hash e de
assinatura, não conhece HTTP; este conhece o cabeçalho `Authorization` e é a
fronteira entre os dois.
"""

from fastapi import Header

from banco.autenticacao import validar_token
from banco.autenticacao.chaves import (e_chave_de_admin, e_chave_do_cluster,
                                       falhas_ativas)
from banco.servico.erros import (FalhasDesativadas, NaoEParDoCluster,
                                 SemChaveDeAdmin, SemPermissao, SemSessao)


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


def usuario_opcional(authorization: str | None = Header(default=None)) -> str | None:
    """O `usuario_id` se houver um token válido; None sem sessão (não recusa).

    Para as rotas abertas, como o depósito, que respondem mais a quem é dono.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return validar_token(authorization.removeprefix("Bearer ").strip())


def exigir_dono(dono: str | None, usuario_id: str, conta: str) -> None:
    """Uma conta só se consulta ou movimenta pelo seu dono."""
    if dono != usuario_id:
        raise SemPermissao(f"a conta {conta!r} não te pertence")


def par_do_cluster(x_chave_cluster: str | None = Header(default=None)) -> None:
    """Só outro nó, com a chave derivada da `SECRET_KEY`, fala por aqui."""
    if not e_chave_do_cluster(x_chave_cluster):
        raise NaoEParDoCluster("rota entre nós: falta a chave do cluster")


def operador(x_chave_admin: str | None = Header(default=None)) -> None:
    """Rotas que mudam o banco para todos (taxas): só com `CHAVE_ADMIN`."""
    if not e_chave_de_admin(x_chave_admin):
        raise SemChaveDeAdmin("rota de operador: falta X-Chave-Admin válida")


def injecao_de_falhas_ativa() -> None:
    if not falhas_ativas():
        raise FalhasDesativadas("a injeção de falhas está desligada (FALHAS_ATIVAS=1 liga-a)")
