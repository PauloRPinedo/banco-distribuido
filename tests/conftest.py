"""Fixtures compartilhadas.

O ``live_cluster`` sobe **processos de verdade** em portas livres. E mais lento
que ligar os nos em memoria, mas e a unica forma honesta de exercitar o que o
projeto promete: ``SIGKILL`` no primario, reinicio e recuperacao pelo disco.
Um mock nunca provaria que o fsync aconteceu antes do ACK.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest

SEED = 42
"""Semente fixa: a mesma execucao produz o mesmo resultado (RNF-06)."""

RAIZ = Path(__file__).resolve().parent.parent
PYTHON = str(RAIZ / ".venv" / "bin" / "python")
if not Path(PYTHON).exists():
    PYTHON = sys.executable


def porta_livre() -> int:
    """Porta efemera livre, para os testes nao colidirem com um cluster manual."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@dataclass
class No:
    id: str
    port: int
    process: subprocess.Popen
    data_dir: Path

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def vivo(self) -> bool:
        return self.process.poll() is None

    def status(self, timeout: float = 1.0) -> dict | None:
        try:
            return httpx.get(f"{self.url}/admin/status", timeout=timeout).json()
        except (httpx.HTTPError, ValueError):
            return None

    def matar(self) -> None:
        """SIGKILL: sem chance de flush. A corretude tem de vir do fsync."""
        if self.vivo():
            os.kill(self.process.pid, signal.SIGKILL)
            self.process.wait(timeout=10)


class Cluster:
    """Tres nos reais, com os atalhos que os testes de failover precisam."""

    def __init__(self, config_path: Path, data_dir: Path, nodes: dict[str, int]) -> None:
        self.config_path = config_path
        self.data_dir = data_dir
        self.ports = nodes
        self.nodes: dict[str, No] = {}

    def iniciar(self, node_id: str) -> No:
        destino = self.data_dir
        processo = subprocess.Popen(
            [
                PYTHON, "-m", "bank.server",
                "--config", str(self.config_path),
                "--id", node_id,
                "--data-dir", str(destino),
                "--seed", str(SEED),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(RAIZ),
        )
        no = No(node_id, self.ports[node_id], processo, destino / node_id)
        self.nodes[node_id] = no
        return no

    def iniciar_todos(self) -> None:
        for node_id in self.ports:
            self.iniciar(node_id)

    @property
    def urls(self) -> list[str]:
        return [n.url for n in self.nodes.values()]

    def vivos(self) -> list[No]:
        return [n for n in self.nodes.values() if n.vivo()]

    def esperar_primario(self, timeout: float = 25.0) -> No:
        """Espera algum no se declarar primario **e** ter confirmado o seu NOOP.

        Sem esperar o NOOP, uma escrita logo apos a eleicao poderia chegar antes
        de o novo primario estar pronto para confirmar entradas herdadas.
        """
        limite = time.monotonic() + timeout
        while time.monotonic() < limite:
            for no in self.vivos():
                estado = no.status()
                if estado and estado["role"] == "primary" and estado["write_available"]:
                    return no
            time.sleep(0.2)
        raise AssertionError(f"nenhum primario em {timeout}s: {[n.status() for n in self.vivos()]}")

    def auditoria(self) -> dict[str, int]:
        """Total em circulacao em cada no vivo."""
        totais = {}
        for no in self.vivos():
            try:
                totais[no.id] = httpx.get(f"{no.url}/audit", timeout=2.0).json()["total_cents"]
            except (httpx.HTTPError, ValueError, KeyError):
                pass
        return totais

    def esperar_convergencia(self, timeout: float = 20.0) -> dict[str, int]:
        """Espera todos os nos vivos concordarem no total e no indice aplicado."""
        limite = time.monotonic() + timeout
        ultimo: dict = {}
        while time.monotonic() < limite:
            estados = {n.id: n.status() for n in self.vivos()}
            if all(estados.values()):
                indices = {e["applied_idx"] for e in estados.values()}
                if len(indices) == 1:
                    return self.auditoria()
                ultimo = estados
            time.sleep(0.3)
        raise AssertionError(f"nos nao convergiram em {timeout}s: {ultimo}")

    def parar(self) -> None:
        for no in self.nodes.values():
            if no.vivo():
                no.process.terminate()
        for no in self.nodes.values():
            try:
                no.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                no.matar()


@pytest.fixture
def live_cluster(tmp_path):
    """Cluster de 3 processos reais em portas livres, derrubado ao fim do teste."""
    portas = {"A": porta_livre(), "B": porta_livre(), "C": porta_livre()}
    config = {
        "cluster_id": "teste",
        "nodes": [{"id": i, "host": "127.0.0.1", "port": p} for i, p in portas.items()],
        # Temporizacoes curtas: o teste nao pode esperar segundos por failover,
        # mas a relacao heartbeat << timeout continua respeitada.
        "timing": {
            "heartbeat_interval_ms": 60,
            "election_timeout_min_ms": 300,
            "election_timeout_max_ms": 700,
            "replication_timeout_ms": 800,
            "vote_timeout_ms": 400,
        },
        "storage": {"data_dir": str(tmp_path / "data"), "fsync_mode": "always"},
    }
    config_path = tmp_path / "cluster.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    cluster = Cluster(config_path, tmp_path / "data", portas)
    cluster.iniciar_todos()
    try:
        cluster.esperar_primario()
        yield cluster
    finally:
        cluster.parar()


@pytest.fixture
def banco(live_cluster):
    """Cliente apontado para o cluster do teste."""
    sys.path.insert(0, str(RAIZ / "cli"))
    from banco_cli import BankClient

    cliente = BankClient(live_cluster.urls, timeout_s=5.0, max_retries=8)
    try:
        yield cliente
    finally:
        cliente.close()
