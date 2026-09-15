"""Arranque de um nó do banco.

    python3 -m banco.servidor --id A --porta 8001

Há um nó só nesta etapa, por isso `--id` é informativo: aparece no arranque e
em `/saude`. Fica porque o comando é o mesmo da etapa 2, e um comando que não
muda entre etapas é um detalhe a menos para explicar na defesa.
"""

import argparse
import os
import sys


def analisar(argumentos: list[str] | None = None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(
        prog="banco.servidor", description="Um nó do banco.")
    analisador.add_argument(
        "--id", default=os.environ.get("NO_ID", "A"),
        help="identifica o nó no arranque e em /saude")
    analisador.add_argument(
        "--porta", type=int, default=int(os.environ.get("PORTA", "8001")))
    analisador.add_argument(
        "--endereco", default="0.0.0.0",
        help="0.0.0.0, e não 127.0.0.1, para ser alcançável de outra máquina")
    return analisador.parse_args(argumentos)


def main(argumentos: list[str] | None = None) -> int:
    import uvicorn

    opcoes = analisar(argumentos)
    os.environ["NO_ID"] = opcoes.id
    print(f"nó {opcoes.id} à escuta em {opcoes.endereco}:{opcoes.porta}", flush=True)
    uvicorn.run("banco.api.app:app", host=opcoes.endereco, port=opcoes.porta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
