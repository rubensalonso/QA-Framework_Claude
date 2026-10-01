"""Inicio de sesión por HTTP para preparar precondiciones de tests de UI.

Decisiones de diseño:

* **Login por HTTP, no por formulario**: los tests que necesitan un usuario logueado (checkout,
  logout...) no deberían fallar si se rompe el formulario de login; eso ya lo cubren los tests
  de autenticación. Es el principio de "arrange por API" aplicado a la sesión.
* **``context.request`` comparte cookies con el navegador**: la cookie de sesión que devuelve el
  servidor queda disponible al instante para todas las páginas del contexto, sin copiarla a mano.
* **Sin reutilizar sesiones entre tests** (``storage_state``): en este sitio el carrito de un usuario
  logueado vive en el servidor; compartir usuario entre tests haría que se ensucien el carrito entre sí.
  Cada test sigue teniendo su usuario propio: se gana velocidad sin perder aislamiento.
* **Se respeta el CSRF de Django** (token del formulario + ``Referer``): el login es legítimo,
  idéntico al que haría el navegador, no un atajo que esquive controles del sitio.
"""

from __future__ import annotations

import re

from playwright.sync_api import BrowserContext

from framework.core.logger import get_logger
from framework.core.step import step

_logger = get_logger(__name__)

# Token CSRF dentro del formulario de login (Django: <input name="csrfmiddlewaretoken" value="...">).
_LOGIN_FORM_RE = re.compile(r'<form[^>]*action="/login"[^>]*>(.*?)</form>', re.DOTALL | re.IGNORECASE)
_CSRF_RE = re.compile(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"')
_LOGGED_IN_MARKER = "Logged in as"


class HttpLoginError(AssertionError):
    """El login por HTTP no dejó una sesión iniciada (precondición del test no cumplida)."""


@step("Login por HTTP como '{email}'")
def login_via_http(context: BrowserContext, base_url: str, email: str, password: str) -> None:
    """Inicia sesión enviando el formulario de login por HTTP dentro del contexto del navegador.

    Args:
        context: Contexto de navegador del test (las cookies quedan en él).
        base_url: URL base del sitio (sin barra final).
        email: Email del usuario registrado.
        password: Contraseña (se enmascara en logs y reportes).

    Raises:
        HttpLoginError: Si no se encontró el token CSRF o la respuesta no muestra la sesión iniciada.
    """
    login_url = f"{base_url}/login"
    page_html = context.request.get(login_url).text()
    form = _LOGIN_FORM_RE.search(page_html)
    token = _CSRF_RE.search(form.group(1)) if form else None
    if token is None:
        raise HttpLoginError(f"No se encontró el token CSRF del formulario de login en {login_url}")

    response = context.request.post(
        login_url,
        form={"csrfmiddlewaretoken": token.group(1), "email": email, "password": password},
        # Django valida el Referer en peticiones HTTPS con CSRF: se envía igual que un navegador.
        headers={"Referer": login_url},
    )
    # El login exitoso redirige a la home, que muestra "Logged in as <nombre>". Las redirecciones
    # se siguen automáticamente, así que se valida el contenido final.
    if not response.ok or _LOGGED_IN_MARKER not in response.text():
        raise HttpLoginError(
            f"El login por HTTP no inició sesión (HTTP {response.status} en {response.url}). "
            "¿Cambió el formulario de login o el usuario no existe?"
        )
    _logger.info("Sesión iniciada por HTTP para %s", email)
