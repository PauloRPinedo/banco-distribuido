"""Leitura e escrita da tabela `usuario` — RF-26.

Não sabe nada de autenticação: o hash e a assinatura vivem em autenticacao/.
"""

from banco.dominio.erros import EmailDuplicado


class RepositorioUsuarios:

    def __init__(self, conexao) -> None:
        self._conexao = conexao

    def procurar_por_email(self, email: str) -> dict | None:
        with self._conexao.cursor() as cursor:
            cursor.execute(
                "SELECT id::text AS id, nome, email, hash_senha FROM usuario "
                "WHERE email = %s", (email,))
            return cursor.fetchone()

    def inserir(self, usuario: dict) -> None:
        """`INSERT` simples: o email é `UNIQUE`, e é a base que garante que
        dois registos simultâneos com o mesmo email não passam os dois."""
        import psycopg2.errors

        try:
            with self._conexao.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO usuario (id, nome, email, hash_senha, criado_em)
                    VALUES (%(id)s, %(nome)s, %(email)s, %(hash_senha)s, %(criado_em)s)
                    """,
                    usuario,
                )
        except psycopg2.errors.UniqueViolation:
            raise EmailDuplicado(f"o email {usuario['email']!r} já está registado") from None
