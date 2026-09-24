"""Estadística de latencias para validar SLAs de API."""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class LatencySummary:
    """Resumen estadístico de una serie de latencias (ms)."""

    samples: int
    min_ms: float
    p50_ms: float
    p95_ms: float
    max_ms: float
    mean_ms: float

    def __str__(self) -> str:
        return (
            f"n={self.samples} min={self.min_ms:.0f} p50={self.p50_ms:.0f} "
            f"p95={self.p95_ms:.0f} max={self.max_ms:.0f} mean={self.mean_ms:.0f} (ms)"
        )


def percentile(values: Sequence[float], pct: float) -> float:
    """Percentil por el método *nearest-rank* (el mismo que usan muchas herramientas de carga).

    Decisión de diseño: con pocas muestras (5-20), la interpolación lineal subestima la cola.
    Nearest-rank devuelve siempre un valor realmente observado, más conservador para un SLA.

    Args:
        values: Latencias observadas (no vacía).
        pct: Percentil entre 0 y 100.

    Returns:
        El valor del percentil.

    Raises:
        ValueError: Si ``values`` está vacía o ``pct`` fuera de rango.
    """
    if not values:
        raise ValueError("No hay muestras para calcular el percentil")
    if not 0 < pct <= 100:
        raise ValueError(f"Percentil fuera de rango: {pct}")
    ordered = sorted(values)
    rank = math.ceil(pct / 100 * len(ordered))
    return ordered[rank - 1]


def summarize(values: Sequence[float]) -> LatencySummary:
    """Calcula el resumen estadístico de una serie de latencias.

    Args:
        values: Latencias en milisegundos (no vacía).

    Returns:
        Resumen con min/p50/p95/max/media.
    """
    return LatencySummary(
        samples=len(values),
        min_ms=min(values),
        p50_ms=percentile(values, 50),
        p95_ms=percentile(values, 95),
        max_ms=max(values),
        mean_ms=statistics.fmean(values),
    )
