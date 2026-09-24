"""Factories de datos de prueba basadas en Faker.

Decisiones de diseño:

* **Datos únicos por test**: el email incluye un UUID. Así los tests son independientes
  y pueden correr en paralelo (``pytest -n auto``) sin colisiones en el backend compartido.
* **Dominio ``example.com``**: reservado por RFC 2606, nunca pertenece a una persona real.
  Evita enviar mails a terceros si el sitio llegara a enviar notificaciones.
* **Overrides explícitos**: ``UserFactory.build(country="Canada")`` permite fijar solo lo
  que el test necesita y dejar el resto aleatorio (patrón *Test Data Builder*).
* **Semilla opcional**: con ``QA_FAKER_SEED`` los datos son reproducibles para depurar.
"""

from __future__ import annotations

import dataclasses
import uuid
from typing import Any

from faker import Faker

from framework.config import get_settings
from framework.core.logger import get_logger
from framework.data.models import SUPPORTED_COUNTRIES, PaymentCard, User

_logger = get_logger(__name__)


def _build_faker() -> Faker:
    """Crea la instancia de Faker aplicando la semilla configurada (si existe)."""
    fake = Faker("en_US")
    seed = get_settings().faker_seed
    if seed is not None:
        fake.seed_instance(seed)
        _logger.info("Faker inicializado con semilla fija %s", seed)
    return fake


_fake: Faker = _build_faker()


def unique_email(prefix: str = "qa") -> str:
    """Genera un email único y seguro para pruebas.

    Args:
        prefix: Prefijo legible para identificar el origen del dato en el backend.

    Returns:
        Email del tipo ``qa.3f9a1c2b7d4e@example.com``.
    """
    # El UUID no depende de la semilla de Faker: incluso con datos reproducibles,
    # dos corridas no chocan por email duplicado.
    return f"{prefix}.{uuid.uuid4().hex[:12]}@example.com"


class UserFactory:
    """Construye objetos :class:`User` válidos con datos realistas."""

    @staticmethod
    def build(**overrides: Any) -> User:
        """Crea un usuario válido, sobreescribiendo los campos indicados.

        Args:
            **overrides: Campos de :class:`User` a fijar explícitamente.

        Returns:
            Usuario listo para registrar vía UI o API.

        Raises:
            TypeError: Si algún override no es un campo de :class:`User`.
        """
        first_name = _fake.first_name()
        last_name = _fake.last_name()
        birth = _fake.date_of_birth(minimum_age=18, maximum_age=80)
        user = User(
            name=f"{first_name} {last_name}",
            email=unique_email(),
            # Contraseña fuerte y aleatoria: evita asumir reglas de complejidad que no conocemos.
            password=_fake.password(length=12, special_chars=True, digits=True, upper_case=True),
            title=_fake.random_element(("Mr", "Mrs")),
            birth_day=birth.day,
            birth_month=birth.month,
            birth_year=birth.year,
            first_name=first_name,
            last_name=last_name,
            company=_fake.company(),
            address1=_fake.street_address(),
            address2=_fake.secondary_address(),
            country=_fake.random_element(SUPPORTED_COUNTRIES),
            state=_fake.state(),
            city=_fake.city(),
            zipcode=_fake.postcode(),
            mobile_number=_fake.numerify("##########"),
        )
        # dataclasses.replace valida que los overrides existan (TypeError si hay un typo).
        return dataclasses.replace(user, **overrides) if overrides else user


class PaymentCardFactory:
    """Construye tarjetas de pago ficticias."""

    @staticmethod
    def build(**overrides: Any) -> PaymentCard:
        """Crea una tarjeta con fecha de vencimiento siempre en el futuro.

        Args:
            **overrides: Campos de :class:`PaymentCard` a fijar explícitamente.

        Returns:
            Tarjeta de pago de prueba.
        """
        expiry = _fake.future_date(end_date="+5y")
        card = PaymentCard(
            name_on_card=_fake.name(),
            number=_fake.credit_card_number(card_type="visa16"),
            cvc=_fake.credit_card_security_code(card_type="visa16"),
            expiry_month=f"{expiry.month:02d}",
            expiry_year=str(expiry.year),
        )
        return dataclasses.replace(card, **overrides) if overrides else card
