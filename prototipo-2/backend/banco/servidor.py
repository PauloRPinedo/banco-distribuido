"""Arranque de um nó do banco.

    python3 -m banco.servidor --id A --porta 8001

O nó identifica-se por `--id`, e é essa identidade que o ficheiro apontado por
CLUSTER_CONFIG usa para saber quem são os outros nós. Sem CLUSTER_CONFIG, o nó
funciona sozinho (maioria de um).
"""

import argparse
import os
import sys


def analisar(argumentos: list[str] | None = None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(
        prog="banco.servidor", description="Um nó do banco distribuído.")
    analisador.add_argument(
        "--id", default=os.environ.get("NO_ID", "A"),
        help="identifica o nó no arranque, em /saude e em /interno/estado")
    analisador.add_argument(
        "--porta", type=int, default=int(os.environ.get("PORTA", "8001")))
    analisador.add_argument(
        "--endereco", default="0.0.0.0",
        help="0.0.0.0, e não 127.0.0.1, para ser alcançável de outra máquina")
    return analisador.parse_args(argumentos)


def main(argumentos: list[str] | None = None) -> int:
    # O uvicorn entra aqui, e não no topo: assim `--help` funciona numa
    # máquina sem a pilha instalada.
    import uvicorn

    opcoes = analisar(argumentos)
    os.environ["NO_ID"] = opcoes.id
    print(f"nó {opcoes.id} à escuta em {opcoes.endereco}:{opcoes.porta}", flush=True)
    uvicorn.run("banco.api.app:app", host=opcoes.endereco, port=opcoes.porta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
