"""Injecao de falhas controlada (RF-16).

Permite reproduzir em teste os cenarios que interessam sem depender de sorte:
perda de mensagens de replicacao, lentidao e queda do processo. Toda decisao
aleatoria sai de um ``random.Random`` com semente da configuracao, entao a mesma
semente reproduz exatamente a mesma execucao (RNF-06).

Configurado em tempo de execucao por ``POST /admin/fault``:

``{"drop_replication": 0.3, "delay_ms": 500, "reject_votes": false, "seed": 42}``

Fica desligado por padrao. Um servidor de producao nunca sairia com isto ligado;
aqui e uma ferramenta de teste, e ``/admin/status`` mostra quando esta ativa.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class FaultConfig:
    """Falhas ativas neste no."""

    drop_replication: float = 0.0
    """Probabilidade [0,1] de descartar um AppendEntries de saida."""

    delay_ms: int = 0
    """Atraso artificial antes de responder a um RPC interno."""

    reject_votes: bool = False
    """Recusar todo pedido de voto -- simula um no isolado para a eleicao."""

    freeze: bool = False
    """Parar de responder sem morrer -- o caso que distingue um primario lento de
    um primario morto, e que so o fencing por epoch resolve com seguranca."""


class FaultInjector:
    """Aplica as falhas configuradas nos pontos de I/O."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self.config = FaultConfig()

    def configure(self, **fields: object) -> FaultConfig:
        """Atualiza a configuracao em tempo de execucao e devolve a nova."""
        raise NotImplementedError

    def should_drop_replication(self) -> bool:
        """Sorteia se a proxima mensagem de replicacao sera descartada."""
        raise NotImplementedError

    def maybe_delay(self) -> None:
        """Aplica o atraso configurado, se houver."""
        raise NotImplementedError

    def is_frozen(self) -> bool:
        raise NotImplementedError
