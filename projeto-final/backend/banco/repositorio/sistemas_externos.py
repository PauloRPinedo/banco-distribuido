"""RepositorioSistemasExternos — RF-25."""


class RepositorioSistemasExternos:

    def __init__(self, conexion):
        self._conexion = conexion

    def buscar_por_id(self, sistema_externo_id: str) -> dict | None:
        with self._conexion.cursor() as cur:
            cur.execute(
                "SELECT * FROM sistema_externo WHERE id = %s AND activo = TRUE",
                (sistema_externo_id,),
            )
            return cur.fetchone()
