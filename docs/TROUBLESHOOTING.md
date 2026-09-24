# Solución de problemas

## Diagnóstico general

Ante cualquier fallo de UI, en este orden:

1. **Leé el mensaje del assert** en consola o en `reports/report.html`.
2. **Mirá el screenshot** embebido en el reporte (se captura automáticamente en cada fallo).
3. **Abrí el trace**: `playwright show-trace test-results/<carpeta-del-test>/trace.zip`.
   Muestra cada acción con el DOM antes/después, la red y la consola del navegador.
4. **Revisá el log**: `logs/test_run_<worker>.log` tiene cada paso (`STEP ▶`) y cada request/response.
5. **Reproducí en modo visible**: `pytest <test> --headed --slowmo 500` o con `PWDEBUG=1`.

## Problemas frecuentes

### `SiteUnavailableError: ... verificación anti-bot` o "403 Forbidden"

El WAF del sitio (Cloudflare / Imunify360) bloqueó tu IP por exceso de tráfico. Afecta también a tu
navegador normal, no es un problema del framework.

- Esperá (en la práctica, el bloqueo observado duró más de 2 horas).
- Reducí el paralelismo: `-n 2` o sin `-n`.
- Evitá correr `-m security` seguido: el WAF (Imunify360) banea IPs que envían payloads de
  ataque repetidos. Para la regresión diaria usá `-m "regression and not security"`.
- Probá desde otra red.
- **No** intentes evadirlo (user agents falsos, plugins "stealth", etc.): es un sitio ajeno y compartido.

### `Timeout ... waiting for locator(...)` / `element(s) not found`

- ¿La página correcta cargó? Mirá el screenshot: puede haber un error del sitio o un overlay.
- ¿Cambió el HTML del sitio? Abrí la página, inspeccioná el elemento y actualizá **solo** el Page Object.
- ¿Es intermitente? Revisá el trace: casi siempre es un elemento animándose o un contenido que
  llega por AJAX. Agregá en el Page Object la espera de la condición que falta (`expect(...)`), nunca un `sleep`.

### `... intercepts pointer events`

Otro elemento cubre el que querés clickear (modal, backdrop, overlay de hover). Esperá a que
desaparezca (`expect(modal).to_be_hidden()`) o interactuá con el elemento que el usuario realmente ve
(ver `ProductsPage.add_to_cart`, que hace hover y clickea el botón del overlay).

### `pydantic.ValidationError` en un test de API

El contrato cambió: el mensaje indica el campo exacto (`products.0.price: String should match pattern`).
Confirmá si es un bug del backend o un cambio intencional; en el segundo caso, actualizá `schemas.py`.

### `ApiRequestError: ... sin respuesta tras N intentos`

No hubo respuesta HTTP (red, DNS, timeout). Verificá conectividad y `QA_API_BASE_URL`.

### Los tests pasan localmente y fallan en CI

- Viewport y locale están fijados en `browser_context_args`; si el test depende de otra resolución, parametrizalo.
- CI corre headless: probá localmente sin `--headed`.
- Latencia mayor desde CI: revisá que no haya aserciones con tiempos implícitos.
- Descargá los artefactos del job (`reports/`, `test-results/`, `logs/`).

### `PytestUnknownMarkWarning` / error por marker

`--strict-markers` está activado: registrá el marker nuevo en `pyproject.toml` (`[tool.pytest.ini_options].markers`).

### Allure no abre / `allure: command not found`

Allure CLI requiere Java 8+: `npm install -g allure-commandline` y luego `allure serve reports/allure-results`.
Alternativa sin instalar nada: `reports/report.html`.

### Quiero datos reproducibles para depurar

`QA_FAKER_SEED=123 pytest <test>` genera siempre los mismos nombres/direcciones (los emails siguen
siendo únicos para evitar colisiones con cuentas de otras corridas).
