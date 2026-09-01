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
import random
import statistics
import sys
import threading
import time
import uuid

import httpx

DEFAULT_SERVERS = "http://127.0.0.1:8001,http://127.0.0.1:8002,http://127.0.0.1:8003"


def find_primary(servers: list[str]) -> str:
    for base in servers:
        try:
            status = httpx.get(f"{base}/admin/status", timeout=2.0).json()
            if status["role"] == "primary":
                return base
        except (httpx.HTTPError, ValueError, KeyError):
            continue
    raise SystemExit("nenhum primario encontrado; o cluster esta no ar?")


def audit_all(servers: list[str]) -> dict[str, int]:
    totals = {}
    for base in servers:
        try:
            totals[base] = httpx.get(f"{base}/audit", timeout=2.0).json()["total_cents"]
        except (httpx.HTTPError, ValueError, KeyError):
            totals[base] = -1
    return totals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench", description="Carga e medicao (RNF-04/05)")
    parser.add_argument("--servers", default=DEFAULT_SERVERS)
    parser.add_argument("--accounts", type=int, default=50)
    parser.add_argument("--ops", type=int, default=2000)
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--prefix", default="bench")
    args = parser.parse_args(argv)

    servers = [s.strip().rstrip("/") for s in args.servers.split(",") if s.strip()]
    primary = find_primary(servers)
    print(f"primario: {primary}")

    # Contas de carga, com saldo folgado para que a rejeicao por saldo nao
    # mascare o throughput medido.
    names = [f"{args.prefix}-{i}" for i in range(args.accounts)]
    with httpx.Client(timeout=10.0) as client:
        for name in names:
            client.post(
                f"{primary}/accounts",
                json={
                    "op_id": str(uuid.uuid4()),
                    "account_id": name,
                    "initial_balance_cents": 1_000_000,
                },
            )
    total_before = httpx.get(f"{primary}/audit", timeout=5.0).json()["total_cents"]
    print(f"total antes: {total_before} centavos | {args.accounts} contas")

    latencies: list[float] = []
    errors: dict[str, int] = {}
    lock = threading.Lock()
    per_thread = max(args.ops // args.concurrency, 1)

    def worker(seed: int) -> None:
        rng = random.Random(seed)
        local_lat: list[float] = []
        local_err: dict[str, int] = {}
        with httpx.Client(timeout=10.0) as client:
            for _ in range(per_thread):
                source, target = rng.sample(names, 2)
                body = {
                    "op_id": str(uuid.uuid4()),
                    "from_account": source,
                    "to_account": target,
                    "amount_cents": rng.randint(1, 100),
                }
                started = time.perf_counter()
                try:
                    response = client.post(f"{primary}/transfers", json=body)
                    elapsed = time.perf_counter() - started
                    if response.status_code == 200:
                        local_lat.append(elapsed)
                        continue
                    # Uma resposta de erro nem sempre e JSON (um 500 do servidor
                    # vem como texto). Nunca deixar isso derrubar a thread: uma
                    # thread morta some com as operacoes restantes e falseia o TPS.
                    try:
                        code = str(response.json().get("error", response.status_code))
                    except ValueError:
                        code = f"http_{response.status_code}:{response.text[:60]}"
                    local_err[code] = local_err.get(code, 0) + 1
                except Exception as exc:  # noqa: BLE001
                    key = f"{type(exc).__name__}: {exc}"[:80]
                    local_err[key] = local_err.get(key, 0) + 1
        with lock:
            latencies.extend(local_lat)
            for key, value in local_err.items():
                errors[key] = errors.get(key, 0) + value

    threads = [threading.Thread(target=worker, args=(args.seed + i,)) for i in range(args.concurrency)]
    started = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    elapsed = time.perf_counter() - started

    attempted = per_thread * args.concurrency
    ok = len(latencies)
    ordered = sorted(latencies)

    def percentile(p: float) -> float:
        if not ordered:
            return 0.0
        index = min(int(round(p / 100 * (len(ordered) - 1))), len(ordered) - 1)
        return ordered[index] * 1000

    print()
    print(f"{'operacoes tentadas':<26} {attempted}")
    print(f"{'operacoes confirmadas':<26} {ok}")
    print(f"{'tempo total':<26} {elapsed:.2f} s")
    print(f"{'TPS':<26} {ok / elapsed:.1f}      (RNF-04 exige >= 500)")
    if ordered:
        print(f"{'latencia media':<26} {statistics.mean(ordered) * 1000:.1f} ms")
        print(f"{'latencia p50':<26} {percentile(50):.1f} ms")
        print(f"{'latencia p99':<26} {percentile(99):.1f} ms  (RNF-05 exige < 200)")
    if errors:
        print(f"{'erros':<26} {errors}")

    # A auditoria e parte do resultado: velocidade sem corretude nao vale nada.
    print()
    totals = audit_all(servers)
    print("auditoria por no:", totals)
    alive = [v for v in totals.values() if v >= 0]
    if not alive or len(set(alive)) != 1 or alive[0] != total_before:
        print(f"FALHA: o total mudou ou divergiu (antes={total_before}, depois={totals})")
        return 1
    print(f"OK: total inalterado ({total_before} centavos) e identico em todos os nos vivos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
