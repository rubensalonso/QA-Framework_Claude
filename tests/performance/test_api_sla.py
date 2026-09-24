"""Performance — SLA de latencia de la API (p95 sobre N muestras secuenciales).

Decisión de diseño: muestras **secuenciales** y pocas (``QA_PERF_API_SAMPLES``, máx. 20).
El objetivo es medir la latencia típica de un endpoint, no estresarlo. Generar concurrencia
contra un sitio público gratuito sería abusivo; para eso existe el test de carga con límites.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict

import allure
import pytest

from framework.api import ApiResponse, AutomationExerciseApi
from framework.config import Settings
from framework.performance.stats import summarize

pytestmark = [pytest.mark.performance, pytest.mark.api]

# Solo endpoints de lectura: medir performance nunca debe crear/modificar datos.
READ_ONLY_CALLS: list[tuple[str, Callable[[AutomationExerciseApi], ApiResponse]]] = [
    ("productsList", lambda api: api.get_products()),
    ("brandsList", lambda api: api.get_brands()),
    ("searchProduct", lambda api: api.search_products("top")),
    ("verifyLogin (inválido)", lambda api: api.verify_login("perf.qa@example.com", "x")),
]


@allure.epic("Performance")
@allure.feature("SLA de API")
class TestApiLatency:
    """Latencia de endpoints de lectura."""

    @pytest.mark.parametrize(("name", "call"), READ_ONLY_CALLS, ids=[c[0] for c in READ_ONLY_CALLS])
    @allure.title("p95 de latencia dentro del SLA: {name}")
    def test_p95_latency_within_sla(self, api: AutomationExerciseApi, settings: Settings, name, call):
        # Warm-up descartado: la primera llamada incluye DNS + handshake TLS, que no representan
        # la latencia en régimen del servicio.
        call(api)

        latencies: list[float] = []
        for _ in range(settings.perf_api_samples):
            response = call(api)
            assert response.is_json, f"{name} devolvió una respuesta no-JSON (HTTP {response.http_status})"
            latencies.append(response.elapsed_ms)

        summary = summarize(latencies)
        allure.attach(
            json.dumps(asdict(summary), indent=2), name=f"latencias {name}", attachment_type=allure.attachment_type.JSON
        )
        assert summary.p95_ms <= settings.perf_api_p95_ms, (
            f"{name}: p95 {summary.p95_ms:.0f} ms > SLA {settings.perf_api_p95_ms} ms ({summary})"
        )
