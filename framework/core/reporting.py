"""Metadatos para el reporte de Allure: categorías de fallos y entorno de ejecución.

Decisión de diseño: las categorías convierten la pregunta de triage "¿qué falló?" en una vista del
reporte. Allure agrupa cada fallo en la PRIMERA categoría cuyo patrón coincide, así que el orden
importa: de lo más específico (entorno, contrato) a lo más genérico (producto, error del test).

Recordatorio de semántica en Allure: ``failed`` = falló una aserción (``AssertionError``);
``broken`` = cualquier otra excepción (error del test o de la infraestructura).
Los patrones se evalúan con ``matches()`` de Java sobre el texto completo: por eso ``(?s).*X.*``.
"""

from __future__ import annotations

from typing import Any

ALLURE_CATEGORIES: list[dict[str, Any]] = [
    {
        "name": "Fallo de entorno (sitio bloqueado, sobrecargado o backend 5xx)",
        "description": "No es un bug del producto: WAF, hosting saturado o error 5xx. Reintentar más tarde.",
        "matchedStatuses": ["failed", "broken"],
        "traceRegex": r"(?s).*(SiteUnavailableError|BackendUnavailableError).*",
    },
    {
        "name": "Contrato de API roto",
        "description": "La respuesta no cumple el esquema Pydantic: el backend cambió un campo o un tipo.",
        "matchedStatuses": ["failed", "broken"],
        "traceRegex": r"(?s).*pydantic.*ValidationError.*",
    },
    {
        "name": "Accesibilidad: violación grave nueva",
        "matchedStatuses": ["failed"],
        "messageRegex": r"(?s).*violaciones graves nuevas.*",
    },
    {
        "name": "Precondición no cumplida (login/registro por API o HTTP)",
        "matchedStatuses": ["failed", "broken"],
        "traceRegex": r"(?s).*(HttpLoginError|No se pudo crear el usuario de prueba).*",
    },
    {
        "name": "Timeout de UI (elemento o estado esperado nunca llegó)",
        "matchedStatuses": ["failed", "broken"],
        "messageRegex": r"(?s).*(Timeout \d+ms exceeded|Locator expected to|Page URL expected to).*",
    },
    {
        "name": "Fallo de producto (aserción de negocio)",
        "matchedStatuses": ["failed"],
    },
    {
        "name": "Error del test o del framework",
        "description": "Excepción inesperada que no es una aserción: revisar el código del test.",
        "matchedStatuses": ["broken"],
    },
]
