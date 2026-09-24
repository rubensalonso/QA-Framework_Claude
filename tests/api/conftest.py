"""Fixtures específicas de la suite de API."""

from __future__ import annotations

import pytest

from framework.api import AutomationExerciseApi
from framework.api.schemas import Product, ProductsResponse


@pytest.fixture(scope="module")
def catalog(api: AutomationExerciseApi) -> list[Product]:
    """Catálogo completo, obtenido una vez por módulo.

    Decisión de diseño: scope ``module`` evita repetir la misma llamada en cada test
    parametrizado (menos carga sobre un sitio público y suite más rápida), sin llegar
    a ``session``, que compartiría el dato entre suites no relacionadas.
    """
    return api.get_products().as_model(ProductsResponse).products
