"""Arranque de un nodo del banco.

    python3 -m banco.servidor --id A --puerto 8001

Mismo patrón que prototipo-1/banco/servidor.py — el nodo se identifica por
`--id`, y esa identidad es la que usa config/cluster.exemplo.json para saber
a quién más contactar (cuando el protocolo real exista).
"""

import argparse
import os
import sys

import uvicorn


def analizar(argumentos: list[str] | None = None) -> argparse.Namespace:
    analizador = argparse.ArgumentParser(
        prog="banco.servidor", description="Un nodo del banco distribuido.")
    analizador.add_argument("--id", default=os.environ.get("NODO_ID", "A"))
    analizador.add_argument("--puerto", type=int,
                             default=int(os.environ.get("PUERTO", "8001")))
    analizador.add_argument("--direccion", default="0.0.0.0",
                             help="0.0.0.0, no 127.0.0.1 — para ser alcanzable desde otro nodo")
    return analizador.parse_args(argumentos)


def main(argumentos: list[str] | None = None) -> int:
    opciones = analizar(argumentos)
    os.environ["NODO_ID"] = opciones.id
    print(f"nodo {opciones.id} escuchando en {opciones.direccion}:{opciones.puerto}", flush=True)
    uvicorn.run("banco.api.app:app", host=opciones.direccion, port=opciones.puerto)
    return 0


if __name__ == "__main__":
    sys.exit(main())
