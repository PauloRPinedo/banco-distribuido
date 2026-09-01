"""Heartbeat: o primario prova que esta vivo; as replicas cronometram o silencio.

O heartbeat e um ``AppendEntries`` com ``entries`` vazio, enviado a cada
``heartbeat_interval_ms`` (150 ms por padrao). Reaproveitar o RPC de replicacao
garante que o heartbeat carregue sempre ``epoch`` e ``leader_commit`` corretos.

O timeout de eleicao e sorteado a cada rodada dentro de
``[election_timeout_min_ms, election_timeout_max_ms]``. A aleatoriedade e o que
evita que as duas replicas virem candidatas ao mesmo tempo, dividam os votos e
travem a eleicao. O sorteio usa a semente da configuracao, para os testes de
failover serem reproduziveis (RNF-06).
"""

from __future__ import annotations

import random
import threading
import time
from typing import Callable


class HeartbeatSender:
    """Thread do primario: envia heartbeats enquanto o no for PRIMARY."""

    def __init__(
        self,
        node_state: "object",
        replicator: "object",
        peer_ids: list[str],
        interval_s: float,
    ) -> None:
        self.node_state = node_state
        self.replicator = replicator
        self.peer_ids = list(peer_ids)
        self.interval_s = interval_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._last_contact: dict[str, float] = {n: 0.0 for n in peer_ids}

    def _run(self) -> None:
        while not self._stop.wait(self.interval_s):
            try:
                if self.node_state.is_primary():
                    self.replicator.send_heartbeats()
            except Exception:  # noqa: BLE001 - um heartbeat falho nao pode matar a thread
                continue

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="heartbeat", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def notify_activity(self, node_id: str) -> None:
        """Marca contato bem-sucedido com um par.

        Alimenta ``PrimaryReplicator.has_write_quorum``: se a maioria nao responde
        ha mais de um timeout de eleicao, o primario entra em somente leitura em
        vez de seguir aceitando escritas que nunca serao confirmadas.
        """
        with self._lock:
            self._last_contact[node_id] = time.monotonic()

    def alive_peers(self, within_s: float) -> dict[str, bool]:
        """Quais pares responderam dentro da janela dada."""
        now = time.monotonic()
        with self._lock:
            return {n: (now - t) <= within_s for n, t in self._last_contact.items()}


class ElectionTimer:
    """Thread da replica: dispara a candidatura apos silencio prolongado."""

    def __init__(
        self,
        node_state: "object",
        on_timeout: Callable[[], None],
        min_timeout_s: float,
        max_timeout_s: float,
        rng_seed: int | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self.node_state = node_state
        self.on_timeout = on_timeout
        self.min_timeout_s = min_timeout_s
        self.max_timeout_s = max_timeout_s
        self._rng = random.Random(rng_seed)
        self._deadline = 0.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.reset()

    def _sample(self) -> float:
        return self._rng.uniform(self.min_timeout_s, self.max_timeout_s)

    def reset(self) -> None:
        """Reinicia a contagem. Chamado a cada mensagem valida do primario."""
        with self._lock:
            self._deadline = time.monotonic() + self._sample()

    def _run(self) -> None:
        while not self._stop.wait(0.05):
            with self._lock:
                expired = time.monotonic() >= self._deadline
            if not expired:
                continue
            # Um primario nao concorre contra si mesmo.
            if self.node_state.is_primary():
                self.reset()
                continue
            self.reset()
            try:
                self.on_timeout()
            except Exception:  # noqa: BLE001 - uma eleicao falha nao pode matar a thread
                continue

    def start(self) -> None:
        if self._thread is not None:
            return
        self.reset()
        self._thread = threading.Thread(target=self._run, name="election-timer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
