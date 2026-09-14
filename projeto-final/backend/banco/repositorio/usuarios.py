"""RepositorioUsuarios — RF-26. Usuario ya está replicado igual que el resto
de los datos (RN-04); este repositorio no sabe nada de autenticación, solo
lee/escribe filas — el hash y la firma viven en autenticacion/.
"""


class RepositorioUsuarios:

    def __init__(self, conexion):
        self._conexion = conexion

    def buscar_por_email(self, email: str) -> dict | None:
        with self._conexion.cursor() as cur:
            cur.execute("SELECT * FROM usuario WHERE email = %s", (email,))
            return cur.fetchone()

    def guardar(self, usuario: dict) -> None:
        with self._conexion.cursor() as cur:
            cur.execute(
                """
                INSERT INTO usuario (id, nombre, email, password_hash, fecha_creacion)
                VALUES (%(id)s, %(nombre)s, %(email)s, %(password_hash)s, %(fecha_creacion)s)
                ON CONFLICT (id) DO NOTHING
                """,
                usuario,
            )
