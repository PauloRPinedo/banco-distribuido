"""Lee la misma lista de nodos que usa el clúster
(config/cluster.exemplo.json) — el balanceador no inventa su propia lista,
para que nunca queden desincronizadas.
"""

import json
import os


def cargar_nodos(ruta: str | None = None) -> list[dict]:
    """En Docker/VM: lee un archivo montado (`CLUSTER_CONFIG`). En Lambda no
    hay volumen que montar, así que si `CLUSTER_CONFIG_JSON` trae el JSON
    directo (variable de entorno de la función), se usa esa en vez de
    buscar un archivo — mismo formato, solo cambia de dónde sale.
    """
    en_linea = os.environ.get("CLUSTER_CONFIG_JSON")
    if en_linea:
        return json.loads(en_linea)["nos"]

    ruta = ruta or os.environ.get("CLUSTER_CONFIG", "/config/cluster.json")
    with open(ruta, encoding="utf-8") as archivo:
        return json.load(archivo)["nos"]


def url_base(nodo: dict) -> str:
    return f"http://{nodo['endereco']}:{nodo['porta']}"
