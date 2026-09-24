"""Página de inicio."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page

from framework.core.step import step
from framework.ui.components.modals import AddedToCartModal
from framework.ui.pages.base_page import BasePage


class HomePage(BasePage):
    """Home: slider principal, productos destacados y recomendados."""

    PATH = "/"
    # Acepta "/" y también "/#..." (anclas que agrega el botón de scroll-up).
    URL_PATTERN = re.compile(r"^https?://[^/]+/?(#.*)?$")

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.slider: Locator = page.locator("#slider-carousel")
        self.features_items: Locator = page.locator(".features_items")
        self.recommended_items: Locator = page.locator(".recommended_items")
        self.scroll_up_button: Locator = page.locator("#scrollUp")
        self.hero_heading: Locator = self.slider.locator(".item.active h2")
        self.cart_modal = AddedToCartModal(page)

    @property
    def loaded_indicator(self) -> Locator:
        """El carrusel principal solo existe en la home."""
        return self.slider

    @step("Subir al inicio con el botón flotante")
    def scroll_up_with_arrow(self) -> None:
        """Hace click en la flecha flotante de 'volver arriba'."""
        self.scroll_up_button.click()

    @step("Agregar el producto recomendado '{product_name}' al carrito")
    def add_recommended_to_cart(self, product_name: str) -> None:
        """Agrega un producto desde el carrusel de recomendados.

        Args:
            product_name: Nombre visible del producto.
        """
        self.recommended_items.scroll_into_view_if_needed()
        # El carrusel muestra varios "item" y solo uno está activo: se filtra por visibilidad.
        card = self.recommended_items.locator(".item.active .productinfo").filter(has_text=product_name)
        card.locator(".add-to-cart").click()
        self.cart_modal.should_be_visible()
