"""RepositorioTasaCambio — ver GUIA-REPLICA-POSTGRESQL.md para cómo se llena
esta tabla desde el tick del primario (RF-23/RF-24 comparten el mismo tick).
"""


class RepositorioTasaCambio:

    def __init__(self, conexion):
        self._conexion = conexion

    def tasa_vigente(self, moneda_origen: str, moneda_destino: str) -> dict | None:
        with self._conexion.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM tasa_cambio
                WHERE moneda_origen = %s AND moneda_destino = %s
                  AND vigente_desde <= now()
                ORDER BY vigente_desde DESC
                LIMIT 1
                """,
                (moneda_origen, moneda_destino),
            )
            return cur.fetchone()

    def registrar(self, moneda_origen: str, moneda_destino: str, valor,
                   vigente_desde) -> None:
        with self._conexion.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tasa_cambio (moneda_origen, moneda_destino, valor, vigente_desde)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (moneda_origen, moneda_destino, vigente_desde) DO NOTHING
                """,
                (moneda_origen, moneda_destino, valor, vigente_desde),
            )
