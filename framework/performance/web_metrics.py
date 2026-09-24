"""Recolección de métricas de carga desde el navegador (Navigation Timing + Web Vitals).

Decisión de diseño: se leen las APIs estándar del navegador (``PerformanceNavigationTiming``,
``largest-contentful-paint``, ``layout-shift``) en vez de medir con ``time.time()`` desde Python.
Así el número refleja lo que experimenta el usuario y no incluye el overhead del protocolo
entre Playwright y el navegador.

Limitación conocida: LCP y CLS solo existen en navegadores Chromium. En Firefox/WebKit
se devuelven como ``None`` y los tests correspondientes se saltean (no fallan).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import allure
from playwright.sync_api import Page

from framework.core.logger import get_logger

_logger = get_logger(__name__)

# Script ejecutado en la página. Los PerformanceObserver con `buffered: true` devuelven también
# las entradas ocurridas ANTES de registrarse, por eso puede ejecutarse después del load.
_COLLECT_METRICS_JS = """
async () => {
  const nav = performance.getEntriesByType('navigation')[0];
  const observe = (type) => new Promise((resolve) => {
    try {
      const entries = [];
      const po = new PerformanceObserver((list) => entries.push(...list.getEntries()));
      po.observe({ type, buffered: true });
      // Pequeña ventana para que el observer entregue las entradas bufferizadas.
      setTimeout(() => { po.disconnect(); resolve(entries); }, 300);
    } catch (e) { resolve(null); }   // tipo no soportado por este navegador
  });
  const lcpEntries = await observe('largest-contentful-paint');
  const clsEntries = await observe('layout-shift');
  const resources = performance.getEntriesByType('resource');
  return {
    ttfb_ms: nav ? nav.responseStart - nav.startTime : null,
    dom_content_loaded_ms: nav ? nav.domContentLoadedEventEnd - nav.startTime : null,
    load_ms: nav ? nav.loadEventEnd - nav.startTime : null,
    lcp_ms: lcpEntries && lcpEntries.length ? lcpEntries[lcpEntries.length - 1].startTime : null,
    cls: clsEntries ? clsEntries.filter(e => !e.hadRecentInput).reduce((a, e) => a + e.value, 0) : null,
    resource_count: resources.length,
    transfer_kb: resources.reduce((a, r) => a + (r.transferSize || 0), 0) / 1024,
  };
}
"""


@dataclass(frozen=True)
class PageLoadMetrics:
    """Métricas de una carga de página (tiempos en ms desde el inicio de la navegación)."""

    url: str
    ttfb_ms: float | None
    dom_content_loaded_ms: float | None
    load_ms: float | None
    lcp_ms: float | None
    cls: float | None
    resource_count: int
    transfer_kb: float


def measure_page_load(page: Page, path: str) -> PageLoadMetrics:
    """Navega a ``path`` con carga completa y devuelve sus métricas.

    Se usa ``wait_until="load"`` (no ``domcontentloaded``) porque ``loadEventEnd``
    vale 0 hasta que el evento ``load`` termina.

    Args:
        page: Página de Playwright (idealmente con un contexto limpio → caché fría).
        path: Ruta relativa al base_url.

    Returns:
        Métricas redondeadas a 1 decimal, también adjuntadas a Allure como JSON.
    """
    page.goto(path, wait_until="load")
    raw = page.evaluate(_COLLECT_METRICS_JS)

    def _round(value: float | None) -> float | None:
        return round(value, 1) if value is not None else None

    metrics = PageLoadMetrics(
        url=page.url,
        ttfb_ms=_round(raw["ttfb_ms"]),
        dom_content_loaded_ms=_round(raw["dom_content_loaded_ms"]),
        load_ms=_round(raw["load_ms"]),
        lcp_ms=_round(raw["lcp_ms"]),
        cls=round(raw["cls"], 4) if raw["cls"] is not None else None,
        resource_count=int(raw["resource_count"]),
        transfer_kb=round(raw["transfer_kb"], 1),
    )
    _logger.info("Métricas de carga %s: %s", path, metrics)
    allure.attach(
        json.dumps(asdict(metrics), indent=2),
        name=f"page-load-metrics {path}",
        attachment_type=allure.attachment_type.JSON,
    )
    return metrics
