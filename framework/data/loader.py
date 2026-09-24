"""Carga de datos estáticos para tests data-driven (archivos en ``test_data/``)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from framework.config.settings import PROJECT_ROOT

TEST_DATA_DIR: Path = PROJECT_ROOT / "test_data"


@lru_cache(maxsize=32)
def load_json(file_name: str) -> Any:
    """Lee y cachea un archivo JSON de ``test_data/``.

    Se cachea porque ``pytest.mark.parametrize`` lo evalúa en la fase de colección,
    y con xdist cada worker colecciona de nuevo.

    Args:
        file_name: Nombre del archivo (``"negative_logins.json"``).

    Returns:
        Contenido deserializado.

    Raises:
        FileNotFoundError: Con la ruta absoluta, para que el error sea autoexplicativo.
    """
    path = TEST_DATA_DIR / file_name
    if not path.is_file():
        raise FileNotFoundError(f"No existe el archivo de datos de prueba: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def data_file(file_name: str) -> Path:
    """Devuelve la ruta absoluta de un archivo de ``test_data/`` (p. ej. para uploads).

    Args:
        file_name: Nombre del archivo.

    Returns:
        Ruta absoluta existente.

    Raises:
        FileNotFoundError: Si el archivo no existe.
    """
    path = TEST_DATA_DIR / file_name
    if not path.is_file():
        raise FileNotFoundError(f"No existe el archivo de datos de prueba: {path}")
    return path
