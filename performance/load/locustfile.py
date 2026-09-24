"""Prueba de carga con Locust sobre los endpoints de lectura de AutomationExercise.

⚠️  USO RESPONSABLE: AutomationExercise es un sitio público y gratuito. Este archivo está
pensado para *aprender* la técnica, con límites estrictos incorporados:

* Solo endpoints de lectura (GET / búsquedas). Nunca crea ni borra datos.
* Tope duro de usuarios concurrentes (``QA_LOAD_MAX_USERS``, por defecto 5): si se pide más,
  la prueba se aborta antes de enviar una sola petición.
* Pausas de 1-3 s entre tareas (comportamiento humano, no ráfagas).

Para pruebas de carga reales, apuntar ``--host`` a un entorno propio (staging) y ajustar el tope.

Ejecución (headless, con reporte HTML)::

    locust -f performance/load/locustfile.py --config performance/load/locust.conf

Criterios de aceptación (el proceso termina con código 1 si no se cumplen → apto para CI):
* Tasa de error ≤ ``QA_LOAD_MAX_FAIL_RATIO`` (1 % por defecto).
* p95 global ≤ ``QA_LOAD_P95_MS`` (3000 ms por defecto).
"""

from __future__ import annotations

import json
import logging
import os
import random
import sys

from locust import HttpUser, between, events, task
from locust.clients import ResponseContextManager
from locust.env import Environment

logger = logging.getLogger("load-test")

MAX_USERS = int(os.getenv("QA_LOAD_MAX_USERS", "5"))
MAX_FAIL_RATIO = float(os.getenv("QA_LOAD_MAX_FAIL_RATIO", "0.01"))
P95_LIMIT_MS = float(os.getenv("QA_LOAD_P95_MS", "3000"))
SEARCH_TERMS = ("top", "tshirt", "jean", "dress", "saree", "polo")


@events.init.add_listener
def enforce_user_cap(environment: Environment, **_: object) -> None:
    """Aborta el proceso si se solicitan más usuarios que el tope permitido.

    Decisión de diseño: el límite es parte del código, no solo de la documentación.
    Un error de tipeo (``-u 500`` en vez de ``-u 5``) no debe poder saturar un sitio ajeno.
    Se valida en ``init`` (antes de crear usuarios virtuales): no llega a salir ninguna petición.
    """
    options = environment.parsed_options
    requested = getattr(options, "num_users", 0) or 0
    if requested > MAX_USERS:
        logger.error("Se pidieron %s usuarios; el tope es %s (QA_LOAD_MAX_USERS). Abortando.", requested, MAX_USERS)
        sys.exit(2)


@events.quitting.add_listener
def evaluate_slo(environment: Environment, **_: object) -> None:
    """Evalúa los criterios de aceptación y fija el código de salida del proceso."""
    stats = environment.stats.total
    if stats.num_requests == 0:
        logger.error("No se ejecutó ninguna petición.")
        environment.process_exit_code = 1
        return

    p95 = stats.get_response_time_percentile(0.95)
    result = {
        "requests": stats.num_requests,
        "fail_ratio": round(stats.fail_ratio, 4),
        "p95_ms": p95,
        "avg_ms": round(stats.avg_response_time, 1),
        "rps": round(stats.total_rps, 2),
    }
    logger.info("Resultado de la prueba de carga: %s", json.dumps(result))

    if stats.fail_ratio > MAX_FAIL_RATIO:
        logger.error("FALLO: tasa de error %.2f%% > %.2f%%", stats.fail_ratio * 100, MAX_FAIL_RATIO * 100)
        environment.process_exit_code = 1
    elif p95 > P95_LIMIT_MS:
        logger.error("FALLO: p95 %s ms > %s ms", p95, P95_LIMIT_MS)
        environment.process_exit_code = 1
    else:
        environment.process_exit_code = 0


def validate_business_code(response: ResponseContextManager) -> None:
    """Marca como fallo toda respuesta cuyo ``responseCode`` de negocio no sea 200.

    Necesario porque esta API siempre responde HTTP 200: sin esta validación,
    Locust contaría como exitosos los errores reales (y el HTML de un bloqueo del WAF).

    Args:
        response: Respuesta abierta con ``catch_response=True``.
    """
    try:
        code = response.json().get("responseCode")
    except ValueError:  # body no-JSON (p. ej. página de error de Cloudflare)
        response.failure(f"Respuesta no-JSON (HTTP {response.status_code})")
        return
    if code != 200:
        response.failure(f"responseCode={code}")


class CatalogReader(HttpUser):
    """Usuario virtual que navega el catálogo vía API (solo lectura)."""

    wait_time = between(1, 3)

    @task(3)
    def list_products(self) -> None:
        """Listado completo de productos (la operación más frecuente)."""
        with self.client.get("/api/productsList", name="GET productsList", catch_response=True) as resp:
            validate_business_code(resp)

    @task(2)
    def search_product(self) -> None:
        """Búsqueda con un término aleatorio (evita que la caché sesgue los resultados)."""
        term = random.choice(SEARCH_TERMS)
        with self.client.post(
            "/api/searchProduct", data={"search_product": term}, name="POST searchProduct", catch_response=True
        ) as resp:
            validate_business_code(resp)

    @task(1)
    def list_brands(self) -> None:
        """Listado de marcas."""
        with self.client.get("/api/brandsList", name="GET brandsList", catch_response=True) as resp:
            validate_business_code(resp)
