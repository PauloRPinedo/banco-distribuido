"""Conexión al Postgres local de este nodo.

No hay pool aquí a propósito — psycopg2 ya maneja una conexión por hilo de
forma razonable a la escala de este proyecto; agregar un pool sería
complejidad sin un problema medido que la justifique.
"""

import os

import psycopg2
import psycopg2.extras


def obtener_conexion():
    """Una conexión nueva, con autocommit apagado (el que llama controla la
    transacción — necesario para que cluster/ pueda decidir cuándo aplicar
    una entrada, no antes)."""
    conexion = psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ.get("PGDATABASE", "banco"),
        user=os.environ.get("PGUSER", "banco"),
        password=os.environ.get("PGPASSWORD", "banco"),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    conexion.autocommit = False
    return conexion
