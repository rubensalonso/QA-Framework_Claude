"""Páginas del ciclo de vida de la cuenta: registro, cuenta creada y cuenta eliminada."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page

from framework.core.step import step
from framework.data.models import User
from framework.ui.pages.base_page import BasePage


class SignupPage(BasePage):
    """Formulario 'Enter Account Information' (segundo paso del registro)."""

    PATH = None  # solo se llega después de LoginPage.start_signup()
    URL_PATTERN = re.compile(r"/signup$")

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.form: Locator = page.locator("form[action='/signup']")
        self.heading: Locator = page.get_by_text("Enter Account Information")
        self.name: Locator = page.locator("[data-qa='name']")
        self.email: Locator = page.locator("[data-qa='email']")
        self.password: Locator = page.locator("[data-qa='password']")
        self.days: Locator = page.locator("[data-qa='days']")
        self.months: Locator = page.locator("[data-qa='months']")
        self.years: Locator = page.locator("[data-qa='years']")
        self.newsletter: Locator = page.locator("#newsletter")
        self.special_offers: Locator = page.locator("#optin")
        self.first_name: Locator = page.locator("[data-qa='first_name']")
        self.last_name: Locator = page.locator("[data-qa='last_name']")
        self.company: Locator = page.locator("[data-qa='company']")
        self.address1: Locator = page.locator("[data-qa='address']")
        self.address2: Locator = page.locator("[data-qa='address2']")
        self.country: Locator = page.locator("[data-qa='country']")
        self.state: Locator = page.locator("[data-qa='state']")
        self.city: Locator = page.locator("[data-qa='city']")
        self.zipcode: Locator = page.locator("[data-qa='zipcode']")
        self.mobile_number: Locator = page.locator("[data-qa='mobile_number']")
        self.create_account_button: Locator = page.locator("[data-qa='create-account']")

    @property
    def loaded_indicator(self) -> Locator:
        """El encabezado del formulario de datos de cuenta."""
        return self.heading

    def title_radio(self, title: str) -> Locator:
        """Radio button del tratamiento (``Mr``/``Mrs``).

        Args:
            title: Valor del radio.
        """
        return self.form.locator(f"input[name='title'][value='{title}']")

    @step("Completar datos de cuenta y dirección para {user}")
    def fill_account_information(self, user: User, *, newsletter: bool = True, offers: bool = True) -> None:
        """Completa todos los campos del formulario de registro.

        Args:
            user: Datos a cargar. Nombre y email ya vienen precargados del paso anterior.
            newsletter: Marcar la suscripción al newsletter.
            offers: Marcar la recepción de ofertas.
        """
        self.title_radio(user.title).check()
        self.password.fill(user.password)
        # select_option por *value*: independiente del idioma del texto visible.
        self.days.select_option(str(user.birth_day))
        self.months.select_option(str(user.birth_month))
        self.years.select_option(str(user.birth_year))
        self.newsletter.set_checked(newsletter)
        self.special_offers.set_checked(offers)
        self.first_name.fill(user.first_name)
        self.last_name.fill(user.last_name)
        self.company.fill(user.company)
        self.address1.fill(user.address1)
        self.address2.fill(user.address2)
        self.country.select_option(user.country)
        self.state.fill(user.state)
        self.city.fill(user.city)
        self.zipcode.fill(user.zipcode)
        self.mobile_number.fill(user.mobile_number)

    @step("Confirmar creación de cuenta")
    def submit(self) -> AccountCreatedPage:
        """Envía el formulario.

        Returns:
            Página de confirmación ya verificada.
        """
        self.create_account_button.click()
        return AccountCreatedPage(self.page).should_be_loaded()


class _AccountStatusPage(BasePage):
    """Base para las pantallas de confirmación (misma estructura, distinto mensaje)."""

    DATA_QA: str

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.status_heading: Locator = page.locator(f"[data-qa='{self.DATA_QA}']")
        self.continue_button: Locator = page.locator("[data-qa='continue-button']")

    @property
    def loaded_indicator(self) -> Locator:
        """El encabezado de estado."""
        return self.status_heading

    @step("Continuar")
    def continue_(self) -> None:
        """Hace click en 'Continue' (el guion bajo evita chocar con la palabra reservada)."""
        self.continue_button.click()


class AccountCreatedPage(_AccountStatusPage):
    """Confirmación 'ACCOUNT CREATED!'."""

    PATH = None
    URL_PATTERN = re.compile(r"/account_created$")
    DATA_QA = "account-created"


class AccountDeletedPage(_AccountStatusPage):
    """Confirmación 'ACCOUNT DELETED!'."""

    PATH = None
    URL_PATTERN = re.compile(r"/delete_account$")
    DATA_QA = "account-deleted"
