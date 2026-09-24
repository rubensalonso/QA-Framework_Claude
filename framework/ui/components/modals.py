"""Modales que aparecen sobre las páginas de catálogo y carrito."""

from __future__ import annotations

from playwright.sync_api import Locator, Page, expect

from framework.core.step import step


class AddedToCartModal:
    """Modal 'Added!' que aparece al agregar un producto al carrito."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.root: Locator = page.locator("#cartModal")
        self.title: Locator = self.root.locator(".modal-title")
        self.continue_button: Locator = self.root.get_by_role("button", name="Continue Shopping")
        self.view_cart_link: Locator = self.root.get_by_role("link", name="View Cart")

    def should_be_visible(self) -> None:
        """Aserta que el modal se muestra con el mensaje de confirmación."""
        expect(self.root).to_be_visible()
        expect(self.title).to_have_text("Added!")

    @step("Modal: seguir comprando")
    def continue_shopping(self) -> None:
        """Cierra el modal y espera a que desaparezca.

        Esperar el cierre es clave: el backdrop del modal tiene una animación de fade; si se
        hace click en otro producto antes de que termine, el click lo intercepta el backdrop.
        """
        self.continue_button.click()
        expect(self.root).to_be_hidden()

    @step("Modal: ver carrito")
    def view_cart(self) -> None:
        """Navega al carrito desde el modal."""
        self.view_cart_link.click()


class CheckoutLoginModal:
    """Modal que pide registro/login cuando un invitado intenta hacer checkout."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.root: Locator = page.locator("#checkoutModal")
        self.message: Locator = self.root.locator(".modal-body p").first
        self.register_login_link: Locator = self.root.get_by_role("link", name="Register / Login")
        self.continue_on_cart_button: Locator = self.root.get_by_role("button", name="Continue On Cart")

    @step("Modal de checkout: ir a Register / Login")
    def go_to_register_login(self) -> None:
        """Navega a la página de login desde el modal."""
        self.register_login_link.click()
