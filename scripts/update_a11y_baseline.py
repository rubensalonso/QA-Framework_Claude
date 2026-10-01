"""Regenera ``test_data/a11y_baseline.json`` a partir de la última auditoría de accesibilidad.

Uso::

    pytest -m a11y                                   # genera reports/a11y/<pagina>.json
    python scripts/update_a11y_baseline.py           # muestra los cambios y actualiza el baseline
    python scripts/update_a11y_baseline.py --dry-run # solo muestra los cambios

También acepta otra carpeta de resultados (p. ej. la descargada de un artifact de CI)::

    python scripts/update_a11y_baseline.py --results ruta/a/reports/a11y

Decisión de diseño: el baseline guarda solo las reglas BLOQUEANTES (serious/critical), que son las
únicas que el test compara. Cada cambio se imprime para revisarlo en el diff del PR: agregar una regla
al baseline es aceptar una deuda de accesibilidad y debe ser una decisión explícita, no automática.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.accessibility.axe_audit import BASELINE_FILE, BLOCKING_IMPACTS, RESULTS_DIR  # noqa: E402


def main() -> int:
    """Punto de entrada CLI."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", type=Path, default=RESULTS_DIR, help="carpeta con los <pagina>.json de axe")
    parser.add_argument("--dry-run", action="store_true", help="mostrar cambios sin escribir")
    args = parser.parse_args()

    # Los fixtures de los tests del motor (fixture-*) no son páginas del sitio.
    result_files = sorted(f for f in args.results.glob("*.json") if not f.stem.startswith("fixture"))
    if not result_files:
        print(f"[ERROR] No hay resultados en {args.results}. Corré antes: pytest -m a11y")
        return 1

    baseline: dict[str, list[str]] = (
        json.loads(BASELINE_FILE.read_text(encoding="utf-8")) if BASELINE_FILE.is_file() else {}
    )
    for result_file in result_files:
        violations = json.loads(result_file.read_text(encoding="utf-8"))
        current = sorted({v["rule_id"] for v in violations if v["impact"] in BLOCKING_IMPACTS})
        previous = baseline.get(result_file.stem, [])
        added, removed = sorted(set(current) - set(previous)), sorted(set(previous) - set(current))
        if added or removed:
            print(f"{result_file.stem}: +{added or '-'}  -{removed or '-'}")
        baseline[result_file.stem] = current

    if args.dry_run:
        print("[DRY-RUN] No se escribió el baseline.")
        return 0
    BASELINE_FILE.write_bytes((json.dumps(dict(sorted(baseline.items())), indent=2) + "\n").encode("utf-8"))
    print(f"[OK] Baseline actualizado: {BASELINE_FILE.relative_to(ROOT)}. Revisá el diff antes de commitear.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
