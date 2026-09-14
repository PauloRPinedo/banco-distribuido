"""ServicioTransferencias — CU-04 (misma moneda) implementado; conversión
(CU-05), autotransferencia (CU-06) y externa (CU-16) quedan pendientes,
porque dependen de las extensiones de dominio listadas en
banco/dominio/PENDIENTE.md.
"""

from datetime import datetime, timezone

from banco.dominio.contas import Conta, Livro
from banco.dominio.operacoes import Transferencia
from banco.servicio._comun import fila_operacion


class ServicioTransferencias:

    def __init__(self, repo_cuentas, repo_operaciones, nodo):
        self._cuentas = repo_cuentas
        self._operaciones = repo_operaciones
        self._nodo = nodo

    def transferir(self, origen_id: str, destino_id: str, monto_centavos: int,
                    op_id: str) -> dict:
        existente = self._operaciones.buscar_por_op_id(op_id)
        if existente is not None:
            return existente

        fila_origen = self._cuentas.buscar_por_id(origen_id)
        fila_destino = self._cuentas.buscar_por_id(destino_id)
        if fila_origen is None or fila_destino is None:
            raise ValueError("cuenta origen o destino inexistente")
        if fila_origen["moneda"] != fila_destino["moneda"]:
            raise ValueError(
                "monedas distintas — usar transferirConConversion (CU-05, pendiente)")

        libro = Livro()
        for cuenta_id, fila in ((origen_id, fila_origen), (destino_id, fila_destino)):
            libro.contas[cuenta_id] = Conta(
                cuenta_id, fila["saldo_centavos"], fila["fecha_creacion"].timestamp())
            libro.extratos[cuenta_id] = []

        resultado = Transferencia(origen_id, destino_id, monto_centavos).aplicar(
            libro, indice=1, instante=datetime.now(timezone.utc).timestamp())

        if not self._nodo.replicar_y_esperar_mayoria({"op_id": op_id, "tipo": "TRANSFERENCIA"}):
            raise RuntimeError("sin_quorum")

        ahora = datetime.now(timezone.utc)
        fila_origen["saldo_centavos"] = resultado["saldos_centavos"][origen_id]
        fila_destino["saldo_centavos"] = resultado["saldos_centavos"][destino_id]
        self._cuentas.guardar(fila_origen)
        self._cuentas.guardar(fila_destino)
        self._operaciones.guardar(fila_operacion(
            op_id, "TRANSFERENCIA", origen_id, destino_id, monto_centavos, ahora))
        return resultado

    def transferir_con_conversion(self, *args, **kwargs):
        raise NotImplementedError(
            "CU-05 pendiente — ver banco/dominio/PENDIENTE.md (RN-06, tasa_cambio)")

    def autotransferir(self, *args, **kwargs):
        raise NotImplementedError("CU-06 pendiente — misma dependencia que CU-05")
