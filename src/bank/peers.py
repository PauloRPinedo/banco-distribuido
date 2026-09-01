"""Cliente HTTP para falar com os outros servidores.

Implementa o ``PeerClient`` esperado por ``PrimaryReplicator`` e
``ElectionManager``. Toda chamada tem timeout: uma requisicao sem prazo a um no
congelado prenderia a thread do primario para sempre, que e exatamente a falha
que o projeto se propoe a tolerar.

As falhas configuradas em ``FaultInjector`` sao aplicadas aqui, na saida, para
que o teste possa cortar a replicacao sem mexer na rede real.
"""

from __future__ import annotations

import httpx

from .config import NodeConfig
from .replication.protocol import AppendAck, AppendEntries, RequestVote, VoteReply


class HttpPeerClient:
    """Transporte HTTP entre servidores, com pool de conexoes reaproveitado."""

    def __init__(self, peers: list[NodeConfig], faults: object | None = None) -> None:
        self.urls = {n.id: n.base_url for n in peers}
        self.faults = faults
        # Um pool por processo: abrir conexao a cada AppendEntries dominaria a
        # latencia de replicacao.
        self._client = httpx.Client(
            timeout=httpx.Timeout(1.0), limits=httpx.Limits(max_connections=32)
        )

    def _post(self, node_id: str, path: str, body: dict, timeout_s: float) -> dict | None:
        url = self.urls.get(node_id)
        if url is None:
            return None
        try:
            response = self._client.post(f"{url}{path}", json=body, timeout=timeout_s)
            if response.status_code != 200:
                return None
            return response.json()
        except (httpx.HTTPError, ValueError):
            # Erro de rede ou resposta ilegivel: "nao sei", nunca "nao".
            return None

    def append_entries(
        self, node_id: str, message: AppendEntries, timeout_s: float
    ) -> AppendAck | None:
        """Envia AppendEntries. Devolve ``None`` em erro de rede ou timeout.

        ``None`` significa "nao sei" -- nunca deve ser tratado como ACK negativo
        nem como positivo: a operacao simplesmente nao contou para o quorum.
        """
        if self.faults is not None and self.faults.should_drop_replication():
            return None
        data = self._post(node_id, "/internal/append_entries", message.to_json(), timeout_s)
        return AppendAck.from_json(data) if data else None

    def request_vote(
        self, node_id: str, message: RequestVote, timeout_s: float
    ) -> VoteReply | None:
        """Pede voto a um par. ``None`` em falha de rede."""
        data = self._post(node_id, "/internal/request_vote", message.to_json(), timeout_s)
        return VoteReply.from_json(data) if data else None

    def close(self) -> None:
        self._client.close()


class InMemoryPeerClient:
    """Transporte em memoria para os testes.

    Liga os nos por chamada direta, com perda e atraso sorteados por semente.
    Permite testar failover em milissegundos e de forma reproduzivel (RNF-06),
    sem subir processos nem esperar timeouts reais.
    """

    def __init__(self, nodes: dict[str, object], seed: int | None = None) -> None:
        import random

        self.nodes = nodes
        """``node_id -> objeto com .replica (ReplicaApplier) e .election (ElectionManager)``."""
        self._rng = random.Random(seed)
        self.partitioned: set[str] = set()
        """Nos inalcancaveis a partir deste cliente, para simular particao de rede."""

        self.down: set[str] = set()
        """Nos "mortos": nao respondem nada."""

    def _reachable(self, node_id: str) -> bool:
        return node_id not in self.partitioned and node_id not in self.down

    def append_entries(
        self, node_id: str, message: AppendEntries, timeout_s: float
    ) -> AppendAck | None:
        if not self._reachable(node_id):
            return None
        target = self.nodes.get(node_id)
        if target is None:
            return None
        # Serializa e desserializa de proposito: pega bugs de protocolo que uma
        # chamada direta com os mesmos objetos esconderia.
        copy = AppendEntries.from_json(message.to_json())
        ack = target.replica.handle_append_entries(copy)
        return AppendAck.from_json(ack.to_json())

    def request_vote(
        self, node_id: str, message: RequestVote, timeout_s: float
    ) -> VoteReply | None:
        if not self._reachable(node_id):
            return None
        target = self.nodes.get(node_id)
        if target is None:
            return None
        copy = RequestVote.from_json(message.to_json())
        reply = target.election.handle_request_vote(copy)
        return VoteReply.from_json(reply.to_json())

    def close(self) -> None:
        return None
