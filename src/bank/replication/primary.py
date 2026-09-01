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
"""

from __future__ import annotations

from typing import Protocol

from ..domain.accounts import AccountStore
from ..domain.operations import Operation, OperationResult
from .log import ReplicatedLog


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
    ) -> None:
        raise NotImplementedError

    def submit(self, operation: Operation) -> OperationResult:
        """Executa uma operacao de escrita ponta a ponta.

        Raises:
            NotPrimary: se este no deixou de ser primario (inclusive no meio).
            ReadOnlyMode: se a maioria dos nos esta inalcancavel.
            NoQuorum: se o quorum nao chegou no tempo.
            InsufficientFunds, UnknownAccount, ...: se a validacao reprovou.
        """
        raise NotImplementedError

    def replicate(self, up_to_idx: int, timeout_s: float) -> bool:
        """Envia entradas ate ``up_to_idx`` e espera ACK da maioria.

        Envia a todas as replicas em paralelo e retorna assim que a maioria
        responde, sem esperar a mais lenta. Um ACK negativo por divergencia faz
        retroceder o ponto de envio daquela replica e tentar de novo.
        """
        raise NotImplementedError

    def commit_noop(self) -> None:
        """Grava e confirma uma entrada NOOP no epoch atual.

        Chamado uma unica vez, logo apos a promocao, antes de aceitar escritas.
        E o que torna seguro confirmar entradas herdadas do primario anterior
        (ver ``ReplicatedLog.advance_commit``).
        """
        raise NotImplementedError

    def has_write_quorum(self) -> bool:
        """Se a maioria dos nos respondeu recentemente. Falso => modo somente leitura."""
        raise NotImplementedError
