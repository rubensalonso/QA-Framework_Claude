"""UI — Checkout completo: direcciones, pago y factura (Test Cases 14, 16, 23, 24)."""

from __future__ import annotations

from pathlib import Path

import allure
import pytest
from playwright.sync_api import Page, expect

from framework.data import PaymentCardFactory, User
from framework.ui.pages import CartPage, CheckoutPage, HomePage, LoginPage, ProductsPage, SignupPage

pytestmark = [pytest.mark.ui, pytest.mark.e2e, pytest.mark.regression]


def _expected_address_lines(user: User) -> tuple[str, ...]:
    """Líneas de dirección que el checkout debería mostrar para ``user``."""
    return (user.company, user.address1, user.address2)


@allure.epic("UI")
@allure.feature("Checkout")
class TestCheckout:
    """Compra de punta a punta."""

    @pytest.mark.smoke
    @allure.title("TC16/TC24 - Usuario logueado compra, paga y descarga la factura")
    def test_place_order_and_download_invoice(self, page: Page, logged_in_user: User, tmp_path: Path):
        products_page = ProductsPage(page).open()
        products_page.add_to_cart(1)
        products_page.add_to_cart(5)
        cart = CartPage(page).open()
        cart_items = cart.items()

        cart.proceed_to_checkout()
        checkout = CheckoutPage(page).should_be_loaded()

        with allure.step("Verificar direcciones de entrega y facturación (TC23)"):
            for address in (checkout.delivery(), checkout.invoice()):
                assert address.full_name == logged_in_user.full_name
                assert address.lines == _expected_address_lines(logged_in_user)
                assert address.city_state_zip == (
                    f"{logged_in_user.city} {logged_in_user.state} {logged_in_user.zipcode}"
                )
                assert address.country == logged_in_user.country
                assert address.phone == logged_in_user.mobile_number

        with allure.step("Verificar que el total coincide con la suma del carrito"):
            assert checkout.total() == sum(i.total for i in cart_items)

        order_placed = checkout.place_order("Pedido generado por automatización QA").pay(PaymentCardFactory.build())
        expect(order_placed.heading).to_have_text("Order Placed!", ignore_case=True)
        expect(order_placed.confirmation).to_have_text("Congratulations! Your order has been confirmed!")

        invoice = order_placed.download_invoice(tmp_path)
        content = invoice.read_text(encoding="utf-8")
        assert logged_in_user.first_name in content, "La factura debe estar a nombre del comprador"
        assert str(sum(i.total for i in cart_items)) in content, "La factura debe incluir el importe total"

    @allure.title("Después de pagar, el carrito queda vacío")
    def test_cart_is_empty_after_order(self, page: Page, logged_in_user: User):
        ProductsPage(page).open().add_to_cart(2)
        cart = CartPage(page).open()
        cart.proceed_to_checkout()

        CheckoutPage(page).should_be_loaded().place_order().pay(PaymentCardFactory.build())

        CartPage(page).open().should_be_empty()

    @allure.title("TC14 - Registrarse durante el checkout y completar la compra")
    def test_register_during_checkout(self, page: Page, new_user: User, account_cleanup):
        account_cleanup(new_user)
        ProductsPage(page).open().add_to_cart(1)
        cart = CartPage(page).open()
        cart.proceed_to_checkout()
        cart.checkout_modal.go_to_register_login()

        LoginPage(page).should_be_loaded().start_signup(new_user.name, new_user.email)
        signup = SignupPage(page).should_be_loaded()
        signup.fill_account_information(new_user)
        signup.submit().continue_()
        home = HomePage(page).should_be_loaded()
        expect(home.header.logged_in_as).to_contain_text(new_user.name)

        # El carrito del invitado sobrevive al registro y permite finalizar la compra.
        home.header.go_to_cart()
        CartPage(page).should_be_loaded().proceed_to_checkout()
        order = CheckoutPage(page).should_be_loaded().place_order().pay(PaymentCardFactory.build())
        expect(order.heading).to_be_visible()

    @pytest.mark.negative
    @allure.title("El pago no se confirma con los datos de tarjeta vacíos")
    def test_payment_requires_card_data(self, page: Page, logged_in_user: User):
        ProductsPage(page).open().add_to_cart(1)
        cart = CartPage(page).open()
        cart.proceed_to_checkout()
        payment = CheckoutPage(page).should_be_loaded().place_order()

        payment.pay_button.click()

        # Campos `required`: el navegador bloquea el envío y seguimos en /payment.
        assert not payment.name_on_card.evaluate("el => el.checkValidity()")
        payment.should_be_loaded()
