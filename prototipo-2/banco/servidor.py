"""Arranque de um nó do banco.

    python3 -m banco.servidor --id A --porta 8001 \
        --bd postgresql:///banco_a
    python3 -m banco.servidor --id A --porta 8001 --armazem ficheiro

É aqui que se escolhe onde o log vive. O nó não sabe: recebe um armazém já
construído.
"""

import argparse
import os
import sys
from pathlib import Path

from banco.cluster.configuracao import (ConfiguracaoDoCluster,
                                        ConfiguracaoInvalida)
from banco.cluster.no import No
from banco.interface.servidor_http import criar_servidor
from banco.persistencia.fabrica import NOMES, criar_armazem


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
    analisador.add_argument("--armazem", choices=NOMES, default="postgres",
                            help="onde vive o log (por omissão: postgres)")
    analisador.add_argument("--bd", default=os.environ.get("BANCO_BD"),
                            help="DSN do PostgreSQL; também se lê de BANCO_BD")
    analisador.add_argument("--origens", default="*",
                            help="origem aceite pelo navegador (por omissão: *)")
    analisador.add_argument("--config",
                            help="ficheiro do cluster; sem ele, corre um nó só")
    analisador.add_argument("--encaminhar-escritas", action="store_true",
                            help="reenvia escritas ao primário em vez de "
                                 "recusar; para o frontend atrás de um túnel")
    return analisador.parse_args(argumentos)


def main(argumentos: list[str] | None = None) -> int:
    opcoes = analisar(argumentos)
    try:
        configuracao = (ConfiguracaoDoCluster.de_ficheiro(opcoes.config)
                        if opcoes.config else None)
        if configuracao is not None:
            # Falha já aqui se o id não estiver no ficheiro, em vez de o nó subir
            # e ficar a falar sozinho sem ninguém perceber porquê.
            configuracao.obter(opcoes.id)
        armazem = criar_armazem(opcoes.armazem, no_id=opcoes.id,
                                diretorio=Path(opcoes.dados) / opcoes.id,
                                dsn=opcoes.bd)
    except ConfiguracaoInvalida as erro:
        print(f"  erro: configuração do cluster inválida", file=sys.stderr)
        print(f"  {erro}", file=sys.stderr)
        print("  → confira o ficheiro, ou corra um nó só: sem --config",
              file=sys.stderr)
        return 2
    except ValueError as erro:
        # Falta de configuração não é um rasto de exceção: é uma frase e o passo
        # seguinte.
        print(f"  erro: {erro}", file=sys.stderr)
        print("  → ou arranque sem base de dados: "
              "python3 -m banco.servidor --armazem ficheiro", file=sys.stderr)
        return 2
    no = No(opcoes.id, armazem, configuracao)
    servidor = criar_servidor(no, opcoes.endereco, opcoes.porta, opcoes.origens,
                              opcoes.encaminhar_escritas)
    no.arrancar()

    estado = no.estado_do_no()
    # flush explícito: redirecionada para ficheiro, a saída fica em buffer e
    # a linha de arranque só apareceria no fim, que é quando não serve.
    # A durabilidade é declarada, não afirmada: com PostgreSQL pergunta-se à
    # base o que ela própria diz de si. É a resposta pronta na defesa a "como é
    # que sabem que houve fsync?".
    descricao = getattr(armazem, "descrever_durabilidade", None)
    durabilidade = f" · {descricao()}" if descricao else ""
    pares = ("sozinho" if configuracao is None else
             "com " + ", ".join(p.id for p in configuracao.pares_de(opcoes.id)))
    print(f"nó {opcoes.id} em {opcoes.endereco}:{opcoes.porta} "
          f"· armazém {opcoes.armazem}{durabilidade} "
          f"· {pares} "
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
