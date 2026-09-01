"""Metricas de desempenho e estado (RF-15, RNF-04, RNF-05).

Expostas em ``/admin/metrics`` e consumidas por ``scripts/bench.py`` para montar
a tabela de resultados da entrega.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LatencyHistogram:
    """Amostras de latencia, para p50 e p99.

    Guarda amostras cruas em uma janela deslizante: com o volume deste projeto
    (milhares de operacoes) isso e exato e mais simples que um histograma por
    baldes, e p99 exato importa para checar RNF-05 (< 200 ms).
    """

    window: int = 10_000
    samples: list[float] = field(default_factory=list)

    def observe(self, seconds: float) -> None:
        raise NotImplementedError

    def percentile(self, p: float) -> float:
        """Percentil em milissegundos; 0.0 se nao ha amostras."""
        raise NotImplementedError


@dataclass
class Metrics:
    """Contadores do no."""

    ops_ok: int = 0
    ops_rejected: int = 0
    ops_no_quorum: int = 0
    elections_started: int = 0
    times_promoted: int = 0
    times_stepped_down: int = 0
    entries_truncated: int = 0
    write_latency: LatencyHistogram = field(default_factory=LatencyHistogram)
    replication_latency: LatencyHistogram = field(default_factory=LatencyHistogram)

    def snapshot(self) -> dict:
        """Metricas + TPS observado, no formato de ``/admin/metrics``."""
        raise NotImplementedError
