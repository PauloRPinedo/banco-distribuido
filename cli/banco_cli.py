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


class BankClient:
    """Cliente com descoberta de primario e retentativa idempotente."""

    def __init__(self, servers: list[str], timeout_s: float = 2.0, max_retries: int = 5) -> None:
        raise NotImplementedError

    def _call(self, method: str, path: str, body: dict | None = None, op_id: str | None = None) -> dict:
        """Executa a requisicao seguindo o primario e repetindo com o mesmo ``op_id``.

        Backoff crescente entre tentativas, para nao martelar o cluster enquanto
        uma eleicao acontece.
        """
        raise NotImplementedError

    def create_account(self, account_id: str, initial_cents: int) -> dict: ...
    def get_balance(self, account_id: str) -> dict: ...
    def deposit(self, account_id: str, amount_cents: int) -> dict: ...
    def withdraw(self, account_id: str, amount_cents: int) -> dict: ...
    def transfer(self, from_account: str, to_account: str, amount_cents: int) -> dict: ...
    def statement(self, account_id: str, limit: int = 50) -> dict: ...
    def audit(self) -> dict: ...
    def cluster_status(self) -> list[dict]:
        """Consulta ``/admin/status`` em todos os servidores, inclusive os mortos."""
        ...


def build_parser() -> argparse.ArgumentParser:
    """Monta os subcomandos listados no cabecalho do modulo."""
    raise NotImplementedError


def main(argv: list[str] | None = None) -> int:
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
