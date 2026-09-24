"""UI — Contacto, suscripción, navegación y scroll (Test Cases 6, 7, 10, 11, 25, 26)."""

from __future__ import annotations

import re

import allure
import pytest
from playwright.sync_api import Page, expect

from framework.data.factories import unique_email
from framework.data.loader import data_file
from framework.ui.pages import CartPage, ContactUsPage, HomePage

pytestmark = [pytest.mark.ui, pytest.mark.regression]


@allure.epic("UI")
@allure.feature("Contacto")
class TestContactUs:
    """Formulario de contacto: upload de archivos y diálogos JavaScript."""

    @pytest.mark.smoke
    @allure.title("TC6 - Enviar formulario con adjunto y aceptar el diálogo de confirmación")
    def test_submit_contact_form_with_attachment(self, page: Page):
        contact = ContactUsPage(page).open()
        contact.fill_form(
            name="QA Bot",
            email=unique_email(),
            subject="Consulta automatizada",
            message="Mensaje generado por el framework de automatización.",
            attachment=data_file("contact_attachment.txt"),
        )

        dialog_message = contact.submit(accept_dialog=True)

        assert dialog_message == "Press OK to proceed!"
        expect(contact.success_alert).to_have_text(ContactUsPage.SUCCESS_MESSAGE)
        contact.home_button.click()
        HomePage(page).should_be_loaded()

    @pytest.mark.negative
    @allure.title("Cancelar el diálogo de confirmación no envía el formulario")
    def test_dismiss_dialog_does_not_submit(self, page: Page):
        contact = ContactUsPage(page).open()
        contact.fill_form(name="QA Bot", email=unique_email(), subject="Cancelado", message="No debería enviarse")

        contact.submit(accept_dialog=False)

        expect(contact.success_alert).to_be_hidden()
        # Los datos siguen cargados: el usuario puede corregir y reintentar.
        expect(contact.subject).to_have_value("Cancelado")

    @pytest.mark.negative
    @allure.title("Email con formato inválido bloquea el envío")
    def test_invalid_email_blocks_submission(self, page: Page):
        contact = ContactUsPage(page).open()
        contact.fill_form(name="QA Bot", email="no-es-un-email", subject="X", message="Y")

        assert not contact.is_field_valid(contact.email)
        contact.submit_button.click()

        expect(contact.success_alert).to_be_hidden()
        expect(contact.email).to_have_value("no-es-un-email")


@allure.epic("UI")
@allure.feature("Suscripción")
class TestSubscription:
    """Suscripción al newsletter desde el footer."""

    @pytest.mark.parametrize(
        "open_page",
        [pytest.param(HomePage, id="home"), pytest.param(CartPage, id="cart")],
    )
    @allure.title("TC10/TC11 - Suscribirse desde el footer")
    def test_subscribe_from_footer(self, page: Page, open_page):
        current = open_page(page).open()

        current.subscription.subscribe(unique_email())

        expect(current.subscription.success_alert).to_have_text(current.subscription.SUCCESS_MESSAGE)

    @pytest.mark.negative
    @allure.title("Suscripción con email inválido no se envía")
    def test_subscribe_with_invalid_email(self, page: Page):
        home = HomePage(page).open()

        home.subscription.subscribe("invalido@")

        assert home.subscription.email_validation_message() != ""
        expect(home.subscription.success_alert).to_be_hidden()


@allure.epic("UI")
@allure.feature("Navegación")
class TestNavigation:
    """Home, menú principal y scroll."""

    @pytest.mark.smoke
    @allure.title("La home carga con título, carrusel y productos destacados")
    def test_home_page_loads(self, page: Page):
        home = HomePage(page).open()

        expect(page).to_have_title("Automation Exercise")
        expect(home.features_items.locator(".product-image-wrapper").first).to_be_visible()

    @pytest.mark.parametrize(
        ("link_attr", "expected_url"),
        [
            ("products_link", r"/products$"),
            ("cart_link", r"/view_cart$"),
            ("login_link", r"/login$"),
            ("test_cases_link", r"/test_cases$"),
            ("api_testing_link", r"/api_list$"),
            ("contact_us_link", r"/contact_us$"),
        ],
    )
    @allure.title("TC7 - El menú principal navega a {expected_url}")
    def test_main_menu_navigation(self, page: Page, link_attr, expected_url):
        home = HomePage(page).open()

        getattr(home.header, link_attr).click()

        expect(page).to_have_url(re.compile(expected_url))

    @allure.title("TC25 - La flecha flotante vuelve al inicio de la página")
    def test_scroll_up_with_arrow(self, page: Page):
        home = HomePage(page).open()
        home.scroll_to_bottom()
        expect(home.subscription.email_input).to_be_in_viewport()

        home.scroll_up_with_arrow()

        expect(home.hero_heading).to_be_in_viewport()

    @allure.title("TC26 - Volver al inicio con scroll (sin la flecha)")
    def test_scroll_up_without_arrow(self, page: Page):
        home = HomePage(page).open()
        home.scroll_to_bottom()
        expect(home.subscription.email_input).to_be_in_viewport()

        home.scroll_to_top()

        expect(home.hero_heading).to_be_in_viewport()
