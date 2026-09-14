"""Helpers compartidos entre los servicios de escritura — construir la fila
que va a `operacion` es igual en todos, cambia solo qué campos se llenan.
"""

from datetime import datetime


def fila_operacion(op_id: str, tipo: str, cuenta_origen_id: str | None,
                    cuenta_destino_id: str | None, valor_centavos: int,
                    ahora: datetime, **extra) -> dict:
    base = {
        "id": op_id, "tipo": tipo, "cuenta_origen_id": cuenta_origen_id,
        "cuenta_destino_id": cuenta_destino_id, "valor_centavos": valor_centavos,
        "moneda_origen": None, "moneda_destino": None, "tasa_aplicada": None,
        "valor_destino_centavos": None, "sistema_externo_id": None,
        "referencia_externa": None, "fecha_hora": ahora, "estado": "CONFIRMADA",
    }
    base.update(extra)
    return base
