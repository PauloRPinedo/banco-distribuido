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

import threading
from typing import Callable


class HeartbeatSender:
    """Thread do primario: envia heartbeats enquanto o no for PRIMARY."""

    def __init__(self, node_state: "object", peers: "object", peer_ids: list[str], interval_s: float) -> None:
        raise NotImplementedError

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def notify_activity(self, node_id: str) -> None:
        """Marca contato bem-sucedido com um par.

        Alimenta ``PrimaryReplicator.has_write_quorum``: se a maioria nao responde
        ha mais de um timeout de eleicao, o primario entra em somente leitura em
        vez de seguir aceitando escritas que nunca serao confirmadas.
        """
        raise NotImplementedError


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
        raise NotImplementedError

    def reset(self) -> None:
        """Reinicia a contagem. Chamado a cada mensagem valida do primario."""
        raise NotImplementedError

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError
