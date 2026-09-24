"""Unit — Tests del propio framework (sin red ni navegador, corren en milisegundos).

Un framework de automatización también es software: si ``parse_price`` o ``percentile``
tienen un bug, cientos de tests darían resultados falsos. Estos tests lo previenen.
"""

from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from framework.core.logger import MASK, mask_sensitive
from framework.core.step import _render_title
from framework.data import PaymentCardFactory, UserFactory
from framework.data.models import SUPPORTED_COUNTRIES
from framework.performance.stats import percentile, summarize
from framework.ui.browser_setup import AD_DOMAINS_PATTERN, is_bot_challenge
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
