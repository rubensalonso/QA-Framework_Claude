"""Regenera (o verifica) los archivos de dependencias fijadas a partir de los ``.in``.

Uso::

    python scripts/compile_requirements.py            # regenera requirements*.txt
    python scripts/compile_requirements.py --upgrade  # además sube todo a la última versión permitida
    python scripts/compile_requirements.py --check    # falla si los .txt no corresponden a los .in (CI)

Decisiones de diseño:

* ``uv pip compile --universal``: resuelve para TODAS las plataformas a la vez y agrega marcadores de
  entorno (``pywin32==312 ; sys_platform == 'win32'``). ``pip-compile`` resuelve solo para la máquina
  donde corre: compilado en Windows fijaba ``pywin32``, que no existe en Linux y rompía el CI.
* ``--python-version 3.11``: la versión mínima soportada; garantiza que el lock sirve de 3.11 en adelante.
* Un único script con los argumentos exactos: el header del archivo, la regeneración manual y el
  chequeo de CI usan el mismo comando, así que nunca difieren por un flag.
* Sin ``--upgrade``, uv conserva las versiones ya fijadas: regenerar no cambia nada salvo que se haya
  editado un ``.in``. Por eso ``--check`` es determinístico.
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# El orden importa: requirements-dev.in usa `-c requirements.txt`, que debe estar actualizado antes.
TARGETS: tuple[tuple[str, str], ...] = (
    ("requirements.in", "requirements.txt"),
    ("requirements-dev.in", "requirements-dev.txt"),
)
PYTHON_MIN = "3.11"


def _uv() -> str:
    """Ubica el ejecutable de uv (instalado vía requirements-dev.txt)."""
    exe = shutil.which("uv")
    if exe is None:
        sys.exit("No se encontró 'uv'. Instalalo con: pip install -r requirements-dev.txt")
    return exe


def compile_file(source: str, output: Path, *, upgrade: bool, seed: Path | None = None) -> None:
    """Compila ``source`` hacia ``output`` con los flags canónicos del proyecto.

    Args:
        source: Archivo ``.in`` relativo a la raíz.
        output: Ruta del ``.txt`` a generar.
        upgrade: Si ``True``, ignora las versiones fijadas y toma las últimas permitidas.
        seed: ``.txt`` existente cuyas versiones se conservan (se copia a ``output`` antes de compilar).
    """
    if seed is not None and seed.exists():
        shutil.copyfile(seed, output)
    canonical_output = dict(TARGETS)[source]
    command = [
        _uv(),
        "pip",
        "compile",
        source,
        "--universal",
        "--python-version",
        PYTHON_MIN,
        "--quiet",
        "--custom-compile-command",
        f"python scripts/compile_requirements.py  # -> {canonical_output}",
        "-o",
        str(output),
    ]
    if upgrade:
        command.append("--upgrade")
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    """Punto de entrada CLI."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verifica que los .txt estén al día (no escribe)")
    mode.add_argument("--upgrade", action="store_true", help="actualiza todas las versiones fijadas")
    args = parser.parse_args()

    if not args.check:
        for source, output in TARGETS:
            compile_file(source, ROOT / output, upgrade=args.upgrade)
            print(f"[OK] {output} generado desde {source}")
        return 0

    # --check: compila en una carpeta temporal partiendo de los .txt actuales y compara.
    stale: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for source, output in TARGETS:
            candidate = Path(tmp) / output
            compile_file(source, candidate, upgrade=False, seed=ROOT / output)
            if not filecmp.cmp(candidate, ROOT / output, shallow=False):
                stale.append(output)
    if stale:
        print(
            f"[ERROR] Desactualizado(s): {', '.join(stale)}. Se editó un .in sin regenerar el lock.\n"
            "  Corré: python scripts/compile_requirements.py  y commiteá el resultado."
        )
        return 1
    print("[OK] Los archivos requirements*.txt corresponden a los .in")
    return 0


if __name__ == "__main__":
    sys.exit(main())
