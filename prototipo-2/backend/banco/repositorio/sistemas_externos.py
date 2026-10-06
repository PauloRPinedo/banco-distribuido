"""Leitura da tabela `sistema_externo` — RF-25."""


class RepositorioSistemasExternos:

    def __init__(self, conexao) -> None:
        self._conexao = conexao

    def ativo(self, sistema_externo_id: str) -> bool:
        with self._conexao.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM sistema_externo WHERE id = %s AND ativo",
                (sistema_externo_id,),
            )
            return cursor.fetchone() is not None

    def listar(self) -> list[dict]:
        with self._conexao.cursor() as cursor:
            cursor.execute(
                "SELECT id, nome, codigo FROM sistema_externo WHERE ativo ORDER BY id")
            return cursor.fetchall()
