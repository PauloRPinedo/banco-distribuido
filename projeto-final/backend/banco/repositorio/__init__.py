"""Acceso a PostgreSQL. Cada nodo tiene su propio Postgres, independiente de
los otros nodos (ver docs/adr/ADR-0001, Decisión 1) — este módulo no sabe
nada de replicación, solo lee/escribe en la base local de este proceso.
"""

from banco.repositorio.conexion import obtener_conexion
from banco.repositorio.cuentas import RepositorioCuentas
from banco.repositorio.operaciones import RepositorioOperaciones
from banco.repositorio.tasa_cambio import RepositorioTasaCambio
from banco.repositorio.sistemas_externos import RepositorioSistemasExternos
from banco.repositorio.usuarios import RepositorioUsuarios

__all__ = [
    "obtener_conexion",
    "RepositorioCuentas",
    "RepositorioOperaciones",
    "RepositorioTasaCambio",
    "RepositorioSistemasExternos",
    "RepositorioUsuarios",
]
