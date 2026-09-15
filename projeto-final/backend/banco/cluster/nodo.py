"""Nodo del clúster — TODO real en ROADMAP.md, subfase 2.x (Cristhian).

Esta clase hoy se comporta como el `No` de Prototipo 1: acepta todo, sin
quórum ni elección, porque el protocolo real (replicación, voto, fencing por
`epoch`) todavía no está escrito. Se deja aquí, y no vacía, para que `api/`
y `servicio/` ya tengan a quién llamar — cuando el protocolo real exista,
esta clase gana un `ClienteInterno` que hable con los otros nodos y el
resto del código no debería tener que cambiar.

Ver docs/entregables/06-diseno-detallado/diagrama-de-estados-nodo.md para el
comportamiento que falta.
"""


class Nodo:

    def __init__(self, identificador: str):
        self.id = identificador
        self._epoch = 1

    def es_primario(self) -> bool:
        # TODO(prototipo-2): reemplazar por la máquina de estados real
        # (RÉPLICA / CANDIDATO / PRIMARIO). Hoy todo nodo se comporta como
        # primario porque no hay con quién competir el rol.
        return True

    def estado(self) -> dict:
        return {
            "nodo": self.id,
            "rol": "primario" if self.es_primario() else "replica",
            "epoch": self._epoch,
        }

    def replicar_y_esperar_mayoria(self, entrada: dict) -> bool:
        # TODO(prototipo-2): POST /interno/replicar a los pares y contar
        # confirmaciones (RF-10). Hoy no hay pares — una entrada durable en
        # este único nodo ya se da por confirmada, igual que
        # prototipo-1/banco/cluster/no.py en su etapa 1.
        return True
