"""Endurecimiento del navegador contra ruido externo (publicidad, banners, popups).

AutomationExercise monetiza con Google Ads. En la práctica eso causa:

* **Vignette ads**: un anuncio a pantalla completa que intercepta la navegación y agrega
  ``#google_vignette`` a la URL → clicks perdidos y aserciones de URL fallidas.
* **Iframes de anuncios** que desplazan el layout mientras Playwright intenta hacer click.
* **Banner de consentimiento** (Funding Choices) en regiones con GDPR.
* Cargas lentas por scripts de terceros → timeouts intermitentes.

Decisión de diseño: bloquear esas peticiones a nivel de red (``context.route``) en vez de
"cerrar popups" reactivamente. Es más rápido, determinístico y no depende del DOM del anuncio.
Como red de seguridad, ``page.add_locator_handler`` descarta el banner de consentimiento si
aun así aparece (API oficial de Playwright para overlays impredecibles).
"""

from __future__ import annotations

import re

from playwright.sync_api import BrowserContext, Page, Route
from playwright.sync_api import Error as PlaywrightError

from framework.core.logger import get_logger

_logger = get_logger(__name__)

# Dominios de publicidad/tracking observados en el sitio. Regex compilada una sola vez:
# ``context.route`` solo intercepta las URLs que matchean, el resto no paga overhead.
AD_DOMAINS_PATTERN: re.Pattern[str] = re.compile(
    r"https?://([^/]+\.)?("
    r"googlesyndication\.com|doubleclick\.net|googleadservices\.com|adservice\.google\.[a-z.]+|"
    r"google-analytics\.com|googletagmanager\.com|googletagservices\.com|"
    r"fundingchoicesmessages\.google\.com|adtrafficquality\.google|"
    r"amazon-adsystem\.com|criteo\.(com|net)|taboola\.com|outbrain\.com"
    r")(/|$)"
)


# Títulos de páginas de verificación anti-bot o bloqueo del WAF (Cloudflare / Imunify360),
# observados en varios idiomas. Si el sitio entero devuelve una de estas, no hay nada que testear.
BOT_CHALLENGE_MARKERS: tuple[str, ...] = (
    "One moment, please",
    "Just a moment",
    "Un momento",
    "Attention Required",
    "403 Forbidden",
)


class SiteUnavailableError(AssertionError):
    """El sitio respondió con una verificación anti-bot en lugar del contenido real.

    Hereda de ``AssertionError`` para que pytest lo muestre como fallo con mensaje claro.
    Decisión de diseño: el framework **detecta y reporta** el bloqueo; no intenta evadirlo.
    Saltear protecciones anti-bot de un sitio de terceros no es una práctica aceptable.
    """


# Textos de la página de sobrecarga del hosting (observada en CI: "under heavy load (queue full)").
# No tiene un título distintivo, por eso se detecta por el contenido.
OVERLOAD_MARKERS: tuple[str, ...] = (
    "under heavy load",
    "too many people are accessing this website",
)


class BackendUnavailableError(SiteUnavailableError):
    """Una petición AJAX disparada por la UI recibió un 5xx del backend.

    Caso real observado en CI: ``GET /delete_cart/1 → 503``. El JavaScript del sitio no maneja
    el error (solo actúa en ``success``), así que la UI no cambia ni avisa nada. Sin esta
    detección, el test esperaba el timeout completo y fallaba con un "expected to be hidden"
    que no explicaba la causa. Hereda de :class:`SiteUnavailableError`: es un fallo de entorno.
    """


def is_bot_challenge(title: str) -> bool:
    """Indica si un título de página corresponde a una verificación anti-bot.

    Args:
        title: Título del documento HTML.
    """
    return any(marker.lower() in title.lower() for marker in BOT_CHALLENGE_MARKERS)


def site_unavailability_reason(page: Page) -> str | None:
    """Diagnostica si la página actual es un muro del entorno en vez del contenido del sitio.

    Se usa al fallar un test para separar **fallos de entorno** (WAF, sobrecarga del hosting)
    de **fallos de producto**, que es lo primero que hay que saber al hacer triage.

    Args:
        page: Página a inspeccionar.

    Returns:
        Descripción del problema, o ``None`` si la página parece contenido real.
    """
    try:
        title = page.title()
        if is_bot_challenge(title):
            return f"verificación anti-bot / bloqueo del WAF ('{title}')"
        # Solo el comienzo del body: las páginas de error son cortas y así se evita leer el DOM entero.
        body = page.evaluate("() => (document.body ? document.body.innerText : '').slice(0, 1000)").lower()
    except PlaywrightError:  # página cerrada o navegando: no hay diagnóstico posible
        return None
    if any(marker in body for marker in OVERLOAD_MARKERS):
        return "el hosting respondió que está sobrecargado ('under heavy load')"
    return None


def _abort_route(route: Route) -> None:
    """Aborta la petición interceptada (se registra en DEBUG para no inundar el log)."""
    _logger.debug("Bloqueada petición de publicidad: %s", route.request.url)
    route.abort()


def block_third_party_ads(context: BrowserContext) -> None:
    """Registra el bloqueo de publicidad para todas las páginas del contexto.

    Args:
        context: Contexto de navegador recién creado (antes de abrir páginas).
    """
    context.route(AD_DOMAINS_PATTERN, _abort_route)
    _logger.info("Bloqueo de publicidad de terceros activado")


def register_overlay_handlers(page: Page) -> None:
    """Descarta automáticamente overlays que pueden aparecer en cualquier momento.

    ``add_locator_handler`` se ejecuta *solo* cuando el overlay es visible y bloquea una
    acción, así que no agrega esperas en el camino feliz.

    Args:
        page: Página a proteger.
    """
    consent_dialog = page.locator(".fc-consent-root")

    def _dismiss_consent() -> None:
        # Opción más respetuosa de la privacidad primero; si no existe, se acepta para continuar.
        reject = consent_dialog.locator(".fc-cta-do-not-consent")
        target = reject if reject.count() else consent_dialog.locator(".fc-cta-consent")
        _logger.info("Banner de consentimiento detectado, descartándolo")
        target.first.click()

    page.add_locator_handler(consent_dialog, _dismiss_consent)
