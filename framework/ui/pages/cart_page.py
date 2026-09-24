"""Carrito de compras."""

from __future__ import annotations

import re
from dataclasses import dataclass

from playwright.sync_api import Locator, Page, expect

from framework.core.step import step
from framework.ui.components.modals import CheckoutLoginModal
from framework.ui.pages.base_page import BasePage
from framework.utils.parsing import parse_price


@dataclass(frozen=True)
class CartItem:
    """Fila del carrito tal como la ve el usuario."""

    product_id: int
    name: str
    price: int
    quantity: int
    total: int


class CartPage(BasePage):
    """Página ``/view_cart``."""

    PATH = "/view_cart"
    URL_PATTERN = re.compile(r"/view_cart$")

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.breadcrumb: Locator = page.locator(".breadcrumbs")
        self.rows: Locator = page.locator("#cart_info_table tbody tr[id^='product-']")
        self.empty_cart_message: Locator = page.locator("#empty_cart")
        self.proceed_to_checkout_button: Locator = page.get_by_text("Proceed To Checkout")
        self.checkout_modal = CheckoutLoginModal(page)

    @property
    def loaded_indicator(self) -> Locator:
        """El breadcrumb 'Shopping Cart'."""
        return self.breadcrumb

    def row(self, product_id: int) -> Locator:
        """Fila de un producto concreto."""
        return self.page.locator(f"#product-{product_id}")

    def items(self) -> list[CartItem]:
        """Lee todas las filas del carrito.

        Returns:
            Lista de items en el orden en que se muestran.
        """
        result: list[CartItem] = []
        for row in self.rows.all():
            row_id = row.get_attribute("id") or ""
            result.append(
                CartItem(
                    product_id=int(row_id.removeprefix("product-")),
                    name=row.locator(".cart_description h4").inner_text().strip(),
                    price=parse_price(row.locator(".cart_price").inner_text()),
                    quantity=int(row.locator(".cart_quantity").inner_text().strip()),
                    total=parse_price(row.locator(".cart_total_price").inner_text()),
                )
            )
        self.logger.info("Carrito contiene %s item(s): %s", len(result), result)
        return result

    @step("Eliminar producto id={product_id} del carrito")
    def remove_product(self, product_id: int) -> None:
        """Elimina un producto y espera a que su fila desaparezca (la baja es vía AJAX).

        Args:
            product_id: Id del producto a eliminar.
        """
        row = self.row(product_id)
        self.click_expecting_ajax(row.locator(".cart_quantity_delete"), f"/delete_cart/{product_id}")
        expect(row).to_be_hidden()

    @step("Proceder al checkout")
    def proceed_to_checkout(self) -> None:
        """Hace click en 'Proceed To Checkout'.

        Para invitados abre un modal de login; para usuarios logueados navega a ``/checkout``.
        """
        self.proceed_to_checkout_button.click()

    def should_be_empty(self) -> None:
        """Aserta que el carrito está vacío (sin filas y con el mensaje correspondiente)."""
        expect(self.rows).to_have_count(0)
        expect(self.empty_cart_message).to_be_visible()
        expect(self.empty_cart_message).to_contain_text("Cart is empty!")
