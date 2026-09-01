"""Lado da replica: recebe AppendEntries, valida, grava e aplica.

Ordem das checagens (nao pode ser trocada):

1. ``epoch < meu_epoch``  -> rejeita e devolve o proprio epoch. E o fencing: um
   primario antigo que voltou a si descobre assim que perdeu o mandato.
2. ``epoch > meu_epoch``  -> adota o epoch novo e se rebaixa a replica.
3. Reinicia o temporizador de eleicao (a mensagem prova que ha um primario vivo).
4. Log matching em ``prev_idx``/``prev_epoch``: se nao bate, rejeita com uma dica
   de retrocesso.
5. Grava as entradas de forma duravel, truncando divergencias nao confirmadas.
6. Aplica ao estado ate ``leader_commit``.
7. Responde ACK com o ``match_idx``.

O ACK so sai depois do fsync do passo 5. Confirmar antes de estar duravel
quebraria RNF-02 exatamente no caso que o projeto se propoe a testar.
"""

from __future__ import annotations

from ..domain.accounts import AccountStore
from .log import ReplicatedLog
from .protocol import AppendAck, AppendEntries


class ReplicaApplier:
    """Trata AppendEntries e heartbeats recebidos."""

    def __init__(self, node_state: "object", log: ReplicatedLog, store: AccountStore) -> None:
        raise NotImplementedError

    def handle_append_entries(self, message: AppendEntries) -> AppendAck:
        """Executa a sequencia descrita no cabecalho do modulo."""
        raise NotImplementedError

    def apply_committed(self) -> int:
        """Aplica ao ``AccountStore`` tudo que ja esta confirmado e ainda nao aplicado.

        Returns:
            O novo ``last_applied_idx``.
        """
        raise NotImplementedError
