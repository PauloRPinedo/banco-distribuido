"""Cliente de linha de comando (RF-17, historia de usuario 12).

Uso::

    python cli/banco_cli.py --servers http://127.0.0.1:8001,http://127.0.0.1:8002,http://127.0.0.1:8003 \
        criar-conta alice --saldo 100.00
    python cli/banco_cli.py saldo alice
    python cli/banco_cli.py depositar alice 50.00
    python cli/banco_cli.py sacar alice 20.00
    python cli/banco_cli.py transferir alice bob 10.00
    python cli/banco_cli.py extrato alice
    python cli/banco_cli.py auditoria
    python cli/banco_cli.py status          # painel dos 2 ou 3 servidores (historia de usuario 11)

Duas coisas que este cliente precisa acertar:

**Achar o primario.** Guarda a lista de servidores e tenta o ultimo primario
conhecido. Se receber 409 ``not_primary``, segue o ``primary_hint``; se o no nao
responder, tenta o proximo da lista. Durante uma eleicao todos podem recusar por
alguns segundos -- ai espera e repete, em vez de falhar na cara do usuario.

**Repetir sem duplicar.** O ``op_id`` e gerado **uma vez** por operacao logica e
reutilizado em todas as retentativas. Gerar um novo a cada tentativa transformaria
uma transferencia repetida em duas transferencias -- exatamente o bug que o
projeto existe para evitar.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid

import httpx

DEFAULT_SERVERS = "http://127.0.0.1:8001,http://127.0.0.1:8002,http://127.0.0.1:8003"


def parse_amount(raw: str) -> int:
    """Converte "12.34" em centavos. Reaproveita a regra do dominio."""
    from bank.domain.money import parse_amount as _parse

    return _parse(raw)


def format_amount(cents: int) -> str:
    from bank.domain.money import format_amount as _format

    return _format(cents)


class BankError(Exception):
    """Erro devolvido pelo servidor, ja traduzido para mensagem legivel."""


class BankClient:
    """Cliente com descoberta de primario e retentativa idempotente."""

    def __init__(self, servers: list[str], timeout_s: float = 2.0, max_retries: int = 5) -> None:
        if not servers:
            raise ValueError("e preciso ao menos um servidor")
        self.servers = [s.rstrip("/") for s in servers]
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self._preferred = self.servers[0]
        self._client = httpx.Client(timeout=timeout_s)

    def _order(self) -> list[str]:
        """Ultimo primario conhecido primeiro, depois os demais."""
        rest = [s for s in self.servers if s != self._preferred]
        return [self._preferred] + rest

    def _call(
        self, method: str, path: str, body: dict | None = None, params: dict | None = None
    ) -> dict:
        """Executa a requisicao seguindo o primario e repetindo com o mesmo ``op_id``.

        Backoff crescente entre tentativas, para nao martelar o cluster enquanto
        uma eleicao acontece.
        """
        last_error = "nenhum servidor respondeu"
        for attempt in range(self.max_retries):
            for base in self._order():
                try:
                    response = self._client.request(
                        method, f"{base}{path}", json=body, params=params
                    )
                except httpx.HTTPError:
                    continue  # no fora do ar: tentar o proximo

                if response.status_code == 200:
                    self._preferred = base
                    return response.json()

                try:
                    payload = response.json()
                except ValueError:
                    payload = {"error": "resposta ilegivel", "message": response.text[:200]}

                code = payload.get("error")
                if code == "not_primary":
                    hint = payload.get("primary_hint")
                    if hint and hint.rstrip("/") in self.servers:
                        self._preferred = hint.rstrip("/")
                    continue
                if code in ("no_quorum", "read_only"):
                    # Falha transitoria: pode passar assim que o cluster estabilizar.
                    last_error = payload.get("message", code)
                    break
                # Erro de negocio (saldo insuficiente, conta inexistente...):
                # repetir nao vai mudar a resposta.
                raise BankError(payload.get("message") or code or response.text)

            time.sleep(min(0.2 * (2**attempt), 2.0))

        raise BankError(f"nao foi possivel completar a operacao: {last_error}")

    # -- operacoes ----------------------------------------------------------
    # O op_id nasce aqui, uma vez por operacao logica, e sobrevive a todas as
    # retentativas feitas dentro de _call.

    def create_account(self, account_id: str, initial_cents: int) -> dict:
        return self._call(
            "POST",
            "/accounts",
            {
                "op_id": str(uuid.uuid4()),
                "account_id": account_id,
                "initial_balance_cents": initial_cents,
            },
        )

    def get_balance(self, account_id: str) -> dict:
        return self._call("GET", f"/accounts/{account_id}")

    def deposit(self, account_id: str, amount_cents: int) -> dict:
        return self._call(
            "POST",
            f"/accounts/{account_id}/deposit",
            {"op_id": str(uuid.uuid4()), "amount_cents": amount_cents},
        )

    def withdraw(self, account_id: str, amount_cents: int) -> dict:
        return self._call(
            "POST",
            f"/accounts/{account_id}/withdraw",
            {"op_id": str(uuid.uuid4()), "amount_cents": amount_cents},
        )

    def transfer(self, from_account: str, to_account: str, amount_cents: int) -> dict:
        return self._call(
            "POST",
            "/transfers",
            {
                "op_id": str(uuid.uuid4()),
                "from_account": from_account,
                "to_account": to_account,
                "amount_cents": amount_cents,
            },
        )

    def statement(self, account_id: str, limit: int = 50) -> dict:
        return self._call("GET", f"/accounts/{account_id}/statement", params={"limit": limit})

    def audit(self) -> dict:
        return self._call("GET", "/audit")

    def cluster_status(self) -> list[dict]:
        """Consulta ``/admin/status`` em todos os servidores, inclusive os mortos."""
        rows = []
        for base in self.servers:
            try:
                response = self._client.get(f"{base}/admin/status", timeout=1.0)
                row = response.json()
                row["url"] = base
                row["reachable"] = True
            except (httpx.HTTPError, ValueError):
                row = {"url": base, "reachable": False}
            rows.append(row)
        return rows

    def close(self) -> None:
        self._client.close()


# -- apresentacao -----------------------------------------------------------


def _print_operation(label: str, result: dict) -> None:
    balances = result.get("balances") or {}
    saldos = ", ".join(f"{a}={format_amount(v)}" for a, v in sorted(balances.items()))
    print(f"{label} confirmada (idx={result['applied_idx']})" + (f" | {saldos}" if saldos else ""))


def _print_status(rows: list[dict]) -> None:
    print(f"{'SERVIDOR':<28} {'ESTADO':<10} {'PAPEL':<10} {'EPOCH':>6} {'COMMIT':>7} {'APLICADO':>9}")
    print("-" * 74)
    for row in rows:
        if not row.get("reachable"):
            print(f"{row['url']:<28} {'FORA DO AR':<10} {'-':<10} {'-':>6} {'-':>7} {'-':>9}")
            continue
        marca = "PRIMARIO" if row["role"] == "primary" else row["role"]
        escrita = "" if row.get("write_available") else "  (somente leitura)"
        print(
            f"{row['url']:<28} {'no ar':<10} {marca:<10} {row['epoch']:>6} "
            f"{row['commit_index']:>7} {row['applied_idx']:>9}{escrita}"
        )


def build_parser() -> argparse.ArgumentParser:
    """Monta os subcomandos listados no cabecalho do modulo."""
    parser = argparse.ArgumentParser(
        prog="banco-cli", description="Cliente do banco distribuido (RF-17)"
    )
    parser.add_argument(
        "--servers",
        default=os.environ.get("BANCO_SERVERS", DEFAULT_SERVERS),
        help="lista de servidores separados por virgula (ou variavel BANCO_SERVERS)",
    )
    parser.add_argument("--json", action="store_true", help="saida crua em JSON")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("criar-conta", help="RF-01: cria uma conta")
    p.add_argument("conta")
    p.add_argument("--saldo", default="0.00", help="saldo inicial, ex.: 100.00")

    p = sub.add_parser("saldo", help="RF-02: consulta o saldo")
    p.add_argument("conta")

    p = sub.add_parser("depositar", help="RF-03: deposito")
    p.add_argument("conta")
    p.add_argument("valor")

    p = sub.add_parser("sacar", help="RF-03: saque")
    p.add_argument("conta")
    p.add_argument("valor")

    p = sub.add_parser("transferir", help="RF-04: transferencia atomica")
    p.add_argument("origem")
    p.add_argument("destino")
    p.add_argument("valor")

    p = sub.add_parser("extrato", help="RF-05: extrato da conta")
    p.add_argument("conta")
    p.add_argument("--limite", type=int, default=20)

    sub.add_parser("auditoria", help="RF-14: total de dinheiro em circulacao")
    sub.add_parser("status", help="painel dos servidores (historia de usuario 11)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = BankClient([s for s in args.servers.split(",") if s.strip()])
    try:
        if args.comando == "status":
            rows = client.cluster_status()
            print(json.dumps(rows, indent=2)) if args.json else _print_status(rows)
            return 0

        if args.comando == "criar-conta":
            result = client.create_account(args.conta, parse_amount(args.saldo))
            label = f"conta {args.conta} criada com {args.saldo}"
        elif args.comando == "saldo":
            result = client.get_balance(args.conta)
            label = None
            if not args.json:
                atraso = " (leitura possivelmente atrasada)" if result.get("stale") else ""
                print(f"{args.conta}: {format_amount(result['balance_cents'])}{atraso}")
        elif args.comando == "depositar":
            result = client.deposit(args.conta, parse_amount(args.valor))
            label = f"deposito de {args.valor} em {args.conta}"
        elif args.comando == "sacar":
            result = client.withdraw(args.conta, parse_amount(args.valor))
            label = f"saque de {args.valor} de {args.conta}"
        elif args.comando == "transferir":
            result = client.transfer(args.origem, args.destino, parse_amount(args.valor))
            label = f"transferencia de {args.valor} de {args.origem} para {args.destino}"
        elif args.comando == "extrato":
            result = client.statement(args.conta, args.limite)
            label = None
            if not args.json:
                print(f"extrato de {args.conta} | saldo {format_amount(result['balance_cents'])}")
                for entry in result["entries"]:
                    payload = entry["payload"]
                    valor = format_amount(payload.get("amount_cents", 0))
                    print(f"  idx={entry['idx']:<5} {entry['type']:<15} {valor:>12}  {payload}")
        elif args.comando == "auditoria":
            result = client.audit()
            label = None
            if not args.json:
                print(
                    f"total em circulacao: {format_amount(result['total_cents'])} "
                    f"| contas: {result['account_count']} "
                    f"| no {result['node_id']} (epoch {result['epoch']}, idx {result['applied_idx']})"
                )
        else:
            raise BankError(f"comando desconhecido: {args.comando}")

        if args.json:
            print(json.dumps(result, indent=2))
        elif label:
            _print_operation(label, result)
        return 0

    except (BankError, ValueError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
