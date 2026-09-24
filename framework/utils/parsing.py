"""Helpers puros de parseo (sin dependencias de Playwright → testeables de forma aislada)."""

from __future__ import annotations

import re

_PRICE_RE = re.compile(r"Rs\.\s*(\d[\d,]*)")


def parse_price(text: str) -> int:
    """Convierte un precio mostrado por el sitio a entero.

    Args:
        text: Texto tal como aparece en pantalla, p. ej. ``"Rs. 1,500"``.

    Returns:
        Importe entero en rupias (``1500``).

    Raises:
        ValueError: Si el texto no contiene un precio con el formato esperado. Se falla
            explícitamente en vez de devolver 0, que ocultaría un bug de UI.
    """
    match = _PRICE_RE.search(text)
    if not match:
        raise ValueError(f"No se pudo interpretar el precio: {text!r}")
    return int(match.group(1).replace(",", ""))
