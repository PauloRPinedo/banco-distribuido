"""GatewayExterno — RF-25.

`GatewayExternoSimulado` é um *stub*: espera uma latência aleatória e
responde confirmado/rejeitado ao acaso. Não há integração real com nenhum
banco — a transferência externa existe para exercitar o caminho de
confirmação e reversão, não para falar com um sistema de verdade.
"""

import abc
import random
import time
import uuid


class GatewayExterno(abc.ABC):

    @abc.abstractmethod
    def confirmar(self, sistema_externo_id: str, valor_centavos: int, op_id: str) -> dict:
        """Devolve {"confirmada": bool, "referencia_externa": str | None}."""


class GatewayExternoSimulado(GatewayExterno):

    def __init__(self, latencia_min_s: float = 0.2, latencia_max_s: float = 0.8,
                 probabilidade_confirmacao: float = 0.85):
        self._latencia_min_s = latencia_min_s
        self._latencia_max_s = latencia_max_s
        self._probabilidade_confirmacao = probabilidade_confirmacao

    def confirmar(self, sistema_externo_id: str, valor_centavos: int, op_id: str) -> dict:
        time.sleep(random.uniform(self._latencia_min_s, self._latencia_max_s))
        confirmada = random.random() < self._probabilidade_confirmacao
        return {
            "confirmada": confirmada,
            "referencia_externa": str(uuid.uuid4()) if confirmada else None,
        }


class GatewayExternoFalso(GatewayExterno):
    """Determinista, para testes — sem `sleep` nem `random` (RNF-06)."""

    def __init__(self, confirmar_sempre: bool = True):
        self._confirmar_sempre = confirmar_sempre

    def confirmar(self, sistema_externo_id: str, valor_centavos: int, op_id: str) -> dict:
        return {
            "confirmada": self._confirmar_sempre,
            "referencia_externa": f"teste-{op_id}" if self._confirmar_sempre else None,
        }
