"""Cliente de dominio para la API pública de AutomationExercise (https://automationexercise.com/api_list).

Decisión de diseño: un método por endpoint con nombres de negocio. Los tests leen
``api.search_products("top")`` en vez de ``client.request("POST", "searchProduct", ...)``.
Si mañana cambia una URL o un nombre de parámetro, se corrige en un solo lugar.
"""

from __future__ import annotations

from framework.api.base_client import ApiResponse, BaseApiClient, HttpMethod
from framework.core.step import step
from framework.data.models import User


class Endpoints:
    """Rutas relativas al ``api_base_url`` (sin barra inicial, ver ``BaseApiClient.request``)."""

    PRODUCTS = "productsList"
    BRANDS = "brandsList"
    SEARCH_PRODUCT = "searchProduct"
    VERIFY_LOGIN = "verifyLogin"
    CREATE_ACCOUNT = "createAccount"
    DELETE_ACCOUNT = "deleteAccount"
    UPDATE_ACCOUNT = "updateAccount"
    USER_DETAIL_BY_EMAIL = "getUserDetailByEmail"


class AutomationExerciseApi(BaseApiClient):
    """Operaciones de negocio expuestas por la API."""

    # ------------------------------------------------------------- catálogo
    @step("API: obtener listado de productos")
    def get_products(self) -> ApiResponse:
        """``GET productsList`` (API 1)."""
        return self.request("GET", Endpoints.PRODUCTS)

    @step("API: obtener listado de marcas")
    def get_brands(self) -> ApiResponse:
        """``GET brandsList`` (API 3)."""
        return self.request("GET", Endpoints.BRANDS)

    @step("API: {method} a {endpoint} (método no soportado)")
    def call_with_method(self, method: HttpMethod, endpoint: str) -> ApiResponse:
        """Invoca un endpoint con un verbo arbitrario (para validar respuestas 405).

        Args:
            method: Verbo HTTP a probar.
            endpoint: Una constante de :class:`Endpoints`.
        """
        # retry=False: un 405 es determinístico, reintentar solo agrega latencia.
        return self.request(method, endpoint, retry=False)

    @step("API: buscar productos con término '{term}'")
    def search_products(self, term: str | None) -> ApiResponse:
        """``POST searchProduct`` (API 5 / API 6).

        Args:
            term: Término a buscar. ``None`` omite el parámetro (caso negativo, API 6).
        """
        form = {"search_product": term} if term is not None else None
        # POST de solo lectura: es seguro reintentarlo aunque POST no sea idempotente por norma.
        return self.request("POST", Endpoints.SEARCH_PRODUCT, form=form, retry=True)

    # ---------------------------------------------------------- autenticación
    @step("API: verificar login de '{email}'")
    def verify_login(self, email: str | None, password: str | None) -> ApiResponse:
        """``POST verifyLogin`` (API 7 / 8 / 10).

        Args:
            email: Email del usuario; ``None`` omite el parámetro.
            password: Contraseña; ``None`` omite el parámetro.
        """
        form: dict[str, str] = {}
        if email is not None:
            form["email"] = email
        if password is not None:
            form["password"] = password
        return self.request("POST", Endpoints.VERIFY_LOGIN, form=form or None, retry=True)

    # ------------------------------------------------------------- cuentas
    @step("API: crear cuenta {user}")
    def create_account(self, user: User) -> ApiResponse:
        """``POST createAccount`` (API 11). **No** se reintenta: podría duplicar la cuenta."""
        return self.request("POST", Endpoints.CREATE_ACCOUNT, form=user.to_api_form())

    @step("API: crear cuenta con payload crudo")
    def create_account_raw(self, form: dict[str, str]) -> ApiResponse:
        """``POST createAccount`` con un payload arbitrario (para casos de campos faltantes)."""
        return self.request("POST", Endpoints.CREATE_ACCOUNT, form=form)

    @step("API: actualizar cuenta {user}")
    def update_account(self, user: User) -> ApiResponse:
        """``PUT updateAccount`` (API 13)."""
        return self.request("PUT", Endpoints.UPDATE_ACCOUNT, form=user.to_api_form())

    @step("API: eliminar cuenta '{email}'")
    def delete_account(self, email: str, password: str) -> ApiResponse:
        """``DELETE deleteAccount`` (API 12)."""
        # retry=False: si el primer DELETE llegó pero la respuesta se perdió, el reintento
        # devolvería 404 y confundiría el diagnóstico.
        return self.request(
            "DELETE", Endpoints.DELETE_ACCOUNT, form={"email": email, "password": password}, retry=False
        )

    @step("API: obtener detalle de usuario '{email}'")
    def get_user_by_email(self, email: str) -> ApiResponse:
        """``GET getUserDetailByEmail`` (API 14)."""
        return self.request("GET", Endpoints.USER_DETAIL_BY_EMAIL, params={"email": email})
