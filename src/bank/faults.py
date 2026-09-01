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
import threading
import time
from dataclasses import asdict, dataclass, replace


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
        self._lock = threading.Lock()
        self.config = FaultConfig()

    def configure(self, **fields: object) -> FaultConfig:
        """Atualiza a configuracao em tempo de execucao e devolve a nova."""
        with self._lock:
            seed = fields.pop("seed", None)
            if seed is not None:
                self._rng = random.Random(int(seed))
            clean = {k: v for k, v in fields.items() if v is not None}
            unknown = set(clean) - set(asdict(self.config))
            if unknown:
                raise ValueError(f"campos de falha desconhecidos: {sorted(unknown)}")
            self.config = replace(self.config, **clean)
            return self.config

    @property
    def active(self) -> bool:
        return self.config != FaultConfig()

    def should_drop_replication(self) -> bool:
        """Sorteia se a proxima mensagem de replicacao sera descartada."""
        with self._lock:
            probability = self.config.drop_replication
            if probability <= 0.0:
                return False
            return self._rng.random() < probability

    def maybe_delay(self) -> None:
        """Aplica o atraso configurado, se houver."""
        delay_ms = self.config.delay_ms
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

    def is_frozen(self) -> bool:
        return self.config.freeze
