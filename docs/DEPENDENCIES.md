# Gestión de dependencias

## Cómo está organizado

| Archivo | Quién lo edita | Contenido |
|---|---|---|
| `requirements.in` | **Vos, a mano** | Dependencias directas de ejecución, con rangos (`playwright>=1.47,<2`) |
| `requirements-dev.in` | **Vos, a mano** | Herramientas de desarrollo (ruff, mypy, uv, pre-commit) |
| `requirements.txt` | **Generado** — no editar | Lock: TODAS las dependencias (también las transitivas) con versión exacta |
| `requirements-dev.txt` | **Generado** — no editar | Lock de desarrollo, alineado con `requirements.txt` vía `-c` |

**¿Por qué un lock?** Con solo rangos, dos instalaciones en días distintos pueden obtener versiones
diferentes de alguna dependencia transitiva, y un test que pasaba ayer falla hoy sin que nadie haya
cambiado nada. El lock hace que tu máquina, la de tu equipo y el CI instalen exactamente lo mismo.

Para instalar no cambia nada: `pip install -r requirements-dev.txt`.

## Agregar, quitar o cambiar una dependencia

1. Editá el `.in` correspondiente (nunca el `.txt`).
2. Regenerá los locks:
   ```bash
   python scripts/compile_requirements.py
   ```
3. Instalá y probá: `pip install -r requirements-dev.txt && pytest -m unit`.
4. Commiteá **el `.in` y los `.txt` juntos**.

Si te olvidás del paso 2, el CI falla en el paso *"Lockfiles al día con los .in"* con un mensaje que
te dice qué correr.

## Actualizar versiones

```bash
python scripts/compile_requirements.py --upgrade   # todo a la última versión que permitan los rangos
```

Revisá el diff de los `.txt`: es la lista exacta de lo que cambia. Si una versión nueva rompe algo,
acotá el rango en el `.in` (p. ej. `faker>=28,<41`) y regenerá.

## Por qué `uv pip compile --universal` y no `pip-compile`

`pip-compile` (pip-tools) resuelve las dependencias **solo para la plataforma donde se ejecuta**.
Compilado en Windows fijaba `pywin32==312`, un paquete que solo existe para Windows: el CI, que corre
en Linux, no podía instalar el lock. `uv pip compile --universal` resuelve para todas las plataformas
a la vez y agrega marcadores de entorno:

```text
pywin32==312 ; sys_platform == 'win32'
colorama==0.4.6 ; sys_platform == 'win32'
```

El resultado es un `requirements.txt` estándar: lo instala el `pip` de siempre, `uv` solo se usa para generarlo.

## Dependabot

`.github/dependabot.yml` revisa cada lunes las dependencias de Python y las GitHub Actions, y abre PRs:

- Ruff, mypy, pre-commit y uv se agrupan en un único PR; los plugins de pytest, en otro.
- **Playwright va siempre en su propio PR**: cada versión trae navegadores nuevos y es la dependencia
  con más impacto en los tests de UI.
- Cada PR dispara el CI completo. **Solo mergear con el CI en verde.**

Dependabot actualiza las versiones fijadas directamente en los `.txt`. Si un PR suyo hace fallar el
paso *"Lockfiles al día"*, bajá la rama, corré `python scripts/compile_requirements.py`, y pusheá el resultado.

## Pre-commit

Los hooks de `.pre-commit-config.yaml` corren solos antes de cada commit (formato, lint, tipado,
higiene de archivos) y antes de cada push (tests unitarios). Instalación, una vez por clon:

```bash
pre-commit install
```

Usan las herramientas del entorno virtual (las mismas versiones que el CI), así que **activá el venv
antes de commitear**. Para correrlos a mano sobre todo el repo: `pre-commit run --all-files`.
En casos excepcionales se pueden saltear con `git commit --no-verify`, pero el CI corre los mismos
chequeos, así que el problema reaparece en el PR.
