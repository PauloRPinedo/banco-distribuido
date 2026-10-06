"""Lê a mesma lista de nós que o cluster usa (config/cluster.exemplo.json) —
o balanceador não inventa a sua própria lista, para que nunca fiquem
dessincronizadas.
"""

import json
import os


def carregar_nos(caminho: str | None = None) -> list[dict]:
    """Em Docker/VM: lê um ficheiro montado (`CLUSTER_CONFIG`). Em Lambda não
    há volume para montar, por isso, se `CLUSTER_CONFIG_JSON` trouxer o JSON
    diretamente (variável de ambiente da função), usa-se essa em vez de
    procurar um ficheiro — o mesmo formato, só muda de onde vem.
    """
    em_linha = os.environ.get("CLUSTER_CONFIG_JSON")
    if em_linha:
        return json.loads(em_linha)["nos"]

    caminho = caminho or os.environ.get("CLUSTER_CONFIG", "/config/cluster.json")
    with open(caminho, encoding="utf-8") as ficheiro:
        return json.load(ficheiro)["nos"]


def url_base(no: dict) -> str:
    return f"http://{no['endereco']}:{no['porta']}"
