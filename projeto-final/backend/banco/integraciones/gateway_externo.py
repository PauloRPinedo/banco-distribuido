"""GatewayExterno — RF-25.

`GatewayExternoSimulado` es el *stub* de docs/entregables/07-tecnologia/stack-tecnologico.md:
espera una latencia aleatoria y responde confirmado/rechazado al azar. No
hay integración real con ningún banco — ver el porqué en
docs/entregables/02-casos-de-uso/cu-16-transferir-sistema-externo.md.
"""

import abc
import random
import time
import uuid


class GatewayExterno(abc.ABC):

    @abc.abstractmethod
    def confirmar(self, sistema_externo_id: str, monto_centavos: int, op_id: str) -> dict:
        """Devuelve {"confirmada": bool, "referencia_externa": str | None}."""


class GatewayExternoSimulado(GatewayExterno):

    def __init__(self, latencia_min_s: float = 0.2, latencia_max_s: float = 0.8,
                 probabilidad_confirmacion: float = 0.85):
        self._latencia_min_s = latencia_min_s
        self._latencia_max_s = latencia_max_s
        self._probabilidad_confirmacion = probabilidad_confirmacion

    def confirmar(self, sistema_externo_id: str, monto_centavos: int, op_id: str) -> dict:
        time.sleep(random.uniform(self._latencia_min_s, self._latencia_max_s))
        confirmada = random.random() < self._probabilidad_confirmacion
        return {
            "confirmada": confirmada,
            "referencia_externa": str(uuid.uuid4()) if confirmada else None,
        }


class GatewayExternoFalso(GatewayExterno):
    """Determinista, para pruebas — sin `sleep` ni `random` (RNF-06)."""

    def __init__(self, confirmar_siempre: bool = True):
        self._confirmar_siempre = confirmar_siempre

    def confirmar(self, sistema_externo_id: str, monto_centavos: int, op_id: str) -> dict:
        return {
            "confirmada": self._confirmar_siempre,
            "referencia_externa": f"prueba-{op_id}" if self._confirmar_siempre else None,
        }
