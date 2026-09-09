"""Arranque de um nó do banco.

    python3 -m banco.servidor --id A --porta 8001
"""

import argparse
import sys
from pathlib import Path

from banco.cluster.no import No
from banco.interface.servidor_http import criar_servidor


def analisar(argumentos: list[str] | None = None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(
        prog="banco.servidor", description="Um nó do banco distribuído.")
    analisador.add_argument("--id", default="A",
                            help="identificador do nó (por omissão: A)")
    analisador.add_argument("--porta", type=int, default=8001)
    analisador.add_argument("--endereco", default="0.0.0.0",
                            help="endereço de escuta (por omissão: 0.0.0.0)")
    analisador.add_argument("--dados", default="dados",
                            help="diretório de estado (por omissão: dados/)")
    return analisador.parse_args(argumentos)


def main(argumentos: list[str] | None = None) -> int:
    opcoes = analisar(argumentos)
    no = No(opcoes.id, Path(opcoes.dados) / opcoes.id)
    servidor = criar_servidor(no, opcoes.endereco, opcoes.porta)

    estado = no.estado_do_no()
    # flush explícito: redirecionada para ficheiro, a saída fica em buffer e
    # a linha de arranque só apareceria no fim, que é quando não serve.
    print(f"nó {opcoes.id} em {opcoes.endereco}:{opcoes.porta} "
          f"· {estado['contas']} contas recuperadas "
          f"· último índice {estado['ultimo_indice']}", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\na terminar", flush=True)
    finally:
        servidor.server_close()
        no.fechar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
