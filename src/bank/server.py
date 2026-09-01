"""Ponto de entrada do servidor.

Uso::

    python -m bank.server --config config/cluster.json --id A
    banco-server --config config/cluster.json --id B --seed 42

Sobe o uvicorn e duas threads de fundo:

- ``HeartbeatSender``, ativa enquanto este no for primario;
- ``ElectionTimer``, ativa enquanto for replica.

Encerramento limpo em SIGTERM: para as threads, faz flush do WAL e fecha os
arquivos. Em SIGKILL nao ha o que fazer -- e justamente esse o caso que os testes
de failover exercitam, e a corretude tem de vir do fsync antes do ACK, nao de um
desligamento gentil.
"""

from __future__ import annotations

import argparse


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Argumentos: ``--config``, ``--id``, ``--data-dir``, ``--fsync``, ``--seed``,
    ``--host``, ``--port`` (sobrepoem o JSON)."""
    raise NotImplementedError


def main(argv: list[str] | None = None) -> int:
    """Carrega a configuracao, monta a aplicacao e serve ate receber sinal."""
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
