"""ServicioCuentas — ver docs/entregables/06-diseno-detallado/diagrama-de-clases-servicio.md.

Puente entre el dominio puro (banco.dominio, en memoria) y la persistencia
real (banco.repositorio, Postgres): carga la cuenta involucrada en un
`Livro` efímero, corre la operación pura de dominio sobre ese `Livro`, y
guarda el resultado. `dominio/` sigue sin saber que Postgres existe.

Solo cubre CORRIENTE (RF-01 a RF-03) — AHORRO/PLAZO_FIJO (RF-23/RF-24) están
en `banco/dominio/PENDIENTE.md`.
"""

import uuid
from datetime import datetime, timezone

from banco.dominio.contas import Conta, Livro
from banco.dominio.operacoes import CriarConta, Deposito, Saque
from banco.servicio._comun import fila_operacion


def _fila_vacia(cuenta_id: str, usuario_id: str, moneda: str, saldo_centavos: int,
                 ahora: datetime) -> dict:
    return {
        "id": cuenta_id, "usuario_id": usuario_id, "moneda": moneda,
        "saldo_centavos": saldo_centavos, "fecha_creacion": ahora,
        "estado": "ACTIVA", "tipo_producto": "CORRIENTE", "tasa_interes": None,
        "fecha_ultimo_interes": None, "fecha_vencimiento": None,
    }


class ServicioCuentas:

    def __init__(self, repo_cuentas, repo_operaciones, nodo):
        self._cuentas = repo_cuentas
        self._operaciones = repo_operaciones
        self._nodo = nodo

    def crear_cuenta(self, usuario_id: str, moneda: str, saldo_inicial_centavos: int,
                      op_id: str) -> dict:
        existente = self._operaciones.buscar_por_op_id(op_id)
        if existente is not None:
            return existente

        cuenta_id = uuid.uuid4().hex[:12]
        libro = Livro()
        resultado = CriarConta(cuenta_id, saldo_inicial_centavos).aplicar(
            libro, indice=1, instante=datetime.now(timezone.utc).timestamp())

        if not self._nodo.replicar_y_esperar_mayoria({"op_id": op_id, "tipo": "CREACION"}):
            raise RuntimeError("sin_quorum")

        ahora = datetime.now(timezone.utc)
        self._cuentas.guardar(_fila_vacia(
            cuenta_id, usuario_id, moneda, resultado["saldo_centavos"], ahora))
        self._operaciones.guardar(fila_operacion(
            op_id, "CREACION", None, cuenta_id, saldo_inicial_centavos, ahora))
        return {"id": cuenta_id, "saldo_centavos": resultado["saldo_centavos"]}

    def consultar_saldo(self, cuenta_id: str) -> dict:
        fila = self._cuentas.buscar_por_id(cuenta_id)
        if fila is None:
            raise ValueError(f"la cuenta {cuenta_id!r} no existe")
        return fila

    def _mover(self, cuenta_id: str, operacion_cls, valor_centavos: int, tipo: str,
               op_id: str) -> dict:
        existente = self._operaciones.buscar_por_op_id(op_id)
        if existente is not None:
            return existente

        fila = self._cuentas.buscar_por_id(cuenta_id)
        if fila is None:
            raise ValueError(f"la cuenta {cuenta_id!r} no existe")

        libro = Livro()
        libro.contas[cuenta_id] = Conta(
            cuenta_id, fila["saldo_centavos"], fila["fecha_creacion"].timestamp())
        libro.extratos[cuenta_id] = []
        resultado = operacion_cls(cuenta_id, valor_centavos).aplicar(
            libro, indice=1, instante=datetime.now(timezone.utc).timestamp())

        if not self._nodo.replicar_y_esperar_mayoria({"op_id": op_id, "tipo": tipo}):
            raise RuntimeError("sin_quorum")

        ahora = datetime.now(timezone.utc)
        fila["saldo_centavos"] = resultado["saldo_centavos"]
        self._cuentas.guardar(fila)
        origen = cuenta_id if tipo == "RETIRO" else None
        destino = cuenta_id if tipo == "DEPOSITO" else None
        self._operaciones.guardar(fila_operacion(
            op_id, tipo, origen, destino, valor_centavos, ahora))
        return {"id": cuenta_id, "saldo_centavos": resultado["saldo_centavos"]}

    def depositar(self, cuenta_id: str, monto_centavos: int, op_id: str) -> dict:
        return self._mover(cuenta_id, Deposito, monto_centavos, "DEPOSITO", op_id)

    def retirar(self, cuenta_id: str, monto_centavos: int, op_id: str) -> dict:
        return self._mover(cuenta_id, Saque, monto_centavos, "RETIRO", op_id)

    def consultar_extracto(self, cuenta_id: str) -> list[dict]:
        return self._operaciones.listar_por_cuenta(cuenta_id)
