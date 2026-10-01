"""UI — Accesibilidad (WCAG 2.1 A/AA) con axe-core y baseline de violaciones conocidas.

Ver ``framework/accessibility/axe_audit.py`` para el diseño del "trinquete" (baseline que solo se achica).
Regenerar el baseline tras revisar los resultados: ``python scripts/update_a11y_baseline.py``.
"""

from __future__ import annotations

import json
import warnings
from collections.abc import Iterator
from pathlib import Path

import allure
import pytest
from playwright.sync_api import Browser, Page

from framework.accessibility import axe_audit
from framework.accessibility.axe_audit import audit_page, compare_with_baseline

pytestmark = [pytest.mark.ui, pytest.mark.a11y]

# Página con violaciones conocidas, para validar el motor sin depender del sitio (corre offline).
_INACCESSIBLE_HTML = """
<!doctype html><html lang="es"><head><title>Fixture a11y</title></head><body>
  <main>
    <h1>Página de prueba</h1>
    <img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=">        <!-- sin alt: image-alt -->
    <button></button>                                            <!-- sin nombre: button-name -->
    <p style="color:#bbb;background:#fff">Texto con bajo contraste</p>  <!-- color-contrast -->
  </main>
</body></html>
"""
_ACCESSIBLE_HTML = """
<!doctype html><html lang="es"><head><title>Fixture accesible</title></head><body>
  <main><h1>Página accesible</h1>
    <img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" alt="Logo">
    <button>Enviar</button><p>Texto con buen contraste</p></main>
</body></html>
"""


class A11yBaselineOutdatedWarning(UserWarning):
    """Una violación registrada en el baseline ya no aparece: el baseline se puede achicar."""


@pytest.fixture
def offline_page(browser: Browser) -> Iterator[Page]:
    """Página aislada que no navega al sitio (no depende de su disponibilidad)."""
    context = browser.new_context()
    yield context.new_page()
    context.close()


@allure.epic("Accesibilidad")
@allure.feature("Motor de auditoría")
class TestAxeEngine:
    """Valida el propio framework de accesibilidad contra HTML controlado."""

    @allure.title("axe detecta violaciones conocidas en una página inaccesible")
    def test_detects_known_violations(self, offline_page: Page):
        offline_page.set_content(_INACCESSIBLE_HTML)

        violations = audit_page(offline_page, "fixture-inaccesible")

        rules = {v.rule_id for v in violations}
        assert {"image-alt", "button-name", "color-contrast"} <= rules, f"Reglas detectadas: {rules}"
        assert all(v.nodes >= 1 and v.help_url for v in violations)

    @allure.title("Una página accesible no tiene violaciones")
    def test_accessible_page_is_clean(self, offline_page: Page):
        offline_page.set_content(_ACCESSIBLE_HTML)

        assert audit_page(offline_page, "fixture-accesible") == []

    @allure.title("El baseline tolera lo conocido, bloquea lo nuevo y detecta lo corregido")
    def test_baseline_ratchet(self, offline_page: Page, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        baseline = tmp_path / "baseline.json"
        # image-alt es conocida; landmark-xyz figura en el baseline pero ya no ocurre (corregida).
        baseline.write_text(json.dumps({"fixture": ["image-alt", "landmark-xyz"]}), encoding="utf-8")
        monkeypatch.setattr(axe_audit, "BASELINE_FILE", baseline)
        offline_page.set_content(_INACCESSIBLE_HTML)

        result = compare_with_baseline("fixture", audit_page(offline_page, "fixture"))

        new_rules = {v.rule_id for v in result.new_blocking}
        assert "image-alt" not in new_rules, "Una violación conocida no debe bloquear"
        assert "button-name" in new_rules, "Una violación grave nueva debe bloquear"
        assert result.fixed == ["landmark-xyz"]


@allure.epic("Accesibilidad")
@allure.feature("WCAG 2.1 AA en el sitio")
@pytest.mark.regression
@pytest.mark.only_browser("chromium")  # las reglas de axe no dependen del navegador: una corrida alcanza
class TestSiteAccessibility:
    """Auditoría de las páginas principales contra el baseline."""

    @pytest.mark.parametrize(
        ("page_id", "path"),
        [
            ("home", "/"),
            ("products", "/products"),
            ("product-detail", "/product_details/1"),
            ("login", "/login"),
            ("cart", "/view_cart"),
            ("contact", "/contact_us"),
        ],
    )
    @allure.title("Sin violaciones de accesibilidad graves nuevas: {page_id}")
    def test_no_new_serious_violations(self, page: Page, page_id, path):
        page.goto(path, wait_until="load")

        result = compare_with_baseline(page_id, audit_page(page, page_id))

        if result.fixed:
            warnings.warn(
                f"{page_id}: ya no ocurren {result.fixed}. Quitarlas del baseline "
                "(python scripts/update_a11y_baseline.py) para que no puedan volver sin que el test lo note.",
                A11yBaselineOutdatedWarning,
                stacklevel=1,
            )
        assert not result.new_blocking, f"{page_id}: violaciones graves nuevas:\n" + "\n".join(
            f"  - {v}  → {v.help_url}" for v in result.new_blocking
        )
