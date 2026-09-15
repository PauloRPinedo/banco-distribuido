"""RepositorioOperaciones — ver diagrama-de-clases-servicio.md.

`buscar_por_op_id` es la mitad de la deduplicación de RN-08: la otra mitad
(devolver la respuesta guardada sin re-aplicar nada) vive en servicio/.
"""


class RepositorioOperaciones:

    def __init__(self, conexion):
        self._conexion = conexion

    def buscar_por_op_id(self, op_id: str) -> dict | None:
        with self._conexion.cursor() as cur:
            cur.execute("SELECT * FROM operacion WHERE id = %s", (op_id,))
            return cur.fetchone()

    def listar_por_cuenta(self, cuenta_id: str) -> list[dict]:
        with self._conexion.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM operacion
                WHERE cuenta_origen_id = %(id)s OR cuenta_destino_id = %(id)s
                ORDER BY fecha_hora
                """,
                {"id": cuenta_id},
            )
            return cur.fetchall()

    def guardar(self, operacion: dict) -> None:
        with self._conexion.cursor() as cur:
            cur.execute(
                """
                INSERT INTO operacion (id, tipo, cuenta_origen_id, cuenta_destino_id,
                                        valor_centavos, moneda_origen, moneda_destino,
                                        tasa_aplicada, valor_destino_centavos,
                                        sistema_externo_id, referencia_externa,
                                        fecha_hora, estado)
                VALUES (%(id)s, %(tipo)s, %(cuenta_origen_id)s, %(cuenta_destino_id)s,
                        %(valor_centavos)s, %(moneda_origen)s, %(moneda_destino)s,
                        %(tasa_aplicada)s, %(valor_destino_centavos)s,
                        %(sistema_externo_id)s, %(referencia_externa)s,
                        %(fecha_hora)s, %(estado)s)
                ON CONFLICT (id) DO UPDATE SET
                    estado = EXCLUDED.estado,
                    referencia_externa = EXCLUDED.referencia_externa
                """,
                operacion,
            )
