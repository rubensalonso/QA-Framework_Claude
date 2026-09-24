"""Componente de navegación superior (presente en todas las páginas).

Decisión de diseño sobre locators (orden de preferencia, siguiendo la guía oficial de Playwright):
1. Roles accesibles (``get_by_role``) → reflejan cómo el usuario percibe la UI.
2. Atributos de test dedicados (``data-qa``) → estables ante cambios de estilo.
3. IDs/CSS semánticos → último recurso, siempre acotados a un contenedor.
Nunca XPath absolutos ni selectores dependientes de la posición visual.
"""

from __future__ import annotations

from playwright.sync_api import Locator, Page

from framework.core.step import step


class Header:
    """Barra de navegación principal."""

    def __init__(self, page: Page) -> None:
        self.page = page
        # Se acota todo al menú: "Products" o "Cart" pueden aparecer en otras partes de la página.
        self._nav = page.locator(".shop-menu")
        self.home_link: Locator = self._nav.get_by_role("link", name="Home")
        self.products_link: Locator = self._nav.get_by_role("link", name="Products")
        self.cart_link: Locator = self._nav.get_by_role("link", name="Cart")
        self.login_link: Locator = self._nav.get_by_role("link", name="Signup / Login")
        self.logout_link: Locator = self._nav.get_by_role("link", name="Logout")
        self.delete_account_link: Locator = self._nav.get_by_role("link", name="Delete Account")
        self.contact_us_link: Locator = self._nav.get_by_role("link", name="Contact us")
        self.test_cases_link: Locator = self._nav.get_by_role("link", name="Test Cases")
        self.api_testing_link: Locator = self._nav.get_by_role("link", name="API Testing")
        self.logged_in_as: Locator = self._nav.locator("li", has_text="Logged in as")

    @step("Header: ir a Products")
    def go_to_products(self) -> None:
        """Navega al catálogo."""
        self.products_link.click()

    @step("Header: ir a Cart")
    def go_to_cart(self) -> None:
        """Navega al carrito."""
        self.cart_link.click()

    @step("Header: ir a Signup / Login")
    def go_to_login(self) -> None:
        """Navega a la página de login/registro."""
        self.login_link.click()

    @step("Header: ir a Contact us")
    def go_to_contact_us(self) -> None:
        """Navega al formulario de contacto."""
        self.contact_us_link.click()

    @step("Header: cerrar sesión")
    def logout(self) -> None:
        """Cierra la sesión del usuario actual."""
        self.logout_link.click()

    @step("Header: eliminar cuenta")
    def delete_account(self) -> None:
        """Elimina la cuenta del usuario logueado."""
        self.delete_account_link.click()
