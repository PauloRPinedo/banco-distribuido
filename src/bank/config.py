"""Configuracao do servidor e do cluster (RF-18).

Carregada de um JSON (``config/cluster.example.json`` e o modelo) e sobreposta
por variaveis de ambiente e argumentos de linha de comando. Todos os nos devem
receber a **mesma** lista de participantes: e dela que sai o tamanho da maioria.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
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
        return f"http://{self.host}:{self.port}"


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

    bind_host: str = "0.0.0.0"
    """Interface em que o uvicorn escuta. ``0.0.0.0`` e necessario para que outra
    maquina alcance este no; o endereco anunciado aos pares continua sendo o
    ``host`` da configuracao."""

    @property
    def quorum_size(self) -> int:
        """Maioria simples: ``len(nodes) // 2 + 1``. 2 para 2 ou 3 nos."""
        return len(self.nodes) // 2 + 1

    @property
    def peers(self) -> list[NodeConfig]:
        """Os outros nos, sem este."""
        return [n for n in self.nodes if n.id != self.self_id]

    @property
    def self_node(self) -> NodeConfig:
        for node in self.nodes:
            if node.id == self.self_id:
                return node
        raise ValueError(f"no {self.self_id} nao esta na lista do cluster")

    def node_data_dir(self) -> Path:
        """``data_dir/<self_id>`` -- cada no tem o seu, mesmo na mesma maquina."""
        return Path(self.storage.data_dir) / self.self_id

    @classmethod
    def load(cls, path: Path, self_id: str, **overrides: object) -> "ClusterConfig":
        """Le o JSON e monta a configuracao deste no.

        Raises:
            ValueError: se ``self_id`` nao esta na lista, se ha menos de 2 ou mais
                de 3 nos, se ha ids repetidos, ou se as temporizacoes violam a
                restricao documentada em ``TimingConfig``.
        """
        raw = json.loads(Path(path).read_text(encoding="utf-8"))

        nodes = [
            NodeConfig(id=str(n["id"]), host=str(n["host"]), port=int(n["port"]))
            for n in raw["nodes"]
        ]
        if not 2 <= len(nodes) <= 3:
            raise ValueError(f"o cluster deve ter 2 ou 3 nos, veio {len(nodes)}")
        ids = [n.id for n in nodes]
        if len(set(ids)) != len(ids):
            raise ValueError(f"ids repetidos na lista de nos: {ids}")
        if self_id not in ids:
            raise ValueError(f"no {self_id} nao esta na lista do cluster: {ids}")

        timing = TimingConfig(**{**TimingConfig().__dict__, **(raw.get("timing") or {})})
        raw_storage = dict(raw.get("storage") or {})
        if "data_dir" in raw_storage:
            raw_storage["data_dir"] = Path(raw_storage["data_dir"])
        storage = StorageConfig(**{**StorageConfig().__dict__, **raw_storage})

        config = cls(
            cluster_id=str(raw.get("cluster_id", "banco")),
            self_id=self_id,
            nodes=nodes,
            timing=timing,
            storage=storage,
            rng_seed=raw.get("rng_seed"),
        )

        # Sobreposicoes da linha de comando.
        clean = {k: v for k, v in overrides.items() if v is not None}
        if "data_dir" in clean:
            config = replace(
                config, storage=replace(config.storage, data_dir=Path(clean.pop("data_dir")))
            )
        if "fsync_mode" in clean:
            config = replace(
                config, storage=replace(config.storage, fsync_mode=str(clean.pop("fsync_mode")))
            )
        if clean:
            config = replace(config, **clean)

        config.validate()
        return config

    def validate(self) -> None:
        """Confere as restricoes que, se violadas, produzem falhas dificeis de diagnosticar."""
        t = self.timing
        if not t.heartbeat_interval_ms < t.election_timeout_min_ms < t.election_timeout_max_ms:
            raise ValueError(
                "as temporizacoes devem satisfazer "
                "heartbeat_interval < election_timeout_min < election_timeout_max; "
                f"veio {t.heartbeat_interval_ms} / {t.election_timeout_min_ms} / "
                f"{t.election_timeout_max_ms}"
            )
        if t.election_timeout_min_ms < 3 * t.heartbeat_interval_ms:
            raise ValueError(
                "election_timeout_min deve ser pelo menos 3x o heartbeat_interval, "
                "senao uma lentidao momentanea derruba um primario saudavel"
            )
        if self.storage.fsync_mode not in ("always", "batch", "off"):
            raise ValueError(f"fsync_mode invalido: {self.storage.fsync_mode}")
