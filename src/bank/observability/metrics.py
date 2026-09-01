"""Metricas de desempenho e estado (RF-15, RNF-04, RNF-05).

Expostas em ``/admin/metrics`` e consumidas por ``scripts/bench.py`` para montar
a tabela de resultados da entrega.
"""

from __future__ import annotations

import threading
import time
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
        self.samples.append(seconds)
        if len(self.samples) > self.window:
            del self.samples[: len(self.samples) - self.window]

    def percentile(self, p: float) -> float:
        """Percentil em milissegundos; 0.0 se nao ha amostras."""
        if not self.samples:
            return 0.0
        ordered = sorted(self.samples)
        # Indice pelo metodo do vizinho mais proximo, suficiente e sem dependencias.
        position = min(int(round((p / 100.0) * (len(ordered) - 1))), len(ordered) - 1)
        return round(ordered[position] * 1000.0, 3)


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
    started_at: float = field(default_factory=time.monotonic)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def snapshot(self) -> dict:
        """Metricas + TPS observado, no formato de ``/admin/metrics``."""
        elapsed = max(time.monotonic() - self.started_at, 1e-9)
        return {
            "ops_ok": self.ops_ok,
            "ops_rejected": self.ops_rejected,
            "ops_no_quorum": self.ops_no_quorum,
            "elections_started": self.elections_started,
            "times_promoted": self.times_promoted,
            "times_stepped_down": self.times_stepped_down,
            "entries_truncated": self.entries_truncated,
            "uptime_s": round(elapsed, 3),
            "tps_observed": round(self.ops_ok / elapsed, 2),
            "write_latency_ms": {
                "p50": self.write_latency.percentile(50),
                "p99": self.write_latency.percentile(99),
                "samples": len(self.write_latency.samples),
            },
            "replication_latency_ms": {
                "p50": self.replication_latency.percentile(50),
                "p99": self.replication_latency.percentile(99),
            },
        }
