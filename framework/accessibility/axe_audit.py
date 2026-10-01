"""Auditorías de accesibilidad con axe-core y comparación contra un baseline ("trinquete").

Decisiones de diseño:

* **axe-core**: el motor de reglas de accesibilidad más usado de la industria (WCAG 2.x). Se ejecuta
  dentro de la página, sobre el DOM real ya renderizado, incluido el contenido dinámico.
* **Baseline con trinquete (ratchet)**: un sitio existente casi siempre tiene violaciones previas.
  Exigir "cero violaciones" dejaría el test rojo para siempre y nadie lo miraría. En su lugar:

  - las violaciones conocidas se registran en ``test_data/a11y_baseline.json`` (versionado y revisable);
  - el test falla solo ante una violación **nueva** de impacto ``serious`` o ``critical``;
  - si una violación conocida desaparece, se avisa para quitarla del baseline (que solo puede achicarse).

  Así la accesibilidad solo puede mejorar: nunca empeorar en silencio.
* Las violaciones ``moderate``/``minor`` se reportan (Allure) pero no hacen fallar: priorizar lo que
  más impacta a personas con discapacidad, sin ahogar la señal en ruido.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import allure
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Page

from framework.config.settings import PROJECT_ROOT
from framework.core.logger import get_logger

_logger = get_logger(__name__)
_axe = Axe()

#: Estándares a auditar: WCAG 2.0 y 2.1, niveles A y AA (el requisito legal habitual).
WCAG_TAGS: tuple[str, ...] = ("wcag2a", "wcag2aa", "wcag21a", "wcag21aa")
#: Impactos que hacen fallar un test si la violación no está en el baseline.
BLOCKING_IMPACTS: frozenset[str] = frozenset({"serious", "critical"})

BASELINE_FILE: Path = PROJECT_ROOT / "test_data" / "a11y_baseline.json"
#: Resultados de cada corrida, para revisar o regenerar el baseline (scripts/update_a11y_baseline.py).
RESULTS_DIR: Path = PROJECT_ROOT / "reports" / "a11y"


@dataclass(frozen=True)
class AxeViolation:
    """Una regla de accesibilidad incumplida en una página."""

    rule_id: str
    impact: str
    description: str
    help_url: str
    nodes: int
    examples: tuple[str, ...]  # hasta 3 selectores de elementos afectados, para ubicarlos rápido

    @property
    def is_blocking(self) -> bool:
        """``True`` si el impacto es lo bastante grave como para hacer fallar un test."""
        return self.impact in BLOCKING_IMPACTS

    def __str__(self) -> str:
        return f"[{self.impact}] {self.rule_id}: {self.description} ({self.nodes} elemento/s, ej. {self.examples})"


def _to_violation(raw: dict[str, Any]) -> AxeViolation:
    nodes = raw.get("nodes", [])
    return AxeViolation(
        rule_id=raw["id"],
        impact=raw.get("impact") or "unknown",
        description=raw.get("help", ""),
        help_url=raw.get("helpUrl", ""),
        nodes=len(nodes),
        examples=tuple(str(n.get("target", [""])[0]) for n in nodes[:3]),
    )


def audit_page(page: Page, page_id: str, *, tags: Iterable[str] = WCAG_TAGS) -> list[AxeViolation]:
    """Ejecuta axe-core sobre la página actual y devuelve las violaciones encontradas.

    Los resultados se adjuntan a Allure y se guardan en ``reports/a11y/<page_id>.json``.

    Args:
        page: Página ya cargada en el estado a auditar.
        page_id: Identificador estable de la página (clave del baseline), p. ej. ``"home"``.
        tags: Etiquetas de reglas de axe a evaluar.

    Returns:
        Violaciones, ordenadas de mayor a menor impacto.
    """
    options = {"runOnly": {"type": "tag", "values": list(tags)}, "resultTypes": ["violations"]}
    results = _axe.run(page, options=options)
    order = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}
    violations = sorted(
        (_to_violation(v) for v in results.response.get("violations", [])),
        key=lambda v: (order.get(v.impact, 9), v.rule_id),
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps([asdict(v) for v in violations], indent=2, ensure_ascii=False)
    (RESULTS_DIR / f"{page_id}.json").write_text(payload, encoding="utf-8")
    allure.attach(payload, name=f"axe {page_id}", attachment_type=allure.attachment_type.JSON)
    _logger.info(
        "axe %s: %s violación/es (%s bloqueantes)", page_id, len(violations), sum(v.is_blocking for v in violations)
    )
    return violations


def load_baseline() -> dict[str, list[str]]:
    """Lee el baseline de violaciones conocidas (``{page_id: [rule_id, ...]}``)."""
    if not BASELINE_FILE.is_file():
        return {}
    data: dict[str, list[str]] = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    return data


@dataclass(frozen=True)
class BaselineComparison:
    """Resultado de comparar una auditoría con el baseline."""

    new_blocking: list[AxeViolation]  # violaciones graves que no estaban → el test falla
    fixed: list[str]  # reglas del baseline que ya no aparecen → actualizar el baseline


def compare_with_baseline(page_id: str, violations: list[AxeViolation]) -> BaselineComparison:
    """Compara las violaciones actuales con las conocidas para la página.

    Args:
        page_id: Clave de la página en el baseline.
        violations: Resultado de :func:`audit_page`.

    Returns:
        Violaciones graves nuevas y reglas del baseline que ya se corrigieron.
    """
    known = set(load_baseline().get(page_id, []))
    current = {v.rule_id for v in violations}
    return BaselineComparison(
        new_blocking=[v for v in violations if v.is_blocking and v.rule_id not in known],
        fixed=sorted(known - current),
    )
