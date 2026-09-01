"""Benchmark de carga (RNF-04: >= 500 TPS; RNF-05: p99 < 200 ms).

Uso::

    python scripts/bench.py --servers http://127.0.0.1:8001,... \
        --accounts 100 --ops 5000 --concurrency 32

Roda transferencias aleatorias entre N contas a partir de varias threads e mede
TPS e p50/p99. Ao final **audita**: a soma dos saldos tem de ser exatamente igual
a soma inicial. Um benchmark rapido que perde dinheiro nao vale nada, entao a
auditoria e parte do resultado, nao um extra.

Roda com ``--fsync always|batch|off`` para produzir a tabela de trade-off do
relatorio.
"""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
