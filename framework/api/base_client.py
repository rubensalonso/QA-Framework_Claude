"""Cliente HTTP base sobre ``APIRequestContext`` de Playwright.

Decisiones de diseño:

* **Playwright en vez de ``requests``**: una sola dependencia para UI y API, mismo manejo
  de timeouts/proxies, y la posibilidad de compartir cookies con el navegador si hiciera falta.
* **Nunca lanzar por status HTTP** (``fail_on_status_code=False``): los tests negativos
  necesitan inspeccionar respuestas 4xx. La aserción la decide el test, no el cliente.
* **Parseo tolerante**: AutomationExercise responde JSON con ``Content-Type: text/html``
  y siempre HTTP 200; el código real viaja en ``responseCode`` dentro del body. El cliente
  expone ambos (``http_status`` y ``response_code``) para que el test elija qué validar.
* **Reintentos solo donde es seguro**: errores de red y 5xx/429 se reintentan con backoff
  exponencial únicamente en métodos idempotentes (GET/PUT/DELETE/HEAD). Un POST reintentado
  podría crear dos cuentas; para habilitarlo hay que pedirlo explícitamente (``retry=True``).
* **Medición de latencia incluida**: cada respuesta trae ``elapsed_ms``, que reutilizan
  las pruebas de performance sin código extra.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Literal, TypeVar

import allure
from playwright.sync_api import APIRequestContext, APIResponse
from playwright.sync_api import Error as PlaywrightError
from pydantic import BaseModel

from framework.core.logger import get_logger, mask_sensitive

HttpMethod = Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"]
ModelT = TypeVar("ModelT", bound=BaseModel)

_IDEMPOTENT_METHODS: frozenset[str] = frozenset({"GET", "PUT", "DELETE", "HEAD"})
_RETRYABLE_STATUS: frozenset[int] = frozenset({429, 500, 502, 503, 504})
_MAX_LOGGED_BODY_CHARS = 500  # evita logs gigantes con listados completos de productos

_logger = get_logger(__name__)


class ApiRequestError(RuntimeError):
    """La petición no obtuvo respuesta tras agotar los reintentos (error de red/timeout)."""


@dataclass(frozen=True)
class ApiResponse:
    """Respuesta normalizada e inmutable, independiente del cliente HTTP subyacente."""

    method: str
    url: str
    http_status: int
    headers: dict[str, str]
    text: str
    elapsed_ms: float
    body: dict[str, Any] = field(default_factory=dict)
    is_json: bool = True

    @property
    def response_code(self) -> int | None:
        """Código de negocio que la API envía dentro del body (``responseCode``)."""
        code = self.body.get("responseCode")
        return int(code) if code is not None else None

    @property
    def message(self) -> str | None:
        """Mensaje de negocio (``message``) si la respuesta lo incluye."""
        msg = self.body.get("message")
        return str(msg) if msg is not None else None

    def as_model(self, model: type[ModelT]) -> ModelT:
        """Valida el body contra un esquema Pydantic (contrato).

        Args:
            model: Clase Pydantic que describe el contrato esperado.

        Returns:
            Instancia validada.

        Raises:
            pydantic.ValidationError: Con el detalle exacto del campo que rompió el contrato.
        """
        return model.model_validate(self.body)


class BaseApiClient:
    """Cliente HTTP genérico con logging, reintentos y adjuntos para Allure."""

    def __init__(
        self,
        request_context: APIRequestContext,
        *,
        timeout_ms: int,
        max_retries: int = 2,
        backoff_s: float = 1.0,
    ) -> None:
        """Inicializa el cliente.

        Args:
            request_context: Contexto de Playwright con ``base_url`` ya configurado.
            timeout_ms: Timeout por intento.
            max_retries: Reintentos adicionales ante fallas transitorias.
            backoff_s: Espera base; se duplica en cada reintento (1s, 2s, 4s...).
        """
        self._ctx = request_context
        self._timeout_ms = timeout_ms
        self._max_retries = max_retries
        self._backoff_s = backoff_s

    def request(
        self,
        method: HttpMethod,
        endpoint: str,
        *,
        params: dict[str, str | int | float | bool] | None = None,
        form: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        retry: bool | None = None,
    ) -> ApiResponse:
        """Ejecuta una petición HTTP y devuelve la respuesta normalizada.

        Args:
            method: Verbo HTTP.
            endpoint: Ruta relativa al ``base_url`` del contexto, **sin** barra inicial
                (``"productsList"``); con barra inicial se resolvería contra la raíz del host.
            params: Query string.
            form: Body ``application/x-www-form-urlencoded``.
            headers: Headers adicionales para esta petición.
            retry: Fuerza/desactiva reintentos. ``None`` = automático según idempotencia.

        Returns:
            :class:`ApiResponse` (incluso para 4xx/5xx; el cliente no lanza por status).

        Raises:
            ApiRequestError: Si no se obtuvo ninguna respuesta tras todos los intentos.
        """
        should_retry = retry if retry is not None else method in _IDEMPOTENT_METHODS
        attempts = 1 + (self._max_retries if should_retry else 0)
        last_error: Exception | None = None

        _logger.info("→ %s %s params=%s form=%s", method, endpoint, params, mask_sensitive(dict(form or {})))
        # Copia con el tipo exacto que declara Playwright (dict es invariante en mypy).
        form_data: dict[str, str | float | bool] | None = dict(form) if form is not None else None

        for attempt in range(1, attempts + 1):
            started = time.perf_counter()
            try:
                raw = self._ctx.fetch(
                    endpoint,
                    method=method,
                    params=params,
                    form=form_data,
                    headers=headers,
                    timeout=self._timeout_ms,
                    fail_on_status_code=False,
                )
            except PlaywrightError as exc:  # red caída, DNS, timeout, conexión reseteada
                last_error = exc
                _logger.warning("Intento %s/%s falló (%s): %s", attempt, attempts, method, exc)
                self._sleep_before_retry(attempt, attempts)
                continue

            elapsed_ms = (time.perf_counter() - started) * 1000
            response = self._build_response(method, raw, elapsed_ms)

            if response.http_status in _RETRYABLE_STATUS and attempt < attempts:
                _logger.warning(
                    "HTTP %s transitorio en %s %s (intento %s/%s), reintentando",
                    response.http_status,
                    method,
                    endpoint,
                    attempt,
                    attempts,
                )
                self._sleep_before_retry(attempt, attempts)
                continue

            self._log_and_attach(response, form)
            return response

        raise ApiRequestError(f"{method} {endpoint} sin respuesta tras {attempts} intentos: {last_error}")

    # ------------------------------------------------------------------ helpers
    def _sleep_before_retry(self, attempt: int, attempts: int) -> None:
        """Backoff exponencial; no duerme después del último intento."""
        if attempt < attempts:
            time.sleep(self._backoff_s * (2 ** (attempt - 1)))

    @staticmethod
    def _build_response(method: str, raw: APIResponse, elapsed_ms: float) -> ApiResponse:
        """Convierte la respuesta de Playwright en :class:`ApiResponse` tolerando JSON inválido."""
        # errors="replace": un byte mal codificado en un nombre de producto no debe tumbar la suite.
        text = raw.body().decode("utf-8", errors="replace")
        body: dict[str, Any] = {}
        is_json = True
        try:
            parsed = json.loads(text) if text else {}
            body = parsed if isinstance(parsed, dict) else {"data": parsed}
        except json.JSONDecodeError:
            # Ej.: página HTML de error de Cloudflare. No se lanza: el test verá is_json=False.
            is_json = False
            _logger.warning("Respuesta no-JSON de %s %s (HTTP %s)", method, raw.url, raw.status)

        return ApiResponse(
            method=method,
            url=raw.url,
            http_status=raw.status,
            headers=dict(raw.headers),
            text=text,
            elapsed_ms=round(elapsed_ms, 2),
            body=body,
            is_json=is_json,
        )

    @staticmethod
    def _log_and_attach(response: ApiResponse, form: dict[str, str] | None) -> None:
        """Registra la respuesta en el log y la adjunta al reporte de Allure."""
        preview = response.text[:_MAX_LOGGED_BODY_CHARS]
        _logger.info(
            "← HTTP %s | responseCode=%s | %.0f ms | %s",
            response.http_status,
            response.response_code,
            response.elapsed_ms,
            preview,
        )
        attachment = {
            "request": {"method": response.method, "url": response.url, "form": mask_sensitive(dict(form or {}))},
            "response": {
                "http_status": response.http_status,
                "elapsed_ms": response.elapsed_ms,
                "body": response.body if response.is_json else preview,
            },
        }
        allure.attach(
            json.dumps(attachment, indent=2, ensure_ascii=False),
            name=f"{response.method} {response.url}",
            attachment_type=allure.attachment_type.JSON,
        )
