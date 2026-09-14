"""Construye una petición por request: una conexión Postgres, los
repositorios sobre ella, y los servicios sobre esos repositorios. Sencillo a
propósito — un *connection pool* se agrega solo si un *benchmark* real (RNF-04)
muestra que hace falta, no antes.
"""

import os

from banco.cluster import Nodo
from banco.repositorio import (RepositorioCuentas, RepositorioOperaciones,
                                RepositorioUsuarios, obtener_conexion)
from banco.servicio import ServicioAuditoria, ServicioAutenticacion, ServicioCuentas, ServicioTransferencias

# GatewayExternoSimulado (RF-25) y RepositorioTasaCambio/RepositorioSistemasExternos
# (RF-20/RF-25) se conectan aquí cuando CU-05/CU-16 salgan de PENDIENTE.md.

NODO = Nodo(os.environ.get("NODO_ID", "A"))


def obtener_servicio_cuentas():
    conexion = obtener_conexion()
    try:
        yield ServicioCuentas(RepositorioCuentas(conexion), RepositorioOperaciones(conexion), NODO)
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def obtener_servicio_transferencias():
    conexion = obtener_conexion()
    try:
        yield ServicioTransferencias(RepositorioCuentas(conexion), RepositorioOperaciones(conexion), NODO)
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def obtener_servicio_auditoria():
    conexion = obtener_conexion()
    try:
        yield ServicioAuditoria(conexion)
    finally:
        conexion.close()


def obtener_servicio_autenticacion():
    conexion = obtener_conexion()
    try:
        yield ServicioAutenticacion(RepositorioUsuarios(conexion))
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()
