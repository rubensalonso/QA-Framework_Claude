"""Decorador ``@step``: un único punto para loguear y reportar acciones de negocio.

Decisión de diseño: en vez de escribir ``logger.info`` + ``allure.step`` en cada método de
Page Object, se decora el método una vez. Resultado:

* El log de texto y el reporte de Allure cuentan la misma historia, paso a paso.
* Los argumentos sensibles (``password``, ``card``...) se enmascaran automáticamente,
  así que nunca terminan en un reporte que se comparte con el equipo.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

import allure

from framework.core.logger import MASK, SENSITIVE_KEYS, get_logger

P = ParamSpec("P")
R = TypeVar("R")

_logger = get_logger("steps")
# Argumentos que se enmascaran aunque no estén en SENSITIVE_KEYS (objetos completos con secretos).
_SENSITIVE_ARGS: frozenset[str] = SENSITIVE_KEYS | {"card"}


def _render_title(template: str, func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """Interpola el título con los argumentos reales de la llamada, enmascarando secretos."""
    try:
        bound = inspect.signature(func).bind(*args, **kwargs)
        bound.apply_defaults()
        values = {k: (MASK if k in _SENSITIVE_ARGS else v) for k, v in bound.arguments.items()}
        return template.format(**values)
    except (KeyError, IndexError, TypeError, ValueError):
        # Un título mal formateado nunca debe romper el test: se usa el template literal.
        return template


def step(title: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Marca un método como paso de negocio (log + paso de Allure).

    El título admite placeholders con el nombre de los parámetros, p. ej.
    ``@step("Buscar producto '{term}'")``.

    Args:
        title: Descripción legible del paso.

    Returns:
        Decorador que preserva la firma y los type hints del método original.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            rendered = _render_title(title, func, args, kwargs)
            _logger.info("STEP ▶ %s", rendered)
            with allure.step(rendered):
                return func(*args, **kwargs)

        return wrapper

    return decorator
