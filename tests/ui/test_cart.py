"""UI — Carrito de compras (Test Cases 12, 13, 17, 20, 22)."""

from __future__ import annotations

import allure
import pytest
from playwright.sync_api import Page, expect

from framework.api import AutomationExerciseApi
from framework.api.schemas import ProductsResponse
from framework.data import User
from framework.ui.pages import CartPage, HomePage, LoginPage, ProductDetailPage, ProductsPage

pytestmark = [pytest.mark.ui, pytest.mark.regression]


@allure.epic("UI")
@allure.feature("Carrito")
class TestCart:
    """Alta, baja y persistencia de productos en el carrito."""

    @pytest.mark.smoke
    @allure.title("TC12 - Agregar dos productos: precio, cantidad y total correctos")
    def test_add_multiple_products(self, page: Page):
        products_page = ProductsPage(page).open()

        products_page.add_to_cart(1)
        products_page.add_to_cart(2, continue_shopping=False)
        products_page.cart_modal.view_cart()

        items = CartPage(page).should_be_loaded().items()
        assert [i.product_id for i in items] == [1, 2]
        for item in items:
            assert item.quantity == 1
            # Regla de negocio: total de la línea = precio unitario × cantidad.
            assert item.total == item.price * item.quantity, f"Total incorrecto en {item}"

    @allure.title("TC13 - La cantidad elegida en el detalle se refleja en el carrito")
    def test_product_quantity_from_detail(self, page: Page):
        detail = ProductDetailPage(page).open_product(3)
        unit_price = detail.info().price

        detail.add_to_cart(quantity=4)
        detail.header.go_to_cart()

        [item] = CartPage(page).should_be_loaded().items()
        assert (item.product_id, item.quantity, item.total) == (3, 4, unit_price * 4)

    @allure.title("Agregar el mismo producto dos veces acumula la cantidad (no duplica filas)")
    def test_same_product_twice_accumulates_quantity(self, page: Page):
        products_page = ProductsPage(page).open()

        products_page.add_to_cart(1)
        products_page.add_to_cart(1)
        products_page.header.go_to_cart()

        [item] = CartPage(page).should_be_loaded().items()
        assert item.quantity == 2
        assert item.total == item.price * 2

    @pytest.mark.parametrize("quantity", [1, 99])
    @allure.title("Valores límite de cantidad: {quantity}")
    def test_quantity_boundaries(self, page: Page, quantity):
        detail = ProductDetailPage(page).open_product(1)

        detail.add_to_cart(quantity=quantity)
        detail.header.go_to_cart()

        [item] = CartPage(page).should_be_loaded().items()
        assert item.quantity == quantity
        assert item.total == item.price * quantity

    @allure.title("TC17 - Eliminar el único producto deja el carrito vacío")
    def test_remove_product_empties_cart(self, page: Page):
        ProductsPage(page).open().add_to_cart(1)
        cart = CartPage(page).open()

        cart.remove_product(1)

        cart.should_be_empty()

    @allure.title("Eliminar un producto conserva los demás")
    def test_remove_one_of_many(self, page: Page):
        products_page = ProductsPage(page).open()
        products_page.add_to_cart(1)
        products_page.add_to_cart(2)
        cart = CartPage(page).open()

        cart.remove_product(1)

        assert [i.product_id for i in cart.items()] == [2]

    @pytest.mark.negative
    @allure.title("Carrito vacío muestra el mensaje correspondiente")
    def test_empty_cart_message(self, page: Page):
        CartPage(page).open().should_be_empty()

    @pytest.mark.negative
    @allure.title("Un invitado que intenta hacer checkout ve el modal de login")
    def test_guest_checkout_requires_login(self, page: Page):
        ProductsPage(page).open().add_to_cart(1)
        cart = CartPage(page).open()

        cart.proceed_to_checkout()

        expect(cart.checkout_modal.root).to_be_visible()
        expect(cart.checkout_modal.message).to_have_text("Register / Login account to proceed on checkout.")
        cart.checkout_modal.go_to_register_login()
        LoginPage(page).should_be_loaded()

    @pytest.mark.e2e
    @allure.title("TC20 - El carrito de invitado se conserva después de iniciar sesión")
    def test_cart_persists_after_login(self, page: Page, api: AutomationExerciseApi, registered_user: User):
        # Los ids salen de la API (oráculo) en vez de hardcodearse: si cambia el catálogo, el test se adapta.
        searched_ids = sorted(p.id for p in api.search_products("Jeans").as_model(ProductsResponse).products)
        products_page = ProductsPage(page).open()
        products_page.search("Jeans")
        for product_id in searched_ids:
            products_page.add_to_cart(product_id)

        LoginPage(page).open().login(registered_user.email, registered_user.password)
        HomePage(page).should_be_loaded()
        cart = CartPage(page).open()

        assert sorted(i.product_id for i in cart.items()) == searched_ids

    @allure.title("TC22 - Agregar al carrito desde 'Recommended items'")
    def test_add_from_recommended_items(self, page: Page):
        home = HomePage(page).open()
        home.recommended_items.scroll_into_view_if_needed()
        expect(home.recommended_items).to_contain_text("recommended items", ignore_case=True)
        product_name = home.recommended_items.locator(".item.active .productinfo p").first.inner_text()

        home.add_recommended_to_cart(product_name)
        home.cart_modal.view_cart()

        names = [i.name for i in CartPage(page).should_be_loaded().items()]
        assert names == [product_name]
