"""Fixtures y hooks compartidos por todas las suites (UI, API y performance).

Mapa de fixtures (scope → propósito):

* ``settings`` (session): configuración tipada.
* ``base_url`` (session): override del plugin pytest-base-url → toma la URL de ``settings``
  salvo que se pase ``--base-url`` por CLI.
* ``site_available`` (session): chequeo previo de que el sitio no está detrás de un muro anti-bot.
* ``page`` (function): extiende el ``page`` de pytest-playwright con timeouts, bloqueo de
  publicidad y manejo de overlays. Cada test recibe un contexto de navegador nuevo y aislado.
* ``api_request_context`` / ``api`` (session): cliente HTTP reutilizado por todo el worker.
* ``new_user`` (function): datos de usuario únicos, **no** registrados.
* ``registered_user`` (function): usuario creado vía API y eliminado al terminar el test.
* ``account_cleanup`` (function): registro de cuentas creadas por la UI para borrarlas
  aunque el test falle a mitad de camino.
"""

from __future__ import annotations

import base64
import os
import platform
from collections.abc import Callable, Generator, Iterator
from pathlib import Path
from typing import Any

import allure
import pytest
from playwright.sync_api import APIRequestContext, Browser, Page, Playwright, expect

from framework.api import AutomationExerciseApi
from framework.config import Settings, get_settings
from framework.config.settings import PROJECT_ROOT
from framework.core.logger import configure_logging, get_logger
from framework.data import User, UserFactory
from framework.ui.browser_setup import (
    SiteUnavailableError,
    block_third_party_ads,
    is_bot_challenge,
    register_overlay_handlers,
)

logger = get_logger("conftest")


# =============================================================================
# Hooks de configuración
# =============================================================================
def pytest_configure(config: pytest.Config) -> None:
    """Inicializa logging, timeouts de aserción y carpetas de reportes."""
    settings = get_settings()
    # Con xdist, cada worker expone su id en esta variable (gw0, gw1...); sin xdist no existe.
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    log_file = configure_logging(settings.log_level, settings.log_dir, worker_id)
    (PROJECT_ROOT / "reports").mkdir(exist_ok=True)

    # Timeout global de `expect`: sube el default de Playwright (5 s) para un sitio público lento.
    expect.set_options(timeout=settings.expect_timeout_ms)
    logger.info("Sesión iniciada | worker=%s | base_url=%s | log=%s", worker_id, settings.base_url, log_file)


def pytest_sessionfinish(session: pytest.Session) -> None:
    """Escribe ``environment.properties`` para el widget 'Environment' de Allure.

    Solo lo hace el proceso controlador (no los workers de xdist) para no pisar el archivo.
    """
    if hasattr(session.config, "workerinput"):
        return
    allure_dir = session.config.getoption("--alluredir", default=None)
    if not allure_dir:
        return
    settings = get_settings()
    path = Path(allure_dir)
    path.mkdir(parents=True, exist_ok=True)
    browsers = session.config.getoption("--browser", default=None) or ["chromium"]
    properties = {
        "Base.URL": settings.base_url,
        "API.URL": settings.api_base_url,
        "Browsers": ",".join(browsers),
        "Ads.Blocked": settings.block_ads,
        "Python": platform.python_version(),
        "OS": platform.platform(terse=True),
    }
    (path / "environment.properties").write_text("\n".join(f"{k}={v}" for k, v in properties.items()), encoding="utf-8")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Generator[None, Any, None]:
    """Adjunta evidencia visual a Allure y pytest-html cuando falla un test de UI.

    Decisión de diseño: se hace en el hook (y no en una fixture) porque es el único punto
    donde se conoce el resultado del test *mientras el navegador sigue abierto*. Las fixtures
    de pytest-playwright cierran el contexto después, en el teardown.
    """
    outcome = yield
    report: pytest.TestReport = outcome.get_result()
    if report.when != "call" or not report.failed:
        return

    page: Page | None = getattr(item, "funcargs", {}).get("page")
    if page is None or page.is_closed():
        return

    try:
        screenshot = page.screenshot(full_page=True)
    except Exception as exc:  # noqa: BLE001 - la evidencia nunca debe ocultar el fallo original
        logger.warning("No se pudo capturar screenshot del fallo: %s", exc)
        return

    allure.attach(screenshot, name="screenshot-on-failure", attachment_type=allure.attachment_type.PNG)
    allure.attach(page.url, name="url-on-failure", attachment_type=allure.attachment_type.URI_LIST)

    html_plugin = item.config.pluginmanager.getplugin("html")
    if html_plugin is not None:
        extras = getattr(report, "extras", [])
        extras.append(html_plugin.extras.png(base64.b64encode(screenshot).decode(), name="Screenshot"))
        extras.append(html_plugin.extras.url(page.url, name="URL al fallar"))
        report.extras = extras


# =============================================================================
# Configuración
# =============================================================================
@pytest.fixture(scope="session")
def settings() -> Settings:
    """Configuración de la ejecución."""
    return get_settings()


@pytest.fixture(scope="session")
def base_url(request: pytest.FixtureRequest, settings: Settings) -> str:
    """URL base del sitio. ``--base-url`` por CLI tiene prioridad sobre ``QA_BASE_URL``."""
    cli_value: str | None = request.config.getoption("base_url", default=None)
    return (cli_value or settings.base_url).rstrip("/")


# =============================================================================
# Navegador
# =============================================================================
@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Extiende los argumentos del contexto definidos por pytest-playwright.

    Viewport y locale fijos → renderizado determinístico (evita que el layout responsive
    cambie entre la máquina del desarrollador y el runner de CI).
    """
    return {
        **browser_context_args,
        "viewport": {"width": settings.viewport_width, "height": settings.viewport_height},
        "locale": settings.locale,
        "accept_downloads": True,
    }


@pytest.fixture(scope="session")
def site_available(browser: Browser, base_url: str, settings: Settings) -> None:
    """Verifica una vez por worker que el sitio sirve contenido real y no un muro anti-bot.

    Decisión de diseño: si el entorno no está disponible, todos los tests de UI terminan en
    ERROR (fallo de *setup*, no de producto) con un único mensaje claro, en vez de esperar
    el timeout de cada test. Pytest cachea la excepción de una fixture de sesión, así que el
    chequeo se hace una sola vez. Se usa un navegador real (no un cliente HTTP) porque la
    protección puede tratar distinto a ambos.
    """
    context = browser.new_context()
    try:
        if settings.block_ads:
            block_third_party_ads(context)
        probe = context.new_page()
        probe.goto(base_url, wait_until="domcontentloaded", timeout=settings.navigation_timeout_ms)
        title = probe.title()
    finally:
        context.close()
    if is_bot_challenge(title):
        raise SiteUnavailableError(
            f"{base_url} responde con una verificación anti-bot ('{title}'). El framework no la evade: "
            "esperá unos minutos, reducí el paralelismo (-n 2) o usá otra red/entorno."
        )
    logger.info("Chequeo de disponibilidad OK: '%s'", title)


@pytest.fixture
def page(page: Page, settings: Settings, site_available: None) -> Page:
    """Página de Playwright endurecida para este sitio.

    Extiende (no reemplaza) la fixture original de pytest-playwright, así se conservan
    tracing, video y screenshots configurados por CLI.
    """
    context = page.context
    context.set_default_timeout(settings.default_timeout_ms)
    context.set_default_navigation_timeout(settings.navigation_timeout_ms)
    if settings.block_ads:
        block_third_party_ads(context)
    register_overlay_handlers(page)
    return page


# =============================================================================
# API
# =============================================================================
@pytest.fixture(scope="session")
def api_request_context(playwright: Playwright, settings: Settings) -> Iterator[APIRequestContext]:
    """Contexto HTTP compartido por todo el worker (reutiliza conexiones → más rápido)."""
    context = playwright.request.new_context(
        base_url=settings.api_base_url,
        extra_http_headers={"Accept": "application/json"},
        timeout=settings.api_timeout_ms,
    )
    yield context
    context.dispose()


@pytest.fixture(scope="session")
def api(api_request_context: APIRequestContext, settings: Settings) -> AutomationExerciseApi:
    """Cliente de dominio de la API de AutomationExercise."""
    return AutomationExerciseApi(
        api_request_context,
        timeout_ms=settings.api_timeout_ms,
        max_retries=settings.api_max_retries,
        backoff_s=settings.api_retry_backoff_s,
    )


# =============================================================================
# Datos de prueba
# =============================================================================
@pytest.fixture
def new_user() -> User:
    """Usuario con datos únicos, aún no registrado en el sistema."""
    return UserFactory.build()


@pytest.fixture
def account_cleanup(api: AutomationExerciseApi) -> Iterator[Callable[[User], None]]:
    """Registra cuentas para eliminarlas vía API al final del test, pase o falle.

    Uso::

        def test_signup(page, new_user, account_cleanup):
            account_cleanup(new_user)   # registrar ANTES de crear la cuenta
            ...

    Decisión de diseño: si el test ya borró la cuenta (p. ej. validando 'Delete Account'),
    la API responde 404 y se ignora. La limpieza nunca hace fallar un test que pasó.
    """
    registered: list[User] = []
    yield registered.append
    for user in registered:
        try:
            response = api.delete_account(user.email, user.password)
            logger.info("Cleanup %s → responseCode=%s", user.email, response.response_code)
        except Exception as exc:  # noqa: BLE001 - la limpieza es best-effort
            logger.warning("No se pudo limpiar la cuenta %s: %s", user.email, exc)


@pytest.fixture
def registered_user(api: AutomationExerciseApi, account_cleanup: Callable[[User], None]) -> User:
    """Usuario ya registrado (creado vía API: ~10x más rápido que por UI).

    Decisión de diseño: *arrange por API, act/assert por UI*. Los tests de login o checkout
    no deberían depender de que el formulario de registro funcione; eso tiene su propio test.
    """
    user = UserFactory.build()
    account_cleanup(user)
    response = api.create_account(user)
    # Fallar en el setup (ERROR, no FAILED) deja claro que el problema es la precondición.
    assert response.response_code == 201, f"No se pudo crear el usuario de prueba: {response.text}"
    return user
