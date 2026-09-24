# QA Automation Framework — AutomationExercise

[![tests](https://github.com/rubensalonso/QA-Framework_Claude/actions/workflows/tests.yml/badge.svg)](https://github.com/rubensalonso/QA-Framework_Claude/actions/workflows/tests.yml)

Framework de automatización **UI + API + Performance** construido con **Python, Pytest y Playwright**,
usando como sistema bajo prueba (SUT) el sitio público de práctica
[automationexercise.com](https://automationexercise.com).

> Está pensado como una **plantilla de referencia lista para producción**: cada decisión de diseño está
> explicada en comentarios dentro del código y en [`docs/`](docs/). Si tenés un nivel intermedio en
> automatización, deberías poder entenderlo, ejecutarlo y extenderlo sin ayuda.

---

## Índice

1. [¿Por qué AutomationExercise?](#por-qué-automationexercise)
2. [Qué incluye](#qué-incluye)
3. [Stack tecnológico](#stack-tecnológico)
4. [Estructura del proyecto](#estructura-del-proyecto)
5. [Instalación](#instalación)
6. [Cómo ejecutar los tests](#cómo-ejecutar-los-tests)
7. [Reportes y evidencias](#reportes-y-evidencias)
8. [Configuración](#configuración)
9. [Integración continua](#integración-continua)
10. [Uso responsable del sitio público](#uso-responsable-del-sitio-público)
11. [Documentación adicional](#documentación-adicional)

---

## ¿Por qué AutomationExercise?

Se evaluaron varios sitios de práctica (SauceDemo, the-internet, DemoQA, Restful-Booker...).
AutomationExercise ganó porque **un solo sitio cubre las tres capas** que un framework real necesita:

| Necesidad | Qué ofrece AutomationExercise |
|---|---|
| Flujos E2E de negocio | Registro, login, catálogo, carrito, checkout, pago, descarga de factura |
| API pública documentada | 14 endpoints ([api_list](https://automationexercise.com/api_list)): CRUD de cuentas, búsqueda, catálogo |
| Casos borde reales | Diálogos JS, upload de archivos, descargas, modales animados, publicidad intrusiva, WAF anti-bot |
| Datos consistentes UI ↔ API | Permite tests *híbridos*: la API como oráculo de lo que muestra la UI |
| Catálogo de casos de prueba | 26 [test cases oficiales](https://automationexercise.com/test_cases) para trazabilidad |

**Particularidades del SUT que el framework resuelve** (y que vas a encontrar en sistemas reales):

- La API responde **siempre HTTP 200** con `Content-Type: text/html`; el código real viaja en el body (`responseCode`).
- **Publicidad de Google** (vignette ads) que intercepta clicks → se bloquea a nivel de red.
- **WAF (Cloudflare/Imunify360)** que bloquea ráfagas de tráfico → se detecta y reporta con un mensaje claro.
- Overlays con animaciones (modal de carrito, hover sobre productos) → se esperan condiciones, nunca `sleep`.

---

## Qué incluye

| Suite | Cantidad* | Qué valida |
|---|---|---|
| `tests/unit` | 43 | El propio framework: parseo, percentiles, enmascarado de secretos, factories, diagnóstico de entorno |
| `tests/api` | 50 | Contratos (Pydantic), códigos de negocio, CRUD de cuentas, métodos no soportados, inyección |
| `tests/ui` | 65 | Registro, login, catálogo, búsqueda, filtros, carrito, checkout, pago, factura, contacto, navegación |
| `tests/performance` | 14 | Navigation Timing, Core Web Vitals (LCP/CLS), SLA de latencia p95 de API |
| `performance/load` | — | Prueba de carga con Locust (con topes de seguridad incorporados) |

\* Contando cada combinación parametrizada como un test (`pytest --collect-only -q`).

**Casos borde cubiertos** (resumen, detalle en [`docs/TEST_CATALOG.md`](docs/TEST_CATALOG.md)):

- Validación HTML5 del navegador (campos vacíos, emails mal formados) verificando que **no** hubo submit.
- Payloads de SQL injection / XSS / path traversal / template injection / Unicode / strings largos.
- Diálogos JavaScript aceptados **y** cancelados; upload de archivos; descarga y lectura de la factura.
- Valores límite de cantidad, mismo producto agregado dos veces, borrado parcial y total del carrito.
- Persistencia del carrito de invitado tras login y tras registrarse en medio del checkout.
- Email duplicado, campos obligatorios faltantes, borrado con contraseña incorrecta, Unicode round-trip.
- Consistencia entre endpoints y entre UI y API.

---

## Stack tecnológico

| Herramienta | Uso | Por qué |
|---|---|---|
| [Playwright](https://playwright.dev/python/) | Navegador + cliente HTTP | Auto-waiting, tracing, multi-navegador, una sola dependencia para UI y API |
| [Pytest](https://docs.pytest.org/) + pytest-playwright | Runner y fixtures | Estándar de la industria en Python |
| pytest-xdist | Paralelismo | `-n 2` reduce el tiempo total |
| pytest-rerunfailures | Reintentos (solo CI) | Mitiga flakiness de red sin ocultarla (queda registrada) |
| Pydantic / pydantic-settings | Contratos de API y configuración | Validación estricta con mensajes claros |
| Faker | Datos de prueba | Datos realistas y únicos por test |
| Allure + pytest-html | Reportes | Allure: rico en pasos y adjuntos. HTML: autocontenido, sin instalar nada |
| Locust | Carga | Escenarios en Python, criterios de aceptación aptos para CI |
| Ruff + Mypy (strict) | Calidad de código | El framework también es software |

---

## Estructura del proyecto

```
QA-Framework_Claude/
├── framework/                    # Código reutilizable (NO contiene tests)
│   ├── config/settings.py        # Configuración tipada (QA_* / .env)
│   ├── core/
│   │   ├── logger.py             # Logging por worker + enmascarado de secretos
│   │   └── step.py               # @step → log + paso de Allure en un solo decorador
│   ├── api/
│   │   ├── base_client.py        # HTTP: reintentos, parseo tolerante, latencia, adjuntos
│   │   ├── automation_exercise_api.py  # Un método por endpoint, con nombres de negocio
│   │   └── schemas.py            # Contratos Pydantic de las respuestas
│   ├── ui/
│   │   ├── browser_setup.py      # Bloqueo de ads, overlays, detección de WAF
│   │   ├── components/           # Header, footer de suscripción, modales
│   │   └── pages/                # Page Objects (uno por pantalla)
│   ├── data/                     # Modelos de datos, factories (Faker), loader de JSON
│   ├── performance/              # Web vitals y estadística de latencias
│   └── utils/                    # Helpers puros (parseo de precios)
├── tests/
│   ├── conftest.py               # Fixtures globales, hooks de evidencias
│   ├── unit/                     # Tests del framework
│   ├── api/                      # Tests de API
│   ├── ui/                       # Tests de UI
│   └── performance/              # Web vitals + SLA de API
├── performance/load/             # Locust (carga)
├── test_data/                    # Datos estáticos para tests data-driven
├── docs/                         # Documentación ampliada
├── .github/workflows/tests.yml   # Pipeline de CI
├── pyproject.toml                # Config de pytest, ruff y mypy
├── requirements.txt              # Dependencias de ejecución
└── requirements-dev.txt          # + herramientas de calidad
```

---

## Instalación

**Requisitos:** Python 3.11 o superior, Git. (Java 11+ solo si querés ver reportes Allure localmente).

### Windows (PowerShell)

```powershell
git clone https://github.com/rubensalonso/QA-Framework_Claude.git
cd QA-Framework_Claude
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
playwright install chromium firefox
copy .env.example .env      # opcional: solo si querés cambiar valores por defecto
```

### Linux / macOS

```bash
git clone https://github.com/rubensalonso/QA-Framework_Claude.git
cd QA-Framework_Claude
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
playwright install --with-deps chromium firefox
cp .env.example .env
```

Verificá la instalación (no usa red, tarda menos de un segundo):

```bash
pytest -m unit
```

---

## Cómo ejecutar los tests

Todos los comandos se ejecutan desde la raíz del proyecto con el entorno virtual activo.

### Por suite o por marker

```bash
pytest -m smoke                       # subconjunto crítico (~2 min)
pytest -m api                         # solo API (sin navegador, segundos)
pytest -m ui                          # solo UI
pytest -m "ui and not e2e"            # combinaciones lógicas
pytest -m negative                    # solo casos negativos / borde
pytest -m performance                 # web vitals + SLA de API
pytest tests/ui/test_cart.py          # un archivo
pytest -k "checkout and invoice"      # por nombre
```

Markers disponibles: `unit`, `smoke`, `regression`, `ui`, `api`, `e2e`, `performance`, `negative`, `security`
(definidos en `pyproject.toml`; un marker mal escrito hace fallar la ejecución a propósito).

### Navegadores, modo visible y depuración

```bash
pytest -m smoke --browser firefox                     # otro navegador
pytest -m smoke --browser chromium --browser firefox  # varios
pytest tests/ui/test_cart.py --headed --slowmo 500    # ver el navegador, en cámara lenta
PWDEBUG=1 pytest tests/ui/test_cart.py -k persists    # Playwright Inspector (paso a paso)
pytest -m ui -o log_cli=true                          # logs en vivo en la consola
```

> En PowerShell, las variables de entorno se definen así: `$env:PWDEBUG=1; pytest ...`

### En paralelo

```bash
pytest -m regression -n 2
```

⚠️ Usá **como máximo `-n 2`** contra el sitio público: más paralelismo dispara el WAF y bloquea tu IP
temporalmente (ver [Uso responsable](#uso-responsable-del-sitio-público)).

### Prueba de carga

```bash
locust --config performance/load/locust.conf          # headless, 3 usuarios, 1 minuto
```

Ver [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) para escenarios, criterios de aceptación y límites.

---

## Reportes y evidencias

Cada ejecución genera, sin configuración adicional:

| Artefacto | Ubicación | Cómo verlo |
|---|---|---|
| Reporte HTML autocontenido | `reports/report.html` | Abrir en el navegador |
| Resultados Allure | `reports/allure-results/` | `allure serve reports/allure-results` |
| Screenshot del fallo | Embebido en ambos reportes | — |
| Trace de Playwright (solo fallos) | `test-results/<test>/trace.zip` | `playwright show-trace <ruta>` |
| Log por worker | `logs/test_run_<worker>.log` | Cualquier editor |

El **trace** es la herramienta de diagnóstico más potente: muestra cada acción, el DOM antes/después,
la red y la consola, como una grabación navegable del test que falló.

Para Allure localmente: `npm install -g allure-commandline` (requiere Java) y luego
`allure serve reports/allure-results`.

---

## Configuración

Toda la configuración vive en [`framework/config/settings.py`](framework/config/settings.py) y se
sobreescribe con variables de entorno con prefijo `QA_` o con un archivo `.env`
(ver [`.env.example`](.env.example)). Prioridad: **variable de entorno > `.env` > valor por defecto**.

| Variable | Default | Descripción |
|---|---|---|
| `QA_BASE_URL` | `https://automationexercise.com` | URL del sitio (también `--base-url` por CLI) |
| `QA_API_BASE_URL` | `https://automationexercise.com/api/` | URL base de la API |
| `QA_DEFAULT_TIMEOUT_MS` | `15000` | Timeout de acciones (click, fill...) |
| `QA_EXPECT_TIMEOUT_MS` | `10000` | Timeout de aserciones `expect` |
| `QA_API_MAX_RETRIES` | `2` | Reintentos ante errores transitorios (solo métodos idempotentes) |
| `QA_BLOCK_ADS` | `true` | Bloquear publicidad de terceros |
| `QA_FAKER_SEED` | — | Semilla para datos reproducibles |
| `QA_LOG_LEVEL` | `INFO` | Nivel de log |
| `QA_PERF_*` | ver `.env.example` | Presupuestos de performance |

Los valores se validan al arrancar: `QA_DEFAULT_TIMEOUT_MS=abc` falla de inmediato con un mensaje claro.

---

## Integración continua

[`.github/workflows/tests.yml`](.github/workflows/tests.yml) define:

| Evento | Qué corre |
|---|---|
| Pull request | Lint + mypy + unit → API → UI smoke (Chromium) |
| Push a `main` | Todo lo anterior + UI regresión en Chromium y Firefox |
| Nightly (L-V) | Regresión completa + performance + carga |
| Manual | Marker y navegador a elección |

Todos los jobs publican reportes, traces y logs como artefactos, y un job final unifica los resultados
en un único reporte Allure.

---

## Uso responsable del sitio público

AutomationExercise es gratuito y compartido por miles de personas que aprenden. El framework
incorpora límites **en el código**, no solo en la documentación:

- Paralelismo recomendado `-n 2` (el CI usa 2).
- Las pruebas de performance de API son **secuenciales** y con máximo 20 muestras.
- Locust aborta antes de enviar peticiones si se piden más de `QA_LOAD_MAX_USERS` (5) usuarios.
- Solo se usan endpoints de lectura para medir performance.
- Los tests `security` (payloads de inyección/XSS) **no** corren en el CI automático: el WAF del
  hosting banea por horas las IPs que envían payloads de ataque repetidos. Se ejecutan a demanda
  (`pytest -m security`), idealmente contra un entorno propio.
- Todas las cuentas creadas se eliminan al terminar cada test, aunque el test falle.
- Emails siempre en `@example.com` (dominio reservado, nunca de una persona real).

Si el WAF bloquea tu IP, el framework lo detecta y lo informa con un mensaje explícito
(`SiteUnavailableError`). **No intenta evadir la protección**: esperá, reducí el paralelismo o cambiá
de red. Ver [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

---

## Documentación adicional

| Documento | Contenido |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Capas, flujo de una ejecución, decisiones de diseño y sus alternativas |
| [`docs/WRITING_TESTS.md`](docs/WRITING_TESTS.md) | Guía paso a paso para agregar páginas, endpoints y tests + convenciones |
| [`docs/TEST_CATALOG.md`](docs/TEST_CATALOG.md) | Catálogo de casos de prueba y trazabilidad con los test cases del sitio |
| [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) | Estrategia de performance: web vitals, SLA de API y carga |
| [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) | Problemas frecuentes y cómo diagnosticarlos |
