"""API — Catálogo: productos, marcas y búsqueda (API 1 a 6).

Particularidad del SUT: la API responde siempre HTTP 200 y el código de negocio viaja en
``responseCode``. Por eso se valida ``response_code`` y no ``http_status`` (ver base_client.py).
"""

from __future__ import annotations

import re

import allure
import pytest

from framework.api import AutomationExerciseApi
from framework.api.automation_exercise_api import Endpoints
from framework.api.schemas import BrandsResponse, MessageResponse, ProductsResponse
from framework.data.loader import load_json

pytestmark = [pytest.mark.api, pytest.mark.regression]

METHOD_NOT_SUPPORTED = "This request method is not supported."


@allure.epic("API")
@allure.feature("Productos")
class TestProductsApi:
    """API 1 / API 2: listado de productos."""

    @pytest.mark.smoke
    @allure.title("GET productsList devuelve el catálogo y cumple el contrato")
    def test_get_products_returns_catalog(self, api: AutomationExerciseApi):
        response = api.get_products()

        assert response.http_status == 200
        assert response.response_code == 200
        # Validación de contrato: falla con detalle si cambia cualquier campo o tipo.
        catalog = response.as_model(ProductsResponse)
        assert catalog.products, "El catálogo no debería estar vacío"

    @allure.title("Los ids de producto son únicos")
    def test_product_ids_are_unique(self, catalog):
        ids = [p.id for p in catalog]
        duplicates = {i for i in ids if ids.count(i) > 1}
        assert not duplicates, f"Ids duplicados en el catálogo: {duplicates}"

    @allure.title("Todo producto tiene categoría con segmento Women/Men/Kids")
    def test_products_belong_to_known_segments(self, catalog):
        segments = {p.category.usertype.usertype for p in catalog}
        assert segments <= {"Women", "Men", "Kids"}, f"Segmentos inesperados: {segments}"

    @pytest.mark.negative
    @pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
    @allure.title("productsList rechaza el método {method} con 405")
    def test_products_rejects_unsupported_methods(self, api: AutomationExerciseApi, method):
        response = api.call_with_method(method, Endpoints.PRODUCTS)

        body = response.as_model(MessageResponse)
        assert body.responseCode == 405
        assert body.message == METHOD_NOT_SUPPORTED


@allure.epic("API")
@allure.feature("Marcas")
class TestBrandsApi:
    """API 3 / API 4: listado de marcas."""

    @pytest.mark.smoke
    @allure.title("GET brandsList devuelve marcas y cumple el contrato")
    def test_get_brands_returns_list(self, api: AutomationExerciseApi):
        response = api.get_brands()

        assert response.response_code == 200
        assert response.as_model(BrandsResponse).brands

    @allure.title("Las marcas de los productos coinciden con el listado de marcas")
    def test_brands_are_consistent_with_products(self, api: AutomationExerciseApi, catalog):
        # Test de consistencia entre endpoints: detecta datos huérfanos en el backend.
        brands = {b.brand for b in api.get_brands().as_model(BrandsResponse).brands}
        product_brands = {p.brand for p in catalog}

        assert product_brands == brands, (
            f"Solo en productos: {product_brands - brands} | Solo en marcas: {brands - product_brands}"
        )

    @pytest.mark.negative
    @pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
    @allure.title("brandsList rechaza el método {method} con 405")
    def test_brands_rejects_unsupported_methods(self, api: AutomationExerciseApi, method):
        response = api.call_with_method(method, Endpoints.BRANDS)

        assert response.response_code == 405
        assert response.message == METHOD_NOT_SUPPORTED


@allure.epic("API")
@allure.feature("Búsqueda")
class TestSearchApi:
    """API 5 / API 6: búsqueda de productos."""

    @pytest.mark.smoke
    @pytest.mark.parametrize("term", ["top", "tshirt", "jean", "dress"])
    @allure.title("Buscar '{term}' devuelve solo productos relacionados")
    def test_search_returns_relevant_products(self, api: AutomationExerciseApi, term):
        response = api.search_products(term)

        products = response.as_model(ProductsResponse).products
        assert products, f"La búsqueda de '{term}' no devolvió resultados"
        # Regla observada del SUT: el término matchea contra nombre o categoría.
        irrelevant = [
            p.name for p in products if term not in p.name.lower() and term not in p.category.category.lower()
        ]
        assert not irrelevant, f"Resultados sin relación con '{term}': {irrelevant}"

    @allure.title("La búsqueda no distingue mayúsculas de minúsculas")
    def test_search_is_case_insensitive(self, api: AutomationExerciseApi):
        lower = api.search_products("top").as_model(ProductsResponse).products
        upper = api.search_products("TOP").as_model(ProductsResponse).products

        assert {p.id for p in lower} == {p.id for p in upper}

    @pytest.mark.negative
    @allure.title("Un término sin coincidencias devuelve lista vacía (no error)")
    def test_search_without_matches_returns_empty_list(self, api: AutomationExerciseApi):
        response = api.search_products("zzz-no-existe-qa")

        assert response.response_code == 200
        assert response.as_model(ProductsResponse).products == []

    @pytest.mark.negative
    @allure.title("Término vacío devuelve el catálogo completo")
    def test_search_with_empty_term_returns_full_catalog(self, api: AutomationExerciseApi, catalog):
        # Caso borde: documenta el comportamiento actual. Si cambia, queremos enterarnos.
        searched = api.search_products("").as_model(ProductsResponse).products

        assert {p.id for p in searched} == {p.id for p in catalog}

    @pytest.mark.negative
    @allure.title("Omitir search_product devuelve 400 con mensaje explicativo")
    def test_search_without_parameter_returns_400(self, api: AutomationExerciseApi):
        response = api.search_products(None)

        assert response.response_code == 400
        assert response.message is not None
        assert re.search(r"search_product parameter is missing", response.message)

    @pytest.mark.security
    @pytest.mark.parametrize("payload", load_json("security_payloads.json"), ids=lambda p: p["id"])
    @allure.title("Payload malicioso en la búsqueda no rompe el servicio")
    def test_search_handles_malicious_payloads(self, api: AutomationExerciseApi, catalog, payload):
        response = api.search_products(payload["value"])

        # Dos desenlaces seguros son válidos:
        # 1) El WAF (Cloudflare) bloquea la petición en el perímetro → HTTP 403, nunca llega a la app.
        # 2) La app la procesa y responde de forma controlada, sin error ni fuga de datos.
        assert response.http_status < 500, f"Error de servidor ante payload: HTTP {response.http_status}"
        if response.http_status == 403:
            allure.dynamic.description("Bloqueado por el WAF antes de llegar a la aplicación.")
            return
        assert response.is_json, f"Respuesta no-JSON ante payload: {response.text[:200]}"
        assert response.response_code == 200
        products = response.as_model(ProductsResponse).products
        # Una inyección exitosa ("OR 1=1") devolvería todo el catálogo.
        assert len(products) < len(catalog), "La búsqueda devolvió el catálogo completo: posible inyección"
