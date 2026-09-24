"""Componente de suscripción del footer (presente en todas las páginas)."""

from __future__ import annotations

from playwright.sync_api import Locator, Page

from framework.core.step import step


class SubscriptionFooter:
    """Formulario 'SUBSCRIPTION' del pie de página."""

    SUCCESS_MESSAGE = "You have been successfully subscribed!"

    def __init__(self, page: Page) -> None:
        self.page = page
        self.heading: Locator = page.locator("footer").get_by_role("heading", name="Subscription")
        # Nota: el id real del sitio tiene un typo ("susbscribe"). Se respeta tal cual.
        self.email_input: Locator = page.locator("#susbscribe_email")
        self.submit_button: Locator = page.locator("#subscribe")
        self.success_alert: Locator = page.locator("#success-subscribe")

    @step("Suscribirse con el email '{email}'")
    def subscribe(self, email: str) -> None:
        """Completa y envía el formulario de suscripción.

        Args:
            email: Email a suscribir (puede ser inválido en casos negativos).
        """
        self.email_input.scroll_into_view_if_needed()
        self.email_input.fill(email)
        self.submit_button.click()

    def email_validation_message(self) -> str:
        """Mensaje de validación HTML5 del navegador para el campo email ('' si es válido)."""
        return str(self.email_input.evaluate("el => el.validationMessage"))
