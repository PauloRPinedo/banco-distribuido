"""Ponto de entrada do servidor.

Uso::

    python -m bank.server --config config/cluster.json --id A
    python -m bank.server --config config/cluster.lan.json --id C --seed 42

Sobe o uvicorn e duas threads de fundo:

- ``HeartbeatSender``, ativa enquanto este no for primario;
- ``ElectionTimer``, ativa enquanto for replica.

Por padrao escuta em ``0.0.0.0`` para que outra maquina alcance este no; o
endereco anunciado aos pares continua sendo o ``host`` da configuracao.

Encerramento limpo em SIGTERM: para as threads, faz flush do WAL e fecha os
arquivos. Em SIGKILL nao ha o que fazer -- e justamente esse o caso que os testes
de failover exercitam, e a corretude tem de vir do fsync antes do ACK, nao de um
desligamento gentil.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Argumentos: ``--config``, ``--id``, ``--data-dir``, ``--fsync``, ``--seed``,
    ``--bind``, ``--port`` (sobrepoem o JSON)."""
    parser = argparse.ArgumentParser(
        prog="banco-server", description="Servidor do banco distribuido"
    )
    parser.add_argument("--config", required=True, type=Path, help="JSON do cluster")
    parser.add_argument("--id", required=True, help="id deste no (A, B ou C)")
    parser.add_argument("--data-dir", type=Path, default=None, help="raiz dos dados")
    parser.add_argument(
        "--fsync",
        dest="fsync_mode",
        choices=("always", "batch", "off"),
        default=None,
        help="modo de durabilidade do WAL",
    )
    parser.add_argument("--seed", type=int, default=None, help="semente (RNF-06)")
    parser.add_argument(
        "--bind",
        default=None,
        help="interface de escuta (padrao 0.0.0.0, necessario para acesso em rede)",
    )
    parser.add_argument("--port", type=int, default=None, help="sobrepoe a porta do JSON")
    parser.add_argument("--log-level", default="warning", help="nivel de log do uvicorn")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Carrega a configuracao, monta a aplicacao e serve ate receber sinal."""
    import uvicorn

    from .api.app import create_app
    from .config import ClusterConfig

    args = parse_args(argv)
    overrides: dict[str, object] = {
        "data_dir": args.data_dir,
        "fsync_mode": args.fsync_mode,
        "rng_seed": args.seed,
    }
    if args.bind is not None:
        overrides["bind_host"] = args.bind

    config = ClusterConfig.load(args.config, args.id, **overrides)
    port = args.port if args.port is not None else config.self_node.port

    app = create_app(config)
    print(
        f"[{config.self_id}] escutando em {config.bind_host}:{port} "
        f"| anunciado como {config.self_node.base_url} "
        f"| cluster {[n.id for n in config.nodes]} (maioria {config.quorum_size})",
        flush=True,
    )
    uvicorn.run(app, host=config.bind_host, port=port, log_level=args.log_level)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
