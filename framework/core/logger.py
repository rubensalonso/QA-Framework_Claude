"""Logging del framework.

Decisiones de diseño:

* Todos los loggers cuelgan de un namespace común (``framework``) para poder
  configurarlos juntos sin tocar loggers de librerías de terceros (urllib3, asyncio, etc.).
* No se agregan handlers de consola: pytest ya captura los logs y los muestra en el
  reporte cuando un test falla (o en vivo con ``-o log_cli=true``). Duplicarlos ensucia la salida.
* Sí se agrega un ``FileHandler`` por proceso: con ``pytest-xdist`` cada worker escribe
  su propio archivo (``gw0``, ``gw1``...) y así se evitan líneas intercaladas o archivos pisados.
"""

from __future__ import annotations

import logging
from pathlib import Path

LOGGER_NAMESPACE = "framework"
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

# Claves cuyo valor nunca debe llegar a un log (ni a un reporte que se comparte).
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {"password", "passwd", "card_number", "cvc", "cvv", "token", "authorization"}
)
MASK = "***"


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger dentro del namespace del framework.

    Args:
        name: Normalmente ``__name__`` del módulo que loguea.

    Returns:
        Logger hijo de ``framework`` (hereda nivel y handlers).
    """
    if name == LOGGER_NAMESPACE or name.startswith(f"{LOGGER_NAMESPACE}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{LOGGER_NAMESPACE}.{name}")


def configure_logging(level: str, log_dir: Path, worker_id: str = "main") -> Path:
    """Configura el logger raíz del framework con un archivo por worker.

    Es idempotente: si se llama dos veces (p. ej. al recargar el conftest) no duplica handlers.

    Args:
        level: Nivel mínimo (``DEBUG``, ``INFO``...).
        log_dir: Carpeta donde se escriben los archivos.
        worker_id: Identificador del proceso (``main`` o ``gwN`` con xdist).

    Returns:
        Ruta del archivo de log creado.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"test_run_{worker_id}.log"

    root = logging.getLogger(LOGGER_NAMESPACE)
    root.setLevel(level)

    already_configured = any(
        isinstance(h, logging.FileHandler) and Path(h.baseFilename) == log_file.resolve() for h in root.handlers
    )
    if not already_configured:
        handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        root.addHandler(handler)

    return log_file


def mask_sensitive(data: dict[str, object] | None) -> dict[str, object] | None:
    """Devuelve una copia del diccionario con los valores sensibles enmascarados.

    Args:
        data: Payload a sanitizar (form data, query params, headers).

    Returns:
        Copia sanitizada, o ``None`` si la entrada era ``None``.
    """
    if data is None:
        return None
    return {k: (MASK if k.lower() in SENSITIVE_KEYS else v) for k, v in data.items()}
