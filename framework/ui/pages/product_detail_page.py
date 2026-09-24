"""Detalle de producto."""

from __future__ import annotations

import re
from dataclasses import dataclass

from playwright.sync_api import Locator, Page, expect

from framework.core.step import step
from framework.ui.components.modals import AddedToCartModal
from framework.ui.pages.base_page import BasePage
from framework.utils.parsing import parse_price


@dataclass(frozen=True)
class ProductInfo:
    """Datos visibles en el panel de información del producto."""

    name: str
    category: str
    price: int
    availability: str
    condition: str
    brand: str


class ProductDetailPage(BasePage):
    """Página ``/product_details/<id>``."""

    PATH = None  # depende del id; usar open_product()
    URL_PATTERN = re.compile(r"/product_details/\d+$")

    REVIEW_SUCCESS_MESSAGE = "Thank you for your review."

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.info_panel: Locator = page.locator(".product-information")
        self.name: Locator = self.info_panel.locator("h2")
        self.quantity: Locator = page.locator("#quantity")
        self.add_to_cart_button: Locator = self.info_panel.get_by_role("button", name="Add to cart")
        self.review_name: Locator = page.locator("#review-form #name")
        self.review_email: Locator = page.locator("#review-form #email")
        self.review_text: Locator = page.locator("#review-form #review")
        self.review_submit: Locator = page.locator("#button-review")
        # Se apunta a la alerta interna y no a #review-section: ese contenedor mide 0 px de alto
        # (su hijo es flotante) y Playwright, con razón, lo considera oculto aunque el texto se vea.
        self.review_success: Locator = page.locator("#review-section .alert-success")
        self.cart_modal = AddedToCartModal(page)

    @property
    def loaded_indicator(self) -> Locator:
        """El panel de información del producto."""
        return self.info_panel

    @step("Abrir detalle del producto id={product_id}")
    def open_product(self, product_id: int) -> ProductDetailPage:
        """Navega directamente al detalle de un producto.

        Args:
            product_id: Id del producto.
        """
        self.page.goto(f"/product_details/{product_id}", wait_until="domcontentloaded")
        return self.should_be_loaded()

    def _labeled_value(self, label: str) -> str:
        """Lee valores con formato ``<b>Label:</b> valor`` del panel de información."""
        text = self.info_panel.locator("p", has_text=f"{label}:").inner_text()
        return text.split(":", 1)[1].strip()

    def info(self) -> ProductInfo:
        """Extrae toda la información visible del producto.

        Returns:
            Snapshot inmutable de los datos mostrados.
        """
        return ProductInfo(
            name=self.name.inner_text().strip(),
            category=self._labeled_value("Category"),
            price=parse_price(self.info_panel.locator("span > span").first.inner_text()),
            availability=self._labeled_value("Availability"),
            condition=self._labeled_value("Condition"),
            brand=self._labeled_value("Brand"),
        )

    @step("Agregar {quantity} unidad(es) al carrito")
    def add_to_cart(self, quantity: int = 1, *, continue_shopping: bool = True) -> None:
        """Fija la cantidad y agrega el producto al carrito.

        Args:
            quantity: Unidades a agregar.
            continue_shopping: Cerrar el modal de confirmación al terminar.
        """
        self.quantity.fill(str(quantity))
        self.add_to_cart_button.click()
        self.cart_modal.should_be_visible()
        if continue_shopping:
            self.cart_modal.continue_shopping()

    @step("Escribir review como '{name}'")
    def write_review(self, name: str, email: str, review: str) -> None:
        """Completa y envía el formulario de review.

        Args:
            name: Nombre del autor.
            email: Email del autor.
            review: Texto del review.
        """
        self.review_name.fill(name)
        self.review_email.fill(email)
        self.review_text.fill(review)
        self.review_submit.click()

    def should_show_review_success(self) -> None:
        """Aserta el mensaje de agradecimiento tras enviar un review.

        El mensaje es transitorio (el sitio lo oculta a los ~3 s), por eso debe verificarse
        inmediatamente después de enviar: ``expect`` lo captura mientras está visible.
        """
        expect(self.review_success).to_be_visible()
        expect(self.review_success).to_contain_text(self.REVIEW_SUCCESS_MESSAGE)
