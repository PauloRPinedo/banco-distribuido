"""Caminho de escrita do primario -- onde a promessa "nao perde dinheiro" e cumprida.

A sequencia de uma escrita, em ordem e sem atalhos:

1. Deduplicar por ``op_id``: se ja foi aplicada, devolver o resultado guardado.
2. Tomar os locks das contas envolvidas, em ordem crescente de id.
3. Validar contra o estado atual (conta existe, saldo suficiente).
4. Gravar a entrada no WAL local, de forma duravel.
5. Enviar AppendEntries em paralelo as replicas e esperar ACK da **maioria**
   (o proprio no conta): 2 de 3, ou 2 de 2 num cluster de dois.
6. Avancar ``commit_index``, aplicar ao ``AccountStore``, soltar os locks e so
   entao responder 200 ao cliente.

Os passos 3 a 6 acontecem com os locks das contas tomados, entao duas operacoes
sobre a mesma conta nunca se sobrepoem (RF-08). Operacoes sobre contas distintas
seguem em paralelo -- e por isso os locks sao por conta e nao globais.

Se o quorum nao chega no tempo, a resposta e ``NoQuorum`` (503) e a entrada fica
gravada porem **nao confirmada**. Nunca se responde sucesso antes do quorum: e
isso que faz uma operacao confirmada sobreviver a queda do primario (RF-10, RNF-02).

Dois detalhes de concorrencia que nao sao opcionais:

**Lock de estado.** Os locks por conta protegem *quais* operacoes podem correr em
paralelo, mas a aplicacao ao ``AccountStore`` mexe em estruturas compartilhadas
(``last_applied_idx``, ``history``, ``applied``) e por isso e serializada por um
lock proprio, o ``store_lock``. Sem ele, duas threads segurando contas diferentes
aplicariam ao mesmo tempo e corromperiam a ordem do log. As leituras tambem o
tomam, senao uma consulta poderia enxergar uma transferencia pela metade (RF-07).

**Replicacao em segundo plano.** Uma thread por replica envia continuamente o que
estiver pendente; ``submit`` apenas acorda essas threads e espera o
``commit_index`` alcancar o seu indice. Assim N escritas concorrentes viram **um**
AppendEntries com N entradas e **um** fsync na replica, em vez de N idas e voltas
-- e o que torna RNF-04 alcancavel.
"""

from __future__ import annotations

import threading
import time
from typing import Protocol

from ..domain.accounts import AccountStore
from ..domain.errors import NoQuorum, NotPrimary, ReadOnlyMode
from ..domain.operations import Operation, OperationResult, OpType
from .log import ReplicatedLog
from .protocol import AppendEntries


class PeerClient(Protocol):
    """Transporte para falar com um par.

    Abstraido para que os testes possam injetar um transporte em memoria, com
    atraso e perda controlados por semente, sem subir processos (RNF-06).
    """

    def append_entries(self, node_id: str, message: "object", timeout_s: float) -> "object | None":
        """Envia AppendEntries; devolve ``AppendAck`` ou ``None`` se falhou/estourou."""
        ...


class PrimaryReplicator:
    """Executa escritas com confirmacao por quorum."""

    def __init__(
        self,
        node_state: "object",
        log: ReplicatedLog,
        store: AccountStore,
        locks: "object",
        peers: PeerClient,
        peer_ids: list[str],
        replication_timeout_s: float = 0.5,
        heartbeat: "object | None" = None,
        logger: "object | None" = None,
        metrics: "object | None" = None,
        store_lock: threading.RLock | None = None,
        heartbeat_interval_s: float = 0.15,
    ) -> None:
        self.node_state = node_state
        self.log = log
        self.store = store
        self.locks = locks
        self.peers = peers
        self.peer_ids = list(peer_ids)
        self.replication_timeout_s = replication_timeout_s
        self.heartbeat = heartbeat
        self.logger = logger
        self.metrics = metrics
        self.heartbeat_interval_s = heartbeat_interval_s
        self.quorum = (len(peer_ids) + 1) // 2 + 1

        # Serializa a atribuicao de idx: o log tem de crescer em ordem.
        self._append_lock = threading.Lock()
        # Serializa a aplicacao ao estado e as leituras (ver cabecalho do modulo).
        self.store_lock = store_lock if store_lock is not None else threading.RLock()

        self._commit_cond = threading.Condition()
        self._wake = {node_id: threading.Event() for node_id in self.peer_ids}
        self._threads: list[threading.Thread] = []
        self._running = False

    def _log_event(self, name: str, **fields) -> None:
        if self.logger is not None:
            self.logger.event(name, **fields)

    # -- threads de replicacao ---------------------------------------------

    def start(self) -> None:
        """Sobe uma thread por replica. Elas ficam ociosas enquanto este no nao
        for primario, e acordam a cada escrita ou a cada intervalo de heartbeat."""
        if self._running:
            return
        self._running = True
        for node_id in self.peer_ids:
            thread = threading.Thread(
                target=self._peer_loop, args=(node_id,), name=f"repl-{node_id}", daemon=True
            )
            thread.start()
            self._threads.append(thread)

    def stop(self) -> None:
        self._running = False
        for event in self._wake.values():
            event.set()
        for thread in self._threads:
            thread.join(timeout=2.0)
        self._threads.clear()

    def _peer_loop(self, node_id: str) -> None:
        while self._running:
            # Acorda por escrita nova ou pelo intervalo de heartbeat, o que vier antes.
            self._wake[node_id].wait(timeout=self.heartbeat_interval_s)
            self._wake[node_id].clear()
            if not self._running:
                return
            if not self.node_state.is_primary():
                continue
            try:
                self._push_once(node_id)
            except Exception:  # noqa: BLE001 - falha de um par nao derruba o primario
                continue

    def _wake_all(self) -> None:
        for event in self._wake.values():
            event.set()

    def _push_once(self, node_id: str) -> bool:
        """Envia a cauda pendente a uma replica e processa o ACK.

        Com ``entries`` vazio isto e exatamente o heartbeat: o mesmo caminho de
        codigo serve para replicar e para provar que o primario esta vivo.
        """
        epoch = self.node_state.epoch
        prev_idx, prev_epoch, entries = self.log.next_batch_for(node_id)
        message = AppendEntries(
            epoch=epoch,
            leader_id=self.node_state.node_id,
            prev_idx=prev_idx,
            prev_epoch=prev_epoch,
            entries=entries,
            leader_commit=self.log.commit_index,
        )
        started = time.monotonic()
        ack = self.peers.append_entries(node_id, message, self.replication_timeout_s)
        if ack is None:
            return False  # "nao sei": nem ACK positivo nem negativo

        if self.heartbeat is not None:
            self.heartbeat.notify_activity(node_id)
        if self.metrics is not None and entries:
            self.metrics.replication_latency.observe(time.monotonic() - started)

        if ack.epoch > epoch:
            # Fencing: o cluster seguiu adiante sem este no.
            self.node_state.step_down(ack.epoch)
            if self.metrics is not None:
                self.metrics.times_stepped_down += 1
            self._log_event("stepped_down", epoch=ack.epoch, reason="append_ack")
            with self._commit_cond:
                self._commit_cond.notify_all()
            return False

        if ack.success:
            self.log.record_match(node_id, ack.match_idx)
            self.log.advance_commit(epoch)
            self.apply_committed()
            with self._commit_cond:
                self._commit_cond.notify_all()
            return True

        # Divergencia: retroceder e tentar de novo ja na proxima volta.
        self.log.back_off(node_id, ack.match_idx)
        self._wake[node_id].set()
        return False

    # -- aplicacao ----------------------------------------------------------

    def apply_committed(self) -> int:
        """Aplica ao estado tudo que esta confirmado e ainda nao aplicado.

        Serializada pelo ``store_lock``: e a unica porta de entrada para mudar
        saldos neste no enquanto ele e primario.
        """
        with self.store_lock:
            while self.store.last_applied_idx < self.log.commit_index:
                entry = self.log.wal.entry_at(self.store.last_applied_idx + 1)
                if entry is None:
                    break
                self.store.apply(entry)
            return self.store.last_applied_idx

    # -- escrita ------------------------------------------------------------

    def submit(self, operation: Operation) -> OperationResult:
        """Executa uma operacao de escrita ponta a ponta.

        Raises:
            NotPrimary: se este no deixou de ser primario (inclusive no meio).
            ReadOnlyMode: se a maioria dos nos esta inalcancavel.
            NoQuorum: se o quorum nao chegou no tempo.
            InsufficientFunds, UnknownAccount, ...: se a validacao reprovou.
        """
        started = time.monotonic()
        if not self.node_state.is_primary():
            raise NotPrimary(self._primary_hint())

        # 1. Idempotencia: repetir apos um failover nao pode mover dinheiro duas vezes.
        with self.store_lock:
            previous = self.store.applied.get(operation.op_id)
        if previous is not None:
            self._log_event("op_deduplicated", op_id=operation.op_id)
            return previous

        operation.validate()

        # 2. Locks das contas, em ordem crescente (anti-deadlock).
        with self.locks.acquire(operation.touched_accounts()):
            if not self.node_state.is_primary():
                raise NotPrimary(self._primary_hint())

            with self.store_lock:
                previous = self.store.applied.get(operation.op_id)
                if previous is not None:
                    return previous
                # 3. Validar antes de gravar: nao se replica o que sera rejeitado.
                self.store.check(operation)

            with self._append_lock:
                epoch = self.node_state.epoch
                # 4a. Atribuir o idx e escrever. Rapido: so buffer, sem disco.
                entry = self.log.append_local_buffered(operation, epoch)
            # 4b. Esperar o fsync **fora** do lock de ordenacao, para que as
            #     escritas concorrentes dividam um unico fsync (group commit).
            self.log.wait_durable(entry.idx)
            self._log_event("entry_appended", idx=entry.idx, epoch=epoch, op_id=operation.op_id)

            # 5. Replicar e esperar a maioria.
            if not self.replicate(entry.idx, self.replication_timeout_s):
                if self.metrics is not None:
                    self.metrics.ops_no_quorum += 1
                self._log_event("no_quorum", idx=entry.idx, op_id=operation.op_id)
                if not self.node_state.is_primary():
                    raise NotPrimary(self._primary_hint())
                raise NoQuorum(
                    f"operacao {operation.op_id} gravada em idx={entry.idx} mas nao confirmada"
                )

            # 6. Confirmar e aplicar antes de soltar os locks: quem pegar estas
            #    contas em seguida tem de enxergar esta operacao ja aplicada.
            self.apply_committed()
            with self.store_lock:
                result = self.store.applied.get(operation.op_id)
            self._log_event("commit", idx=entry.idx, op_id=operation.op_id)

        if result is None:
            raise NoQuorum(f"operacao {operation.op_id} confirmada mas nao aplicada")
        if self.metrics is not None:
            self.metrics.ops_ok += 1
            self.metrics.write_latency.observe(time.monotonic() - started)
        return result

    def replicate(self, up_to_idx: int, timeout_s: float) -> bool:
        """Acorda as threads de replicacao e espera o commit alcancar ``up_to_idx``.

        Nao envia nada por conta propria: quem envia sao as threads por par, que
        agrupam naturalmente as escritas concorrentes em um unico AppendEntries.
        """
        if not self.peer_ids:
            # Cluster de um no: o proprio primario ja e a maioria.
            self.log.advance_commit(self.node_state.epoch)
            return True

        deadline = time.monotonic() + timeout_s
        self._wake_all()
        with self._commit_cond:
            while self.log.commit_index < up_to_idx:
                if not self.node_state.is_primary():
                    return False
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._commit_cond.wait(remaining)
        return True

    def send_heartbeats(self) -> None:
        """Compatibilidade: acorda as threads de replicacao.

        O heartbeat de verdade sai do proprio ``_peer_loop``, que acorda sozinho
        a cada ``heartbeat_interval_s`` mesmo sem escritas pendentes.
        """
        self._wake_all()

    def commit_noop(self) -> None:
        """Grava e confirma uma entrada NOOP no epoch atual.

        Chamado uma unica vez, logo apos a promocao, antes de aceitar escritas.
        E o que torna seguro confirmar entradas herdadas do primario anterior
        (ver ``ReplicatedLog.advance_commit``).
        """
        import uuid

        with self._append_lock:
            epoch = self.node_state.epoch
            entry = self.log.append_local_buffered(
                Operation(f"noop-{uuid.uuid4()}", OpType.NOOP), epoch
            )
        self.log.wait_durable(entry.idx)
        self._log_event("noop_appended", idx=entry.idx, epoch=epoch)
        if self.replicate(entry.idx, max(self.replication_timeout_s * 4, 2.0)):
            self.apply_committed()
            self._log_event("noop_committed", idx=entry.idx, epoch=epoch)

    def has_write_quorum(self) -> bool:
        """Se a maioria dos nos respondeu recentemente. Falso => modo somente leitura."""
        if not self.peer_ids or self.heartbeat is None:
            return True
        window = max(self.replication_timeout_s * 6, 3.0)
        alive = sum(1 for ok in self.heartbeat.alive_peers(window).values() if ok)
        return alive + 1 >= self.quorum

    def ensure_writable(self) -> None:
        """Levanta se este no nao pode aceitar escritas agora."""
        if not self.node_state.is_primary():
            raise NotPrimary(self._primary_hint())
        if not self.has_write_quorum():
            raise ReadOnlyMode("maioria dos servidores inalcancavel; somente leitura")

    def _primary_hint(self) -> str | None:
        return getattr(self, "primary_hint_resolver", lambda: None)()
