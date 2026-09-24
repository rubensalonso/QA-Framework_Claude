"""API — Autenticación y ciclo de vida de cuentas (API 7 a 14)."""

from __future__ import annotations

import dataclasses

import allure
import pytest

from framework.api import AutomationExerciseApi
from framework.api.automation_exercise_api import Endpoints
from framework.api.schemas import MessageResponse, UserDetailResponse
from framework.data import User, UserFactory
from framework.data.loader import load_json

pytestmark = [pytest.mark.api, pytest.mark.regression]


@allure.epic("API")
@allure.feature("Autenticación")
class TestVerifyLoginApi:
    """API 7 a 10: verificación de credenciales."""

    @pytest.mark.smoke
    @allure.title("Credenciales válidas → 200 'User exists!'")
    def test_valid_credentials(self, api: AutomationExerciseApi, registered_user: User):
        response = api.verify_login(registered_user.email, registered_user.password)

        body = response.as_model(MessageResponse)
        assert body.responseCode == 200
        assert body.message == "User exists!"

    @pytest.mark.negative
    @allure.title("Contraseña incorrecta para un usuario existente → 404")
    def test_wrong_password(self, api: AutomationExerciseApi, registered_user: User):
        response = api.verify_login(registered_user.email, registered_user.password + "x")

        assert response.response_code == 404
        assert response.message == "User not found!"

    @pytest.mark.negative
    @allure.title("El email se valida de forma exacta (mayúsculas)")
    def test_email_is_case_sensitive(self, api: AutomationExerciseApi, registered_user: User):
        # Caso borde que documenta el comportamiento actual: el backend no normaliza el email.
        response = api.verify_login(registered_user.email.upper(), registered_user.password)

        assert response.response_code == 404

    @pytest.mark.negative
    @pytest.mark.parametrize("case", load_json("invalid_logins.json"), ids=lambda c: c["id"])
    @allure.title("Credenciales inválidas (data-driven) → 404")
    def test_invalid_credentials(self, api: AutomationExerciseApi, case):
        response = api.verify_login(case["email"], case["password"])

        assert response.http_status < 500
        # El WAF puede cortar payloads de inyección (403): también es un resultado seguro.
        if response.http_status != 403:
            assert response.response_code == 404
            assert response.message == "User not found!"

    @pytest.mark.negative
    @pytest.mark.parametrize(
        ("email", "password"),
        [
            pytest.param(None, "Secret123!", id="sin-email"),
            pytest.param("qa@example.com", None, id="sin-password"),
            pytest.param(None, None, id="sin-parametros"),
        ],
    )
    @allure.title("Parámetros faltantes → 400")
    def test_missing_parameters(self, api: AutomationExerciseApi, email, password):
        response = api.verify_login(email, password)

        assert response.response_code == 400
        assert response.message == "Bad request, email or password parameter is missing in POST request."

    @pytest.mark.negative
    @allure.title("DELETE a verifyLogin → 405")
    def test_delete_method_not_supported(self, api: AutomationExerciseApi):
        response = api.call_with_method("DELETE", Endpoints.VERIFY_LOGIN)

        assert response.response_code == 405
        assert response.message == "This request method is not supported."


@allure.epic("API")
@allure.feature("Cuentas")
class TestAccountLifecycleApi:
    """API 11 a 14: alta, consulta, modificación y baja de cuentas."""

    @pytest.mark.smoke
    @pytest.mark.e2e
    @allure.title("Ciclo de vida completo: crear → consultar → actualizar → eliminar")
    def test_full_account_lifecycle(self, api: AutomationExerciseApi, new_user: User, account_cleanup):
        account_cleanup(new_user)  # red de seguridad si el test falla antes del paso final

        with allure.step("Crear cuenta"):
            created = api.create_account(new_user)
            assert created.response_code == 201
            assert created.message == "User created!"

        with allure.step("Consultar y verificar persistencia de datos"):
            user = api.get_user_by_email(new_user.email).as_model(UserDetailResponse).user
            assert (user.email, user.name, user.first_name, user.last_name) == (
                new_user.email,
                new_user.name,
                new_user.first_name,
                new_user.last_name,
            )
            assert (user.city, user.country, user.zipcode) == (new_user.city, new_user.country, new_user.zipcode)

        with allure.step("Actualizar ciudad y empresa"):
            updated_user = dataclasses.replace(new_user, city="Ottawa", company="QA Automation Inc.")
            updated = api.update_account(updated_user)
            assert updated.response_code == 200
            assert updated.message == "User updated!"
            persisted = api.get_user_by_email(new_user.email).as_model(UserDetailResponse).user
            assert (persisted.city, persisted.company) == ("Ottawa", "QA Automation Inc.")

        with allure.step("Eliminar cuenta y verificar que ya no puede autenticarse"):
            deleted = api.delete_account(new_user.email, new_user.password)
            assert deleted.response_code == 200
            assert deleted.message == "Account deleted!"
            assert api.verify_login(new_user.email, new_user.password).response_code == 404
            assert api.get_user_by_email(new_user.email).response_code == 404

    @allure.title("Los datos con caracteres Unicode se persisten sin corrupción")
    def test_unicode_data_round_trip(self, api: AutomationExerciseApi, account_cleanup):
        user = UserFactory.build(first_name="José Ñandú", last_name="Müller-Østergaard", city="São Paulo")
        account_cleanup(user)

        assert api.create_account(user).response_code == 201
        persisted = api.get_user_by_email(user.email).as_model(UserDetailResponse).user

        assert (persisted.first_name, persisted.last_name, persisted.city) == (
            "José Ñandú",
            "Müller-Østergaard",
            "São Paulo",
        )

    @pytest.mark.negative
    @allure.title("Registrar un email ya existente → 400 'Email already exists!'")
    def test_duplicate_email_is_rejected(self, api: AutomationExerciseApi, registered_user: User):
        duplicate = UserFactory.build(email=registered_user.email)

        response = api.create_account(duplicate)

        assert response.response_code == 400
        assert response.message == "Email already exists!"

    @pytest.mark.negative
    @pytest.mark.parametrize("missing_field", ["firstname", "lastname", "address1", "country", "mobile_number"])
    @allure.title("Crear cuenta sin '{missing_field}' → 400")
    def test_create_account_missing_required_field(
        self, api: AutomationExerciseApi, new_user: User, account_cleanup, missing_field
    ):
        account_cleanup(new_user)  # por si el backend la creara igual (sería un bug)
        payload = new_user.to_api_form()
        payload.pop(missing_field)

        response = api.create_account_raw(payload)

        assert response.response_code == 400
        assert response.message == f"Bad request, {missing_field} parameter is missing in POST request."

    @pytest.mark.negative
    @allure.title("Eliminar una cuenta inexistente → 404")
    def test_delete_nonexistent_account(self, api: AutomationExerciseApi, new_user: User):
        response = api.delete_account(new_user.email, new_user.password)

        assert response.response_code == 404
        assert response.message == "Account not found!"

    @pytest.mark.negative
    @allure.title("Eliminar con contraseña incorrecta no borra la cuenta")
    def test_delete_with_wrong_password_keeps_account(self, api: AutomationExerciseApi, registered_user: User):
        response = api.delete_account(registered_user.email, "wrong-password")

        assert response.response_code == 404
        # Verificación del efecto: la cuenta debe seguir existiendo.
        assert api.verify_login(registered_user.email, registered_user.password).response_code == 200

    @pytest.mark.negative
    @allure.title("Consultar un email inexistente → 404")
    def test_get_detail_of_unknown_email(self, api: AutomationExerciseApi, new_user: User):
        response = api.get_user_by_email(new_user.email)

        assert response.response_code == 404
        assert response.message == "Account not found with this email, try another email!"
