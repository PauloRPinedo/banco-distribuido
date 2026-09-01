"""Configuracao do servidor e do cluster (RF-18).

Carregada de um JSON (``config/cluster.example.json`` e o modelo) e sobreposta
por variaveis de ambiente e argumentos de linha de comando. Todos os nos devem
receber a **mesma** lista de participantes: e dela que sai o tamanho da maioria.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class NodeConfig:
    """Um participante do cluster."""

    id: str
    host: str
    port: int

    @property
    def base_url(self) -> str:
        """``http://host:port`` -- endereco usado por pares e pelo CLI."""
        raise NotImplementedError


@dataclass(frozen=True)
class TimingConfig:
    """Temporizacoes do protocolo, em milissegundos.

    Restricao que precisa ser respeitada:
    ``heartbeat_interval << election_timeout_min < election_timeout_max``.
    Se o heartbeat nao for bem menor que o timeout, uma lentidao momentanea da
    rede dispara eleicoes desnecessarias e o cluster fica trocando de primario.
    """

    heartbeat_interval_ms: int = 150
    election_timeout_min_ms: int = 800
    election_timeout_max_ms: int = 1500
    replication_timeout_ms: int = 500
    vote_timeout_ms: int = 400


@dataclass(frozen=True)
class StorageConfig:
    """Persistencia local."""

    data_dir: Path = Path("./data")
    fsync_mode: str = "batch"
    """``always`` | ``batch`` | ``off`` -- ver storage/wal.py."""

    group_commit_window_ms: int = 5
    snapshot_every_entries: int = 1000


@dataclass(frozen=True)
class ClusterConfig:
    """Configuracao completa de um servidor dentro do cluster."""

    cluster_id: str
    self_id: str
    nodes: list[NodeConfig]
    timing: TimingConfig = field(default_factory=TimingConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    rng_seed: int | None = None
    """Semente do sorteio de timeouts e da injecao de falhas (RNF-06)."""

    @property
    def quorum_size(self) -> int:
        """Maioria simples: ``len(nodes) // 2 + 1``. 2 para 2 ou 3 nos."""
        raise NotImplementedError

    @property
    def peers(self) -> list[NodeConfig]:
        """Os outros nos, sem este."""
        raise NotImplementedError

    @property
    def self_node(self) -> NodeConfig:
        raise NotImplementedError

    def node_data_dir(self) -> Path:
        """``data_dir/<self_id>`` -- cada no tem o seu, mesmo na mesma maquina."""
        raise NotImplementedError

    @classmethod
    def load(cls, path: Path, self_id: str, **overrides: object) -> "ClusterConfig":
        """Le o JSON e monta a configuracao deste no.

        Raises:
            ValueError: se ``self_id`` nao esta na lista, se ha menos de 2 ou mais
                de 3 nos, se ha ids repetidos, ou se as temporizacoes violam a
                restricao documentada em ``TimingConfig``.
        """
        raise NotImplementedError
