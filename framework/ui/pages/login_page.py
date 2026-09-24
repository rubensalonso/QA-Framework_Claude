"""Página de Login / Signup (ambos formularios conviven en ``/login``)."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page

from framework.core.step import step
from framework.ui.pages.base_page import BasePage


class LoginPage(BasePage):
    """Formularios 'Login to your account' y 'New User Signup!'."""

    PATH = "/login"
    URL_PATTERN = re.compile(r"/login(\?.*)?$")

    INVALID_CREDENTIALS_ERROR = "Your email or password is incorrect!"
    EMAIL_ALREADY_EXISTS_ERROR = "Email Address already exist!"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        # --- Login ---
        self.login_form: Locator = page.locator(".login-form")
        self.login_email: Locator = page.locator("[data-qa='login-email']")
        self.login_password: Locator = page.locator("[data-qa='login-password']")
        self.login_button: Locator = page.locator("[data-qa='login-button']")
        self.login_error: Locator = self.login_form.locator("p")
        # --- Signup ---
        self.signup_form: Locator = page.locator(".signup-form")
        self.signup_name: Locator = page.locator("[data-qa='signup-name']")
        self.signup_email: Locator = page.locator("[data-qa='signup-email']")
        self.signup_button: Locator = page.locator("[data-qa='signup-button']")
        self.signup_error: Locator = self.signup_form.locator("p")

    @property
    def loaded_indicator(self) -> Locator:
        """El formulario de login."""
        return self.login_form

    @step("Login con email '{email}'")
    def login(self, email: str, password: str) -> None:
        """Completa y envía el formulario de login.

        No devuelve la página destino porque depende del resultado (home si es válido,
        la misma página con error si no). El test decide qué verificar.

        Args:
            email: Email (puede ser vacío/inválido en casos negativos).
            password: Contraseña (se enmascara en logs y reportes).
        """
        self.fill_login(email, password)
        self.login_button.click()

    def fill_login(self, email: str, password: str) -> None:
        """Completa el formulario de login sin enviarlo.

        Separar "completar" de "enviar" permite a los tests negativos inspeccionar la
        validación HTML5 *antes* del submit: después, si la página recarga, el campo queda
        vacío y su ``validationMessage`` daría un falso positivo.

        Args:
            email: Email.
            password: Contraseña.
        """
        self.login_email.fill(email)
        self.login_password.fill(password)

    @staticmethod
    def is_valid(field: Locator) -> bool:
        """Estado de validez HTML5 del campo (``checkValidity()``)."""
        return bool(field.evaluate("el => el.checkValidity()"))

    @step("Iniciar registro con nombre '{name}' y email '{email}'")
    def start_signup(self, name: str, email: str) -> None:
        """Completa el primer paso del registro (nombre + email).

        Args:
            name: Nombre visible del usuario.
            email: Email a registrar.
        """
        self.signup_name.fill(name)
        self.signup_email.fill(email)
        self.signup_button.click()

    @staticmethod
    def validation_message(field: Locator) -> str:
        """Mensaje de validación nativo del navegador (HTML5) para un campo.

        Útil para campos ``required``/``type=email``: el navegador bloquea el envío
        y el backend nunca recibe la petición, así que no hay mensaje en el DOM.

        Args:
            field: Locator del ``<input>``.

        Returns:
            Texto del mensaje, o ``''`` si el campo es válido.
        """
        return str(field.evaluate("el => el.validationMessage"))
