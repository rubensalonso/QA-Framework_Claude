"""Clase base de todos los Page Objects.

Decisiones de diseño:

* **Page Object Model + Componentes**: lo que se repite en todas las páginas (header, footer
  de suscripción) es un componente reutilizable, no código duplicado en cada página.
* **Interfaz fluida**: cuando el destino es determinístico, el método devuelve la página
  destino ya verificada (``SignupPage.submit() -> AccountCreatedPage``), así el IDE guía el
  flujo y el test se lee como una historia. Si el destino depende del resultado (``login``
  válido o inválido), el método no devuelve nada y el test decide qué página verificar.
* **Sin esperas manuales**: ni ``time.sleep`` ni ``wait_for_timeout``. Playwright espera
  automáticamente a que los elementos sean accionables, y ``expect`` reintenta las aserciones
  hasta el timeout. Las "esperas" de este framework son siempre condiciones explícitas.
* **Aserciones de carga**: cada página define ``loaded_indicator``; ``open()`` y las
  transiciones verifican que la página correcta realmente cargó antes de seguir.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import ClassVar, Self

from playwright.sync_api import Locator, Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from framework.core.logger import get_logger
from framework.core.step import step
from framework.ui.browser_setup import SiteUnavailableError, site_unavailability_reason
from framework.ui.components.header import Header
from framework.ui.components.subscription import SubscriptionFooter

# Tolerancia de 2 px por redondeos de subpíxeles en pantallas con escalado.
_AT_DOCUMENT_BOTTOM_JS = "() => window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2"
_AT_DOCUMENT_TOP_JS = "() => window.scrollY <= 2"


class BasePage(ABC):
    """Comportamiento común a todas las páginas del sitio."""

    #: Ruta relativa al base_url (``/login``). Las páginas sin ruta propia la dejan en ``None``.
    PATH: ClassVar[str | None] = None
    #: Patrón que debe cumplir la URL cuando la página está cargada.
    URL_PATTERN: ClassVar[re.Pattern[str]]

    def __init__(self, page: Page) -> None:
        self.page = page
        self.header = Header(page)
        self.subscription = SubscriptionFooter(page)
        self.logger = get_logger(self.__class__.__name__)

    @property
    @abstractmethod
    def loaded_indicator(self) -> Locator:
        """Elemento cuya visibilidad garantiza que la página terminó de renderizar lo esencial."""

    @step("Abrir página {self.__class__.__name__}")
    def open(self) -> Self:
        """Navega directamente a la página y espera a que esté cargada.

        Returns:
            La propia página (para encadenar llamadas).

        Raises:
            NotImplementedError: Si la página no tiene URL propia (se llega a ella por un flujo).
        """
        if self.PATH is None:
            raise NotImplementedError(f"{self.__class__.__name__} no se puede abrir por URL directa")
        # wait_until="domcontentloaded": no esperamos a que carguen imágenes/fuentes de terceros,
        # solo al DOM. La visibilidad del loaded_indicator hace el resto.
        self.page.goto(self.PATH, wait_until="domcontentloaded")
        return self.should_be_loaded()

    def should_be_loaded(self) -> Self:
        """Aserta que la URL y el indicador de carga corresponden a esta página.

        Returns:
            La propia página.
        """
        try:
            expect(self.page).to_have_url(self.URL_PATTERN)
            expect(self.loaded_indicator).to_be_visible()
        except AssertionError as exc:
            # Diagnóstico explícito: sin esto, un bloqueo anti-bot se vería como "element not found"
            # y alguien perdería tiempo buscando un locator roto que en realidad está bien.
            reason = site_unavailability_reason(self.page)
            if reason:
                raise SiteUnavailableError(
                    f"{self.__class__.__name__}: en lugar del contenido, {reason}. Es un problema del "
                    "entorno, no del producto: reducir el paralelismo (-n) y reintentar más tarde."
                ) from exc
            raise
        return self

    @property
    def title(self) -> str:
        """Título del documento (``<title>``)."""
        return self.page.title()

    @step("Scroll hasta el final de la página")
    def scroll_to_bottom(self) -> None:
        """Hace scroll con la tecla ``End`` hasta el final real del documento."""
        self._scroll_with_key("End", _AT_DOCUMENT_BOTTOM_JS)

    @step("Scroll hasta el inicio de la página")
    def scroll_to_top(self) -> None:
        """Hace scroll con la tecla ``Home`` hasta el inicio real del documento."""
        self._scroll_with_key("Home", _AT_DOCUMENT_TOP_JS)

    def _scroll_with_key(self, key: str, reached_js: str, max_attempts: int = 5) -> None:
        """Presiona ``key`` hasta que se cumple la condición de posición ``reached_js``.

        Un único ``End``/``Home`` no alcanza en este sitio: la tecla apunta a una posición calculada
        *al presionarla*, pero las imágenes lazy cambian la altura del documento durante el scroll
        (medido: de ~4900 px a ~8300 px) y el *scroll anchoring* del navegador corrige la posición
        (medido: ``Home`` terminó en 470 px en lugar de 0). Se repite hasta cumplir la condición:
        espera por condición, sin tiempos fijos.

        Args:
            key: Tecla a presionar.
            reached_js: Función JS que devuelve ``true`` al llegar al destino.
            max_attempts: Intentos antes de fallar.

        Raises:
            AssertionError: Si tras ``max_attempts`` no se alcanzó el destino.
        """
        for attempt in range(1, max_attempts + 1):
            self.page.keyboard.press(key)
            try:
                self.page.wait_for_function(reached_js, timeout=1_500)
                return
            except PlaywrightTimeoutError:
                self.logger.debug("Intento %s con '%s': el layout cambió durante el scroll, reintentando", attempt, key)
        raise AssertionError(f"No se alcanzó la posición destino con '{key}' tras {max_attempts} intentos")
