"""Cliente HTTP para falar com os outros servidores.

Implementa o ``PeerClient`` esperado por ``PrimaryReplicator`` e
``ElectionManager``. Toda chamada tem timeout: uma requisicao sem prazo a um no
congelado prenderia a thread do primario para sempre, que e exatamente a falha
que o projeto se propoe a tolerar.

As falhas configuradas em ``FaultInjector`` sao aplicadas aqui, na saida, para
que o teste possa cortar a replicacao sem mexer na rede real.
"""

from __future__ import annotations

from .config import NodeConfig
from .replication.protocol import AppendAck, AppendEntries, RequestVote, VoteReply


class HttpPeerClient:
    """Transporte HTTP entre servidores, com pool de conexoes reaproveitado."""

    def __init__(self, peers: list[NodeConfig], faults: object | None = None) -> None:
        raise NotImplementedError

    def append_entries(self, node_id: str, message: AppendEntries, timeout_s: float) -> AppendAck | None:
        """Envia AppendEntries. Devolve ``None`` em erro de rede ou timeout.

        ``None`` significa "nao sei" -- nunca deve ser tratado como ACK negativo
        nem como positivo: a operacao simplesmente nao contou para o quorum.
        """
        raise NotImplementedError

    def request_vote(self, node_id: str, message: RequestVote, timeout_s: float) -> VoteReply | None:
        """Pede voto a um par. ``None`` em falha de rede."""
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class InMemoryPeerClient:
    """Transporte em memoria para os testes.

    Liga os nos por chamada direta, com perda e atraso sorteados por semente.
    Permite testar failover em milissegundos e de forma reproduzivel (RNF-06),
    sem subir processos nem esperar timeouts reais.
    """

    def __init__(self, nodes: dict[str, object], seed: int | None = None) -> None:
        raise NotImplementedError
