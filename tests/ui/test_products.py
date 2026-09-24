"""UI — Catálogo: listado, detalle, búsqueda, filtros y reviews (Test Cases 8, 9, 18, 19, 21)."""

from __future__ import annotations

import re

import allure
import pytest
from playwright.sync_api import Page, expect

from framework.api import AutomationExerciseApi
from framework.api.schemas import ProductsResponse
from framework.data.factories import unique_email
from framework.data.loader import load_json
from framework.ui.browser_setup import is_bot_challenge
from framework.ui.pages import ProductDetailPage, ProductsPage

pytestmark = [pytest.mark.ui, pytest.mark.regression]


@allure.epic("UI")
@allure.feature("Catálogo")
class TestProductCatalog:
    """Listado y detalle de productos."""

    @pytest.mark.smoke
    @allure.title("TC8 - El listado muestra productos y el detalle muestra toda su información")
    def test_product_list_and_detail(self, page: Page):
        products_page = ProductsPage(page).open()
        expect(products_page.grid_title).to_have_text("All Products", ignore_case=True)
        expect(products_page.product_cards.first).to_be_visible()

        products_page.view_product(1)

        detail = ProductDetailPage(page).should_be_loaded()
        info = detail.info()
        assert info.name, "El producto debe tener nombre"
        assert info.price > 0
        empty_fields = [f for f in ("category", "availability", "condition", "brand") if not getattr(info, f)]
        assert not empty_fields, f"Campos vacíos en el detalle: {empty_fields}"

    @allure.title("La UI muestra el mismo catálogo que expone la API")
    def test_ui_catalog_matches_api(self, page: Page, api: AutomationExerciseApi):
        # Test híbrido: la API es el oráculo de datos; la UI debe reflejarlo fielmente.
        api_products = api.get_products().as_model(ProductsResponse).products

        ui_names = ProductsPage(page).open().product_names()

        assert len(ui_names) == len(api_products)
        assert sorted(ui_names) == sorted(p.name for p in api_products)

    @allure.title("Todos los precios del catálogo son positivos")
    def test_all_prices_are_positive(self, page: Page):
        prices = ProductsPage(page).open().product_prices()

        assert prices, "No se encontraron precios"
        assert all(price > 0 for price in prices), f"Precios inválidos: {[p for p in prices if p <= 0]}"


@allure.epic("UI")
@allure.feature("Búsqueda")
class TestProductSearch:
    """Búsqueda de productos."""

    @pytest.mark.smoke
    @pytest.mark.parametrize("term", ["Top", "Jeans", "Dress"])
    @allure.title("TC9 - Buscar '{term}' muestra solo productos relacionados")
    def test_search_shows_related_products(self, page: Page, api: AutomationExerciseApi, term):
        products_page = ProductsPage(page).open()

        products_page.search(term)

        names = products_page.product_names()
        assert names, f"Sin resultados para '{term}'"
        # Oráculo: la API de búsqueda. La UI y la API deben coincidir exactamente.
        expected = api.search_products(term).as_model(ProductsResponse).products
        assert sorted(names) == sorted(p.name for p in expected)

    @pytest.mark.negative
    @allure.title("Búsqueda sin coincidencias muestra la grilla vacía sin errores")
    def test_search_without_results(self, page: Page):
        products_page = ProductsPage(page).open()

        products_page.search("zzz-no-existe-qa")

        expect(products_page.product_cards).to_have_count(0)

    @pytest.mark.security
    @pytest.mark.parametrize(
        "payload",
        [p for p in load_json("security_payloads.json") if p["id"].startswith(("xss", "sql"))],
        ids=lambda p: p["id"],
    )
    @allure.title("Payloads de XSS/inyección en la búsqueda no se ejecutan")
    def test_search_does_not_execute_injected_scripts(self, page: Page, payload):
        dialogs: list[str] = []
        # Si el XSS se ejecutara, dispararía un alert(): lo capturamos para detectarlo.
        page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
        products_page = ProductsPage(page).open()

        products_page.submit_search(payload["value"])

        # Dos desenlaces seguros: el WAF bloquea la petición, o la app responde sin resultados.
        if not is_bot_challenge(page.title()):
            expect(products_page.grid_title).to_have_text("Searched Products", ignore_case=True)
            expect(products_page.product_cards).to_have_count(0)
        assert not dialogs, f"Se ejecutó JavaScript inyectado: {dialogs}"


@allure.epic("UI")
@allure.feature("Filtros")
class TestProductFilters:
    """Filtros por categoría y marca."""

    @pytest.mark.parametrize(
        ("parent", "child"),
        [("Women", "Dress"), ("Men", "Tshirts"), ("Kids", "Tops & Shirts")],
    )
    @allure.title("TC18 - Filtrar por categoría {parent} > {child}")
    def test_filter_by_category(self, page: Page, parent, child):
        products_page = ProductsPage(page).open()

        products_page.filter_by_category(parent, child)

        expect(page).to_have_url(re.compile(r"/category_products/\d+$"))
        expect(products_page.grid_title).to_have_text(f"{parent} - {child} Products", ignore_case=True)
        expect(products_page.product_cards.first).to_be_visible()

    @pytest.mark.parametrize("brand", ["Polo", "H&M", "Madame"])
    @allure.title("TC19 - Filtrar por marca '{brand}' muestra solo productos de esa marca")
    def test_filter_by_brand(self, page: Page, api: AutomationExerciseApi, brand):
        products_page = ProductsPage(page).open()

        products_page.filter_by_brand(brand)

        expect(products_page.grid_title).to_have_text(f"Brand - {brand} Products", ignore_case=True)
        expected = [p.name for p in api.get_products().as_model(ProductsResponse).products if p.brand == brand]
        assert sorted(products_page.product_names()) == sorted(expected)


@allure.epic("UI")
@allure.feature("Reviews")
class TestProductReview:
    """Reviews de productos."""

    @allure.title("TC21 - Escribir un review muestra el mensaje de agradecimiento")
    def test_write_review(self, page: Page):
        detail = ProductDetailPage(page).open_product(2)

        detail.write_review("QA Bot", unique_email(), "Review automatizado: excelente calidad.")

        detail.should_show_review_success()

    @pytest.mark.negative
    @allure.title("El review no se envía con campos obligatorios vacíos")
    def test_review_requires_fields(self, page: Page):
        detail = ProductDetailPage(page).open_product(2)

        detail.write_review("", "", "")

        # El formulario usa `required`: el navegador bloquea el envío y no aparece el mensaje.
        assert not detail.review_name.evaluate("el => el.checkValidity()")
        expect(detail.review_success).to_be_hidden()
