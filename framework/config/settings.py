"""Configuración centralizada del framework.

Decisión de diseño: una única fuente de verdad tipada (pydantic-settings) en lugar de
constantes dispersas. Orden de precedencia (mayor a menor):

1. Variables de entorno reales (``QA_BASE_URL=...``) -> ideal para CI.
2. Archivo ``.env`` en la raíz del proyecto -> ideal para desarrollo local.
3. Valores por defecto definidos en esta clase.

Pydantic valida tipos al arrancar: un ``QA_DEFAULT_TIMEOUT_MS=abc`` falla de inmediato
con un mensaje claro, en vez de romper un test a mitad de ejecución.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Parámetros de ejecución. Cada atributo se sobreescribe con ``QA_<NOMBRE_EN_MAYÚSCULAS>``."""

    model_config = SettingsConfigDict(
        env_prefix="QA_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # variables QA_ desconocidas no rompen la ejecución
        frozen=True,  # la configuración es inmutable durante la corrida
    )

    # --- Entorno bajo prueba ---
    base_url: str = "https://automationexercise.com"
    # La barra final es obligatoria: Playwright resuelve rutas relativas como URLs (RFC 3986),
    # así que "api" + "productsList" sin barra reemplazaría el último segmento.
    api_base_url: str = "https://automationexercise.com/api/"

    # --- Timeouts (ms) ---
    default_timeout_ms: int = Field(default=15_000, gt=0)
    navigation_timeout_ms: int = Field(default=30_000, gt=0)
    expect_timeout_ms: int = Field(default=10_000, gt=0)
    api_timeout_ms: int = Field(default=20_000, gt=0)

    # --- Resiliencia API ---
    api_max_retries: int = Field(default=2, ge=0, le=5)
    api_retry_backoff_s: float = Field(default=1.0, ge=0)

    # --- Navegador ---
    block_ads: bool = True
    viewport_width: int = 1366
    viewport_height: int = 768
    locale: str = "en-US"

    # --- Datos de prueba ---
    faker_seed: int | None = None

    # --- Logging ---
    log_level: str = "INFO"
    log_dir: Path = PROJECT_ROOT / "logs"

    # --- Presupuestos de performance ---
    # Son deliberadamente holgados: el sitio es público y gratuito, y la latencia desde CI
    # varía mucho. El objetivo es detectar regresiones graves, no micro-optimizar.
    perf_ttfb_ms: int = 2_000
    perf_dom_content_loaded_ms: int = 6_000
    perf_load_ms: int = 12_000
    perf_lcp_ms: int = 6_000
    perf_api_p95_ms: int = 3_000
    perf_api_samples: int = Field(default=5, ge=3, le=20)  # tope para no saturar un sitio público

    @field_validator("base_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        """Normaliza la URL base para que ``base_url + '/login'`` nunca genere ``//login``."""
        return value.rstrip("/")

    @field_validator("api_base_url")
    @classmethod
    def _ensure_trailing_slash(cls, value: str) -> str:
        """Garantiza la barra final que necesita la resolución de rutas relativas."""
        return value if value.endswith("/") else f"{value}/"

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        """Acepta el nivel en cualquier capitalización y rechaza valores inválidos."""
        level = value.upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"QA_LOG_LEVEL inválido: {value!r}")
        return level


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Devuelve la configuración (singleton cacheado).

    Decisión de diseño: ``lru_cache`` evita releer ``.env`` en cada fixture y, a la vez,
    permite limpiar la caché en tests unitarios con ``get_settings.cache_clear()``.
    """
    return Settings()
