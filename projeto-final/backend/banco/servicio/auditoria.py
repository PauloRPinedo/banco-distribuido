"""ServicioAuditoria — RF-14.

TODO(RF-19/20): separar por moneda (`auditarPorMoneda`, ya nombrado así en
diagrama-de-clases-servicio.md) — hoy suma todas las cuentas juntas porque
`dominio/` todavía no distingue moneda (ver PENDIENTE.md).
"""


class ServicioAuditoria:

    def __init__(self, repo_cuentas_sql):
        self._conexion = repo_cuentas_sql

    def auditar(self) -> dict:
        with self._conexion.cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(saldo_centavos), 0) AS total FROM cuenta")
            total_por_saldos = cur.fetchone()["total"]

            cur.execute("""
                SELECT COALESCE(SUM(
                    CASE
                        WHEN tipo IN ('CREACION', 'DEPOSITO') THEN valor_centavos
                        WHEN tipo = 'RETIRO' THEN -valor_centavos
                        ELSE 0
                    END
                ), 0) AS total
                FROM operacion WHERE estado = 'CONFIRMADA'
            """)
            total_por_log = cur.fetchone()["total"]

        return {
            "total_centavos": total_por_saldos,
            "total_esperado_centavos": total_por_log,
            "divergencia_centavos": total_por_saldos - total_por_log,
            "divergente": total_por_saldos != total_por_log,
        }
