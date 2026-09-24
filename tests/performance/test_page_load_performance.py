"""Performance — Tiempos de carga percibidos por el usuario (Navigation Timing + Core Web Vitals).

Qué mide y qué NO mide:
* SÍ: si una página crítica se degrada groseramente (TTFB, DOMContentLoaded, load, LCP, CLS).
* NO: capacidad del servidor bajo carga concurrente → eso es ``performance/load/locustfile.py``.

Cada test usa un contexto de navegador nuevo (caché fría): es el peor caso realista,
el de un usuario que llega por primera vez.
"""

from __future__ import annotations

import allure
import pytest
from playwright.sync_api import Page

from framework.config import Settings
from framework.performance.web_metrics import measure_page_load

pytestmark = [pytest.mark.performance, pytest.mark.ui]

CRITICAL_PAGES = [
    pytest.param("/", id="home"),
    pytest.param("/products", id="products"),
    pytest.param("/product_details/1", id="product-detail"),
    pytest.param("/login", id="login"),
    pytest.param("/view_cart", id="cart"),
]

# Umbral de CLS "bueno" según Google (web.dev/cls). A diferencia de los tiempos,
# no depende de la red, así que puede ser estricto.
CLS_GOOD_THRESHOLD = 0.1


@allure.epic("Performance")
@allure.feature("Carga de páginas")
class TestPageLoadPerformance:
    """Presupuestos de rendimiento por página (configurables vía QA_PERF_*)."""

    @pytest.mark.parametrize("path", CRITICAL_PAGES)
    @allure.title("Presupuesto de tiempos de carga: {path}")
    def test_page_load_within_budget(self, page: Page, settings: Settings, path):
        metrics = measure_page_load(page, path)

        # Se juntan todas las violaciones en un solo mensaje: un fallo muestra el panorama completo.
        budgets = {
            "TTFB": (metrics.ttfb_ms, settings.perf_ttfb_ms),
            "DOMContentLoaded": (metrics.dom_content_loaded_ms, settings.perf_dom_content_loaded_ms),
            "Load": (metrics.load_ms, settings.perf_load_ms),
        }
        violations = [
            f"{name}: {value:.0f} ms > {limit} ms"
            for name, (value, limit) in budgets.items()
            if value is not None and value > limit
        ]
        assert not violations, f"{path} excede el presupuesto → " + "; ".join(violations)

    @pytest.mark.only_browser("chromium")
    @pytest.mark.parametrize("path", CRITICAL_PAGES)
    @allure.title("Core Web Vitals (LCP y CLS): {path}")
    def test_core_web_vitals(self, page: Page, settings: Settings, path):
        # `only_browser`: LCP/CLS son APIs de Chromium; en Firefox/WebKit el test se saltea.
        metrics = measure_page_load(page, path)

        if metrics.lcp_ms is None:
            pytest.skip("El navegador no reportó LCP para esta página")
        assert metrics.lcp_ms <= settings.perf_lcp_ms, f"LCP {metrics.lcp_ms:.0f} ms > {settings.perf_lcp_ms} ms"
        assert metrics.cls is not None
        assert metrics.cls <= CLS_GOOD_THRESHOLD, f"CLS {metrics.cls} > {CLS_GOOD_THRESHOLD}"
