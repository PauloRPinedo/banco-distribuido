"""Montagem da aplicacao FastAPI e do container de dependencias.

Tres grupos de rotas, separados de proposito:

- ``client_routes``   -- o que o cliente do banco usa (RF-01..RF-05, RF-14);
- ``internal_routes`` -- os RPCs entre servidores (nao sao API publica);
- ``admin_routes``    -- estado, metricas e injecao de falhas (RF-15, RF-16).
"""

from __future__ import annotations

import threading
import zlib
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..concurrency.locks import AccountLockManager
from ..config import ClusterConfig
from ..domain.errors import BankError, NotPrimary
from ..election.election import ElectionManager
from ..election.heartbeat import ElectionTimer, HeartbeatSender
from ..election.node_state import NodeState
from ..faults import FaultInjector
from ..observability.logging import StructuredLogger
from ..observability.metrics import Metrics
from ..peers import HttpPeerClient
from ..replication.log import ReplicatedLog
from ..replication.primary import PrimaryReplicator
from ..replication.replica import ReplicaApplier
from ..storage import snapshot as snapshot_module
from ..storage.recovery import recover


@dataclass
class ServerContext:
    """Tudo que as rotas precisam, montado uma vez no boot.

    Guardado em ``app.state.ctx``; as rotas o obtem por uma dependencia, para os
    testes poderem injetar um contexto falso.
    """

    config: ClusterConfig
    node_state: object
    store: object
    log: object
    primary: object
    replica: object
    election: object
    locks: object
    metrics: object
    logger: object
    faults: object
    heartbeat: object = None
    election_timer: object = None
    peers: object = None
    store_lock: object = None
    """Serializa a aplicacao ao estado e as leituras. Ver replication/primary.py."""

    # -- utilidades compartilhadas pelas rotas ------------------------------

    def primary_hint(self) -> str | None:
        """URL do ultimo primario conhecido, para o CLI seguir direto."""
        leader_id = self.node_state.leader_id
        if not leader_id:
            return None
        for node in self.config.nodes:
            if node.id == leader_id:
                return node.base_url
        return None

    def require_primary(self) -> None:
        """Recusa escritas que nao chegaram ao primario."""
        if not self.node_state.is_primary():
            raise NotPrimary(self.primary_hint())

    def read(self, function):
        """Executa uma leitura do estado sob o ``store_lock``.

        Sem isso, uma consulta feita no meio de ``apply`` de uma transferencia
        poderia enxergar o debito sem o credito -- dinheiro sumido aos olhos do
        cliente, violando RF-07.
        """
        with self.store_lock:
            return function()

    def status(self) -> dict:
        """Painel de saude, compartilhado por ``/admin/status`` e ``/internal/status``."""
        window = max(self.config.timing.replication_timeout_ms / 1000.0 * 6, 3.0)
        alive = self.heartbeat.alive_peers(window) if self.heartbeat else {}
        state = self.node_state.snapshot()
        return {
            "node_id": state["node_id"],
            "role": state["role"],
            "epoch": state["epoch"],
            "leader_id": state["leader_id"],
            "commit_index": self.log.commit_index,
            "applied_idx": self.store.last_applied_idx,
            "last_idx": self.log.last_idx,
            "peers_alive": alive,
            "quorum_size": self.config.quorum_size,
            "write_available": self.node_state.is_primary() and self.primary.has_write_quorum(),
            "faults_active": self.faults.active,
        }

    def maybe_snapshot(self) -> None:
        """Grava um snapshot a cada N entradas aplicadas, para encurtar o replay."""
        every = self.config.storage.snapshot_every_entries
        if every <= 0 or self.store.last_applied_idx == 0:
            return
        if self.store.last_applied_idx % every != 0:
            return
        snapshot_module.save(
            self.store, self.config.node_data_dir() / "snapshot.json", self.node_state.epoch
        )
        self.logger.event("snapshot_saved", applied_idx=self.store.last_applied_idx)


def build_context(config: ClusterConfig) -> ServerContext:
    """Recupera o estado do disco e monta todos os componentes do no.

    Ordem: recuperacao (snapshot + replay do WAL) -> estado do no -> log
    replicado -> replicador/aplicador -> eleicao. O no sempre sobe como REPLICA,
    mesmo que fosse primario antes de cair: quem decide quem manda e a eleicao.
    """
    data_dir = config.node_data_dir()
    logger = StructuredLogger(config.self_id, data_dir / "server.log")
    metrics = Metrics()
    faults = FaultInjector(seed=config.rng_seed)

    recovered = recover(
        data_dir,
        fsync_mode=config.storage.fsync_mode,
        group_commit_window_ms=config.storage.group_commit_window_ms,
    )
    node_state = NodeState(config.self_id, data_dir / "state.json")
    node_ids = [n.id for n in config.nodes]
    peer_ids = [n.id for n in config.peers]

    log = ReplicatedLog(recovered.wal, node_ids, config.self_id)
    log.force_commit(recovered.commit_index)

    locks = AccountLockManager()
    peers = HttpPeerClient(config.peers, faults=faults)
    timing = config.timing
    # Um unico lock de estado para o no inteiro: primario, replica e leituras.
    store_lock = threading.RLock()

    heartbeat = HeartbeatSender(
        node_state, None, peer_ids, timing.heartbeat_interval_ms / 1000.0
    )
    primary = PrimaryReplicator(
        node_state=node_state,
        log=log,
        store=recovered.store,
        locks=locks,
        peers=peers,
        peer_ids=peer_ids,
        replication_timeout_s=timing.replication_timeout_ms / 1000.0,
        heartbeat=heartbeat,
        logger=logger,
        metrics=metrics,
        store_lock=store_lock,
        heartbeat_interval_s=timing.heartbeat_interval_ms / 1000.0,
    )
    heartbeat.replicator = primary

    replica = ReplicaApplier(
        node_state, log, recovered.store, logger=logger, store_lock=store_lock
    )

    context = ServerContext(
        config=config,
        node_state=node_state,
        store=recovered.store,
        log=log,
        primary=primary,
        replica=replica,
        election=None,
        locks=locks,
        metrics=metrics,
        logger=logger,
        faults=faults,
        heartbeat=heartbeat,
        peers=peers,
        store_lock=store_lock,
    )
    primary.primary_hint_resolver = context.primary_hint

    def on_promoted() -> None:
        """Ao assumir: reiniciar o acompanhamento dos pares e confirmar o NOOP."""
        metrics.times_promoted += 1
        logger.bind(role="primary", epoch=node_state.epoch)
        log.reset_tracking()
        primary.commit_noop()

    election = ElectionManager(
        node_state=node_state,
        log=log,
        peers=peers,
        peer_ids=peer_ids,
        on_promoted=on_promoted,
        vote_timeout_s=timing.vote_timeout_ms / 1000.0,
        logger=logger,
    )
    context.election = election

    def on_election_timeout() -> None:
        metrics.elections_started += 1
        logger.event("heartbeat_missed", epoch=node_state.epoch)
        election.start_election()

    # A semente do timer e derivada por no (semente global + id), nunca a global
    # pura: com a mesma semente em todos, os tres sorteiam o **mesmo** timeout,
    # viram candidatos juntos, dividem os votos e a eleicao nunca converge --
    # exatamente o que a aleatoriedade deveria evitar. Derivar de forma estavel
    # mantem RNF-06: a mesma semente reproduz a mesma execucao.
    timer_seed = (
        None
        if config.rng_seed is None
        else config.rng_seed + zlib.crc32(config.self_id.encode("utf-8"))
    )
    election_timer = ElectionTimer(
        node_state,
        on_election_timeout,
        min_timeout_s=timing.election_timeout_min_ms / 1000.0,
        max_timeout_s=timing.election_timeout_max_ms / 1000.0,
        rng_seed=timer_seed,
    )
    replica.election_timer = election_timer
    context.election_timer = election_timer

    logger.bind(role=node_state.role.value, epoch=node_state.epoch)
    logger.event(
        "recovered",
        last_idx=recovered.last_idx,
        applied_idx=recovered.store.last_applied_idx,
        total_cents=recovered.store.total_cents(),
    )
    return context


def create_app(config: ClusterConfig) -> FastAPI:
    """Cria a aplicacao, registra as rotas e liga as threads de fundo."""
    from . import admin_routes, client_routes, internal_routes

    context = build_context(config)
    app = FastAPI(title=f"banco-distribuido [{config.self_id}]", version="0.1.0")
    app.state.ctx = context

    @app.exception_handler(BankError)
    def _bank_error(request: Request, exc: BankError) -> JSONResponse:
        """Traduz os erros de dominio para JSON estavel, com o codigo do erro."""
        body: dict[str, object] = {"error": exc.code, "message": str(exc)}
        hint = getattr(exc, "primary_hint", None)
        if hint:
            body["primary_hint"] = hint
        return JSONResponse(status_code=exc.http_status, content=body)

    app.include_router(client_routes.router)
    app.include_router(internal_routes.router)
    app.include_router(admin_routes.router)

    @app.on_event("startup")
    def _start() -> None:
        context.primary.start()
        context.heartbeat.start()
        context.election_timer.start()
        context.logger.event("server_started", bind=config.bind_host, port=config.self_node.port)

    @app.on_event("shutdown")
    def _stop() -> None:
        context.election_timer.stop()
        context.heartbeat.stop()
        context.primary.stop()
        context.peers.close()
        context.log.wal.close()
        context.logger.event("server_stopped")
        context.logger.close()

    return app
