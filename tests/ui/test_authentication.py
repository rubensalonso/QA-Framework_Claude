"""UI — Registro, login, logout y baja de cuenta (Test Cases 1 a 5 del sitio)."""

from __future__ import annotations

import allure
import pytest
from playwright.sync_api import Page, expect

from framework.data import User
from framework.data.loader import load_json
from framework.ui.pages import AccountDeletedPage, HomePage, LoginPage, SignupPage

pytestmark = [pytest.mark.ui, pytest.mark.regression]


@allure.epic("UI")
@allure.feature("Registro")
class TestSignup:
    """Alta de usuarios desde la interfaz."""

    @pytest.mark.smoke
    @pytest.mark.e2e
    @allure.title("TC1 - Registrar usuario, verificar sesión y eliminar la cuenta")
    def test_register_and_delete_user(self, page: Page, new_user: User, account_cleanup):
        account_cleanup(new_user)  # si algo falla a mitad de camino, la API borra la cuenta igual

        login_page = LoginPage(page).open()
        expect(login_page.signup_form).to_contain_text("New User Signup!")
        login_page.start_signup(new_user.name, new_user.email)

        signup_page = SignupPage(page).should_be_loaded()
        # El nombre y el email del primer paso deben llegar precargados al formulario.
        expect(signup_page.name).to_have_value(new_user.name)
        expect(signup_page.email).to_have_value(new_user.email)
        signup_page.fill_account_information(new_user)
        created_page = signup_page.submit()
        expect(created_page.status_heading).to_have_text("Account Created!", ignore_case=True)

        created_page.continue_()
        home = HomePage(page).should_be_loaded()
        expect(home.header.logged_in_as).to_have_text(f"Logged in as {new_user.name}")

        home.header.delete_account()
        deleted_page = AccountDeletedPage(page).should_be_loaded()
        expect(deleted_page.status_heading).to_have_text("Account Deleted!", ignore_case=True)

    @pytest.mark.negative
    @allure.title("TC5 - Registrar un email ya existente muestra error")
    def test_signup_with_existing_email(self, page: Page, registered_user: User):
        login_page = LoginPage(page).open()

        login_page.start_signup("Otro Nombre", registered_user.email)

        expect(login_page.signup_error).to_have_text(LoginPage.EMAIL_ALREADY_EXISTS_ERROR)
        # Comportamiento observado: el formulario se re-renderiza en /signup (no en /login).
        # Lo relevante no es la URL sino que NO se avance al paso de datos de la cuenta.
        expect(login_page.signup_form).to_be_visible()
        expect(SignupPage(page).heading).to_be_hidden()

    @pytest.mark.negative
    @allure.title("El registro no avanza con un email de formato inválido (validación HTML5)")
    def test_signup_blocked_by_invalid_email_format(self, page: Page):
        login_page = LoginPage(page).open()

        login_page.start_signup("QA", "email-sin-arroba")

        # El navegador bloquea el submit: seguimos en /login con los datos intactos.
        assert login_page.validation_message(login_page.signup_email) != ""
        expect(login_page.signup_email).to_have_value("email-sin-arroba")
        expect(page).to_have_url(LoginPage.URL_PATTERN)


@allure.epic("UI")
@allure.feature("Login")
class TestLogin:
    """Inicio y cierre de sesión."""

    @pytest.mark.smoke
    @allure.title("TC2 - Login con credenciales válidas")
    def test_login_with_valid_credentials(self, page: Page, registered_user: User):
        LoginPage(page).open().login(registered_user.email, registered_user.password)

        home = HomePage(page).should_be_loaded()
        expect(home.header.logged_in_as).to_have_text(f"Logged in as {registered_user.name}")
        expect(home.header.logout_link).to_be_visible()
        expect(home.header.login_link).to_be_hidden()

    @allure.title("TC4 - Logout redirige a login y cierra la sesión")
    def test_logout(self, page: Page, logged_in_user: User):
        home = HomePage(page)

        home.header.logout()

        login_page = LoginPage(page).should_be_loaded()
        expect(login_page.header.logged_in_as).to_be_hidden()
        # Verifica que la sesión realmente terminó: una página protegida no debe mostrar al usuario.
        HomePage(page).open()
        expect(home.header.logged_in_as).to_be_hidden()

    @pytest.mark.negative
    @allure.title("TC3 - Login con contraseña incorrecta muestra error")
    def test_login_with_wrong_password(self, page: Page, registered_user: User):
        login_page = LoginPage(page).open()

        login_page.login(registered_user.email, "contraseña-incorrecta")

        expect(login_page.login_error).to_have_text(LoginPage.INVALID_CREDENTIALS_ERROR)
        expect(login_page.header.logged_in_as).to_be_hidden()

    @pytest.mark.negative
    @pytest.mark.parametrize("case", load_json("invalid_logins.json"), ids=lambda c: c["id"])
    @allure.title("Login con credenciales inválidas (data-driven)")
    def test_login_with_invalid_credentials(self, page: Page, case):
        login_page = LoginPage(page).open()
        login_page.fill_login(case["email"], case["password"])
        # Algunos payloads (p. ej. inyección SQL) no son emails válidos: el navegador los frena.
        blocked_by_browser = not login_page.is_valid(login_page.login_email)

        login_page.login_button.click()

        if blocked_by_browser:
            # Sin navegación: el valor sigue en el campo y no hay error del servidor.
            expect(login_page.login_email).to_have_value(case["email"].strip())
            expect(login_page.login_error).to_be_hidden()
        else:
            # Aserción positiva: esperar el mensaje de error confirma que el servidor respondió.
            expect(login_page.login_error).to_have_text(LoginPage.INVALID_CREDENTIALS_ERROR)
        expect(login_page.header.logged_in_as).to_be_hidden()

    @pytest.mark.negative
    @pytest.mark.parametrize(
        ("email", "password", "invalid_field"),
        [
            pytest.param("", "Secret123!", "login_email", id="email-vacio"),
            pytest.param("qa@example.com", "", "login_password", id="password-vacio"),
            pytest.param("qa-sin-arroba", "Secret123!", "login_email", id="email-mal-formado"),
        ],
    )
    @allure.title("Validaciones HTML5 impiden enviar el login incompleto")
    def test_login_client_side_validation(self, page: Page, email, password, invalid_field):
        login_page = LoginPage(page).open()
        login_page.fill_login(email, password)
        field = getattr(login_page, invalid_field)
        assert login_page.validation_message(field) != "", f"{invalid_field} debería ser inválido"

        login_page.login_button.click()

        # Prueba de que NO hubo submit: si la página hubiera recargado, los campos estarían vacíos.
        expect(login_page.login_email).to_have_value(email)
        expect(login_page.login_password).to_have_value(password)
        expect(login_page.login_error).to_be_hidden()

    @pytest.mark.security
    @allure.title("La contraseña no se expone en el DOM (input de tipo password)")
    def test_password_field_is_masked(self, page: Page):
        login_page = LoginPage(page).open()

        expect(login_page.login_password).to_have_attribute("type", "password")
