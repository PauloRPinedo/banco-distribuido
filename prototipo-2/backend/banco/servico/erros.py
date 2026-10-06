"""Recusas que não são regras de dinheiro: sessão, dono da conta, câmbio.

Ficam fora de `dominio/erros.py` porque o domínio não sabe o que é um
utilizador nem um cluster. Herdam de `ErroDoBanco` na mesma, para saírem pelo
mesmo tratador e com a mesma forma `{"erro", "mensagem"}` que o resto da API.
"""

from banco.cluster.erros import SemQuorum  # noqa: F401 — vive com o protocolo
from banco.dominio.erros import EmailDuplicado  # noqa: F401 — vive com a ContaDuplicada
from banco.dominio.erros import ErroDoBanco


class SemSessao(ErroDoBanco):
    """Falta o token, ou o token não vale (expirado ou alterado)."""

    codigo = "sem_sessao"
    estado_http = 401


class CredenciaisInvalidas(ErroDoBanco):
    """Email ou senha errados — a mesma mensagem para os dois casos (CU-17)."""

    codigo = "credenciais_invalidas"
    estado_http = 401


class SemPermissao(ErroDoBanco):
    """A conta existe, mas não é de quem está a pedir."""

    codigo = "proibido"
    estado_http = 403


class TaxaIndisponivel(ErroDoBanco):
    """Não há taxa de câmbio registada para este par de moedas."""

    codigo = "taxa_indisponivel"
    estado_http = 409


class SistemaExternoInexistente(ErroDoBanco):
    codigo = "sistema_externo_inexistente"
    estado_http = 404
