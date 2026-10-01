"""Unit — Tests del propio framework (sin red ni navegador, corren en milisegundos).

Un framework de automatización también es software: si ``parse_price`` o ``percentile``
tienen un bug, cientos de tests darían resultados falsos. Estos tests lo previenen.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import re

import pytest

from framework.core.logger import MASK, mask_sensitive
from framework.core.reporting import ALLURE_CATEGORIES
from framework.core.step import _render_title
from framework.data import PaymentCardFactory, UserFactory
from framework.data.models import SUPPORTED_COUNTRIES
from framework.performance.stats import percentile, summarize
from framework.ui.browser_setup import AD_DOMAINS_PATTERN, is_bot_challenge, site_unavailability_reason
from framework.ui.session import HttpLoginError, login_via_http
from framework.utils.parsing import parse_price

pytestmark = pytest.mark.unit


class TestParsePrice:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [("Rs. 500", 500), ("Rs.1000", 1000), ("Rs. 1,500", 1500), ("Total: Rs. 42 ", 42)],
    )
    def test_valid_formats(self, text, expected):
        assert parse_price(text) == expected

    @pytest.mark.parametrize("text", ["", "500", "USD 10", "Rs. abc"])
    def test_invalid_formats_raise(self, text):
        # Fallar explícitamente es mejor que devolver 0 y ocultar un bug de la UI.
        with pytest.raises(ValueError, match="No se pudo interpretar"):
            parse_price(text)


class TestPercentile:
    def test_nearest_rank(self):
        values = [100, 200, 300, 400, 500]
        assert percentile(values, 50) == 300
        assert percentile(values, 95) == 500
        assert percentile(values, 100) == 500

    def test_single_value(self):
        assert percentile([42.0], 95) == 42.0

    def test_order_independent(self):
        assert percentile([5, 1, 4, 2, 3], 50) == 3

    @pytest.mark.parametrize(
        ("values", "pct", "error"),
        [([], 50, "No hay muestras"), ([1, 2], 0, "fuera de rango"), ([1, 2], 101, "fuera de rango")],
    )
    def test_invalid_input_raises(self, values, pct, error):
        with pytest.raises(ValueError, match=error):
            percentile(values, pct)

    def test_summary(self):
        summary = summarize([10, 20, 30, 40])
        assert (summary.samples, summary.min_ms, summary.max_ms, summary.mean_ms) == (4, 10, 40, 25)


class TestSensitiveDataMasking:
    def test_masks_sensitive_keys_case_insensitive(self):
        masked = mask_sensitive({"email": "a@b.com", "Password": "secret", "cvc": "123"})
        assert masked == {"email": "a@b.com", "Password": MASK, "cvc": MASK}

    def test_none_passthrough(self):
        assert mask_sensitive(None) is None

    def test_step_title_masks_password_argument(self):
        def login(email: str, password: str) -> None: ...

        title = _render_title("Login {email} / {password}", login, ("qa@example.com", "secret"), {})
        assert title == f"Login qa@example.com / {MASK}"

    def test_step_title_falls_back_on_bad_template(self):
        def action(value: int) -> None: ...

        assert _render_title("Paso {inexistente}", action, (1,), {}) == "Paso {inexistente}"

    def test_repr_does_not_leak_secrets(self):
        user = UserFactory.build(password="SuperSecret!")
        card = PaymentCardFactory.build(number="4111111111111111")
        assert "SuperSecret!" not in repr(user)
        assert "4111111111111111" not in repr(card)
        assert repr(card).endswith("****1111)")


class TestFactories:
    def test_users_are_unique(self):
        emails = {UserFactory.build().email for _ in range(50)}
        assert len(emails) == 50

    def test_user_uses_safe_domain_and_supported_country(self):
        user = UserFactory.build()
        assert user.email.endswith("@example.com")
        assert user.country in SUPPORTED_COUNTRIES

    def test_overrides_are_applied(self):
        user = UserFactory.build(city="Rosario", title="Mrs")
        assert (user.city, user.title) == ("Rosario", "Mrs")

    def test_invalid_override_fails_fast(self):
        with pytest.raises(TypeError):
            UserFactory.build(no_existe="x")

    def test_users_are_immutable(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            UserFactory.build().city = "X"  # type: ignore[misc]

    def test_api_form_uses_api_field_names(self):
        form = UserFactory.build().to_api_form()
        assert {"firstname", "lastname", "birth_date"} <= form.keys()
        assert "first_name" not in form

    def test_card_expiry_is_in_the_future(self):
        card = PaymentCardFactory.build()
        today = dt.date.today()
        assert (int(card.expiry_year), int(card.expiry_month)) >= (today.year, today.month)


class TestBrowserSetup:
    @pytest.mark.parametrize(
        "url",
        [
            "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js",
            "https://googleads.g.doubleclick.net/pagead/ads",
            "https://fundingchoicesmessages.google.com/i/pub",
            "https://www.googletagmanager.com/gtag/js",
        ],
    )
    def test_ad_urls_are_blocked(self, url):
        assert AD_DOMAINS_PATTERN.search(url)

    @pytest.mark.parametrize(
        "url",
        [
            "https://automationexercise.com/products",
            "https://automationexercise.com/static/js/main.js",
            "https://code.jquery.com/jquery.min.js",
            "https://example.com/doubleclick.net.html",  # el dominio aparece en el path, no en el host
        ],
    )
    def test_site_urls_are_not_blocked(self, url):
        assert not AD_DOMAINS_PATTERN.search(url)

    @pytest.mark.parametrize("title", ["One moment, please...", "Just a moment...", "Un momento…", "403 Forbidden"])
    def test_detects_bot_challenge(self, title):
        assert is_bot_challenge(title)

    def test_real_title_is_not_a_challenge(self):
        assert not is_bot_challenge("Automation Exercise - Signup / Login")


class _FakePage:
    """Doble de prueba mínimo de ``Page``: solo lo que usa ``site_unavailability_reason``."""

    def __init__(self, title: str, body: str) -> None:
        self._title, self._body = title, body

    def title(self) -> str:
        return self._title

    def evaluate(self, _script: str) -> str:
        return self._body


class TestSiteUnavailabilityDiagnosis:
    @pytest.mark.parametrize(
        ("title", "body", "expected"),
        [
            pytest.param("403 Forbidden", "", "WAF", id="waf-block"),
            pytest.param(
                "Automation Exercise",
                "This website is under heavy load (queue full). We're sorry, too many people...",
                "sobrecargado",
                id="hosting-overload",
            ),
            pytest.param("", "   ", "página vacía", id="empty-403-page"),
        ],
    )
    def test_detects_environment_failures(self, title, body, expected):
        reason = site_unavailability_reason(_FakePage(title, body))  # type: ignore[arg-type]
        assert reason is not None
        assert expected in reason

    def test_real_page_has_no_diagnosis(self):
        page = _FakePage("Automation Exercise", "Full-Fledged practice website for Automation Engineers")
        assert site_unavailability_reason(page) is None  # type: ignore[arg-type]


class _FakeResponse:
    def __init__(self, text: str, status: int = 200, url: str = "https://example.test/") -> None:
        self._text, self.status, self.url = text, status, url

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 400

    def text(self) -> str:
        return self._text


class _FakeRequest:
    """Doble de ``APIRequestContext``: registra las llamadas y devuelve respuestas predefinidas."""

    def __init__(self, login_page: str, post_response: _FakeResponse) -> None:
        self._login_page, self._post_response = login_page, post_response
        self.posted: dict[str, object] = {}

    def get(self, _url: str) -> _FakeResponse:
        return _FakeResponse(self._login_page)

    def post(self, url: str, form: dict[str, str], headers: dict[str, str]) -> _FakeResponse:
        self.posted = {"url": url, "form": form, "headers": headers}
        return self._post_response


class _FakeContext:
    def __init__(self, request: _FakeRequest) -> None:
        self.request = request


_LOGIN_HTML = """
<form action="/search" method="GET"><input name="csrfmiddlewaretoken" value="OTRO-FORM"></form>
<div class="login-form"><form action="/login" method="POST">
  <input type="hidden" name="csrfmiddlewaretoken" value="TOKEN-123">
  <input data-qa="login-email" name="email"></form></div>
"""


class TestLoginViaHttp:
    def test_sends_login_form_token_and_referer(self):
        request = _FakeRequest(_LOGIN_HTML, _FakeResponse("<a>Logged in as <b>QA</b></a>"))

        login_via_http(_FakeContext(request), "https://site.test", "qa@example.com", "secret")  # type: ignore[arg-type]

        # Debe usar el token del formulario de LOGIN, no el de otro formulario de la página.
        assert request.posted["form"] == {
            "csrfmiddlewaretoken": "TOKEN-123",
            "email": "qa@example.com",
            "password": "secret",
        }
        assert request.posted["headers"] == {"Referer": "https://site.test/login"}

    def test_missing_csrf_token_fails_clearly(self):
        request = _FakeRequest("<html>sin formulario</html>", _FakeResponse(""))

        with pytest.raises(HttpLoginError, match="token CSRF"):
            login_via_http(_FakeContext(request), "https://site.test", "qa@example.com", "x")  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "response",
        [
            pytest.param(_FakeResponse("Your email or password is incorrect!"), id="credenciales-invalidas"),
            pytest.param(_FakeResponse("Forbidden (CSRF)", status=403), id="csrf-rechazado"),
        ],
    )
    def test_failed_login_raises(self, response):
        request = _FakeRequest(_LOGIN_HTML, response)

        with pytest.raises(HttpLoginError, match="no inició sesión"):
            login_via_http(_FakeContext(request), "https://site.test", "qa@example.com", "x")  # type: ignore[arg-type]


def _allure_category(status: str, message: str, trace: str) -> str:
    """Replica la selección de Allure: la PRIMERA categoría que coincide (matches() de Java = fullmatch)."""
    for category in ALLURE_CATEGORIES:
        if status not in category["matchedStatuses"]:
            continue
        if "messageRegex" in category and not re.fullmatch(category["messageRegex"], message):
            continue
        if "traceRegex" in category and not re.fullmatch(category["traceRegex"], trace):
            continue
        return str(category["name"])
    return "sin categoría"


class TestAllureCategories:
    @pytest.mark.parametrize(
        ("status", "message", "trace", "expected"),
        [
            pytest.param(
                "failed",
                "Locator expected to be visible",
                "Traceback...\nframework.ui.browser_setup.SiteUnavailableError: HTTP 403\n",
                "Fallo de entorno",
                id="entorno-gana-a-timeout",
            ),
            pytest.param(
                "failed",
                "assert ...",
                "E   pydantic_core._pydantic_core.ValidationError: 1 validation error",
                "Contrato de API",
                id="contrato",
            ),
            pytest.param("failed", "home: violaciones graves nuevas:\n - x", "", "Accesibilidad", id="a11y"),
            pytest.param(
                "failed", "Locator expected to have text 'X'\nActual value: None", "", "Timeout de UI", id="timeout"
            ),
            pytest.param("failed", "assert 3 == 2", "", "Fallo de producto", id="producto"),
            pytest.param("broken", "KeyError: 'x'", "Traceback ... KeyError", "Error del test", id="error-test"),
        ],
    )
    def test_failures_land_in_the_right_category(self, status, message, trace, expected):
        assert _allure_category(status, message, trace).startswith(expected)
