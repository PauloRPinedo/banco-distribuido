"""Eleicao de primario por maioria (RF-09).

Uma replica que fica sem noticias do primario incrementa o epoch, vota em si e
pede votos. Vira primario com a maioria dos votos -- 2 de 3, ou 2 de 2 num
cluster de dois.

O eleitor so concede o voto se **todas** as condicoes valerem:

1. ``epoch`` do candidato >= o seu (se for maior, ele adota o epoch antes de decidir);
2. ainda nao votou neste epoch (ou ja votou neste mesmo candidato);
3. o log do candidato esta **pelo menos tao atualizado** quanto o seu, comparando
   primeiro ``last_epoch`` e, em empate, ``last_idx``.

A condicao 3 e o que garante a corretude do failover: como toda operacao
confirmada esta no log da maioria, e todo vencedor precisa da maioria, o novo
primario tem obrigatoriamente todas as operacoes confirmadas. Nenhuma some.

Ao vencer, o novo primario envia um heartbeat imediato (para calar candidatos
concorrentes) e grava um NOOP no seu epoch antes de aceitar escritas.
"""

from __future__ import annotations

from .protocol_types import ElectionOutcome  # noqa: F401  (reexport para os testes)


class ElectionManager:
    """Conduz a candidatura e responde a pedidos de voto."""

    def __init__(
        self,
        node_state: "object",
        log: "object",
        peers: "object",
        peer_ids: list[str],
        on_promoted: "object",
        vote_timeout_s: float = 0.4,
    ) -> None:
        raise NotImplementedError

    def start_election(self) -> "ElectionOutcome":
        """Concorre a primario no proximo epoch.

        Pede votos em paralelo e decide assim que a maioria responde. Se durante a
        apuracao chegar um epoch maior, desiste e se rebaixa.
        """
        raise NotImplementedError

    def handle_request_vote(self, message: "object") -> "object":
        """Decide um pedido de voto conforme as tres condicoes do cabecalho.

        Persiste o voto **antes** de responder.
        """
        raise NotImplementedError
