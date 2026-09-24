"""Formulario de contacto (incluye upload de archivo y diálogo JavaScript de confirmación)."""

from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Dialog, Locator, Page

from framework.core.step import step
from framework.ui.pages.base_page import BasePage


class ContactUsPage(BasePage):
    """Página ``/contact_us``."""

    PATH = "/contact_us"
    URL_PATTERN = re.compile(r"/contact_us$")

    SUCCESS_MESSAGE = "Success! Your details have been submitted successfully."

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.heading: Locator = page.get_by_role("heading", name="Get In Touch")
        self.name: Locator = page.locator("[data-qa='name']")
        self.email: Locator = page.locator("[data-qa='email']")
        self.subject: Locator = page.locator("[data-qa='subject']")
        self.message: Locator = page.locator("[data-qa='message']")
        self.file_input: Locator = page.locator("input[name='upload_file']")
        self.submit_button: Locator = page.locator("[data-qa='submit-button']")
        self.success_alert: Locator = page.locator("#contact-page .status.alert-success")
        self.home_button: Locator = page.locator("#form-section").get_by_role("link", name="Home")

    @property
    def loaded_indicator(self) -> Locator:
        """El encabezado 'Get In Touch'."""
        return self.heading

    @step("Completar formulario de contacto como '{name}'")
    def fill_form(self, name: str, email: str, subject: str, message: str, attachment: Path | None = None) -> None:
        """Completa el formulario.

        Args:
            name: Nombre.
            email: Email.
            subject: Asunto.
            message: Mensaje.
            attachment: Archivo opcional a adjuntar.
        """
        self.name.fill(name)
        self.email.fill(email)
        self.subject.fill(subject)
        self.message.fill(message)
        if attachment is not None:
            self.file_input.set_input_files(attachment)

    @step("Enviar formulario (aceptar diálogo de confirmación: {accept_dialog})")
    def submit(self, *, accept_dialog: bool = True) -> str:
        """Envía el formulario y responde el ``confirm()`` de JavaScript.

        Decisión de diseño: el handler se registra con ``page.once`` *antes* del click.
        Si se registrara después, Playwright ya habría descartado el diálogo por defecto.

        Args:
            accept_dialog: ``True`` = OK, ``False`` = Cancelar.

        Returns:
            Texto del diálogo, para que el test pueda verificarlo.
        """
        captured: dict[str, str] = {}

        def _handle(dialog: Dialog) -> None:
            captured["message"] = dialog.message
            self.logger.info(
                "Diálogo JS '%s' (%s) → %s", dialog.message, dialog.type, "aceptar" if accept_dialog else "cancelar"
            )
            if accept_dialog:
                dialog.accept()
            else:
                dialog.dismiss()

        self.page.once("dialog", _handle)
        self.submit_button.click()
        return captured.get("message", "")

    def is_field_valid(self, field: Locator) -> bool:
        """Estado de validez HTML5 de un campo (``required``, ``type=email``...)."""
        return bool(field.evaluate("el => el.checkValidity()"))
