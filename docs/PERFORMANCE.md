# Estrategia de performance

El framework mide performance en **tres niveles complementarios**. Cada uno responde una pregunta distinta:

| Nivel | Pregunta | Herramienta | Cuándo corre |
|---|---|---|---|
| Carga de página (frontend) | ¿La página carga rápido para un usuario nuevo? | Playwright + APIs del navegador | Nightly |
| Latencia de API | ¿Cada endpoint responde dentro del SLA? | Cliente API del framework | Nightly |
| Carga concurrente | ¿El sistema aguanta N usuarios simultáneos? | Locust | Nightly / manual |

## 1. Carga de página — `tests/performance/test_page_load_performance.py`

Se leen las métricas **del propio navegador** (no se cronometra desde Python), por lo que reflejan lo
que percibe el usuario:

| Métrica | Qué significa | Presupuesto por defecto |
|---|---|---|
| TTFB | Tiempo hasta el primer byte del servidor | `QA_PERF_TTFB_MS` = 2000 ms |
| DOMContentLoaded | HTML parseado y scripts síncronos ejecutados | `QA_PERF_DOM_CONTENT_LOADED_MS` = 6000 ms |
| Load | Todos los recursos cargados | `QA_PERF_LOAD_MS` = 12000 ms |
| LCP (Core Web Vital) | Cuándo se pintó el elemento principal | `QA_PERF_LCP_MS` = 6000 ms |
| CLS (Core Web Vital) | Cuánto "salta" el layout | 0.1 (umbral "bueno" de Google) |

- Cada test usa un contexto nuevo → **caché fría** (peor caso realista).
- LCP/CLS solo existen en Chromium; en otros navegadores esos tests se saltean.
- Las métricas se adjuntan como JSON en Allure, así se pueden comparar entre corridas.
- Los presupuestos son holgados a propósito (sitio público, latencia variable desde CI): detectan
  **regresiones graves**, no micro-variaciones. Contra un entorno propio, ajustalos a tus objetivos reales.

```bash
pytest -m "performance and ui"
```

## 2. SLA de API — `tests/performance/test_api_sla.py`

- Una llamada de *warm-up* descartada (DNS + TLS no representan el régimen del servicio).
- `QA_PERF_API_SAMPLES` muestras **secuenciales** (5 por defecto, máximo 20 por diseño).
- Se valida el **p95** contra `QA_PERF_API_P95_MS` (3000 ms), con percentil *nearest-rank*
  (con pocas muestras es más conservador que la interpolación).
- Solo endpoints de lectura.

```bash
pytest -m "performance and api"
```

¿Por qué p95 y no el promedio? Un promedio de 200 ms puede esconder que 1 de cada 20 usuarios espera
5 segundos. El p95 describe la experiencia de "casi todos".

## 3. Carga concurrente — `performance/load/locustfile.py`

Escenario: usuarios que navegan el catálogo por API con pausas humanas de 1–3 s.

| Tarea | Peso |
|---|---|
| `GET productsList` | 3 |
| `POST searchProduct` (término aleatorio) | 2 |
| `GET brandsList` | 1 |

**Criterios de aceptación** (el proceso termina con código ≠ 0 si fallan → el job de CI falla):

| Criterio | Variable | Default |
|---|---|---|
| Tasa de error máxima | `QA_LOAD_MAX_FAIL_RATIO` | 1 % |
| p95 global máximo | `QA_LOAD_P95_MS` | 3000 ms |
| Usuarios máximos permitidos | `QA_LOAD_MAX_USERS` | 5 |

Como la API responde siempre HTTP 200, cada tarea valida el `responseCode` del body: sin eso,
Locust contaría como exitosos los errores reales (y las páginas de bloqueo del WAF).

```bash
# Headless con la config por defecto (3 usuarios, 1 minuto) → reports/load-test-report.html
locust --config performance/load/locust.conf

# Con interfaz web en http://localhost:8089
locust -f performance/load/locustfile.py --host https://automationexercise.com
```

### ⚠️ Límites éticos

AutomationExercise es un servicio gratuito y compartido. Por eso:

- El tope de usuarios está **en el código**: `-u 50` aborta antes de enviar una sola petición.
- Solo operaciones de lectura; nunca se crean datos durante una prueba de carga.
- **Para pruebas de estrés o de capacidad real, apuntá `--host` a un entorno propio** (staging) y
  subí `QA_LOAD_MAX_USERS` ahí. Cargar un sitio ajeno más allá de lo razonable es, en la práctica,
  un ataque de denegación de servicio.
