"""UI — Comportamiento en dispositivos móviles (emulación de Playwright).

Se ejecutan solo con un perfil de dispositivo; sin él se saltean::

    pytest -m mobile --device "Pixel 7"
    pytest -m "(smoke and ui) or mobile" --device "Pixel 7"   # smoke completo en móvil (CI nightly)

Decisión de diseño: la emulación de Playwright reproduce viewport, densidad de píxeles, user agent
y eventos táctiles del dispositivo. No reemplaza probar en un teléfono real (motor de renderizado,
rendimiento), pero detecta en CI la mayoría de los defectos responsive a costo casi cero.
"""

from __future__ import annotations

import allure
import pytest
from playwright.sync_api import Page, expect

from framework.ui.pages import ProductDetailPage

pytestmark = [
    pytest.mark.ui,
    pytest.mark.mobile,
    # Condición como string: pytest la evalúa en la fase de COLECCIÓN, con `config` disponible.
    # Así el test se saltea antes de crear fixtures (un fixture autouse llegaría tarde: las
    # fixtures de sesión, como el chequeo de disponibilidad del sitio, se resuelven antes).
    pytest.mark.skipif(
        'not config.getoption("--device")',
        reason='Requiere emulación móvil: agregar --device "Pixel 7" (u otro perfil de Playwright)',
    ),
]

RESPONSIVE_PAGES = [
    pytest.param("/", id="home"),
    pytest.param("/products", id="products"),
    pytest.param("/product_details/1", id="product-detail"),
    pytest.param("/login", id="login"),
    pytest.param("/view_cart", id="cart"),
    pytest.param("/contact_us", id="contact"),
]


@allure.epic("UI")
@allure.feature("Responsive / móvil")
class TestMobileLayout:
    """Layout y gestos táctiles en viewport de teléfono."""

    @pytest.mark.parametrize("path", RESPONSIVE_PAGES)
    @allure.title("Sin scroll horizontal en móvil: {path}")
    def test_no_horizontal_overflow(self, page: Page, path):
        page.goto(path, wait_until="load")

        # scrollWidth > clientWidth = algún elemento es más ancho que la pantalla y obliga a
        # desplazarse de costado. Tolerancia de 1 px por redondeos de subpíxeles.
        overflow = page.evaluate(
            """() => {
                const doc = document.documentElement;
                const widest = [...document.body.querySelectorAll('*')]
                    .filter(el => el.getBoundingClientRect().right > doc.clientWidth + 1)
                    .slice(0, 5)
                    .map(el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '')
                              + (el.className && typeof el.className === 'string'
                                 ? '.' + el.className.trim().split(/\\s+/).join('.') : ''));
                return {scroll: doc.scrollWidth, client: doc.clientWidth, culprits: widest};
            }"""
        )
        assert overflow["scroll"] <= overflow["client"] + 1, (
            f"{path}: el contenido mide {overflow['scroll']}px y la pantalla {overflow['client']}px. "
            f"Elementos que desbordan: {overflow['culprits']}"
        )

    @allure.title("Agregar al carrito con un toque (tap) en el detalle de producto")
    def test_add_to_cart_with_tap(self, page: Page):
        detail = ProductDetailPage(page).open_product(1)

        # tap() dispara eventos táctiles reales (touchstart/touchend), no un click de mouse.
        with page.expect_response(lambda r: "/add_to_cart/" in r.url):
            detail.add_to_cart_button.tap()

        detail.cart_modal.should_be_visible()
        expect(detail.cart_modal.view_cart_link).to_be_visible()
