"""Modelos de datos de prueba (entradas que el test envía al sistema).

Decisión de diseño: ``dataclass(frozen=True)`` en vez de diccionarios.
* Autocompletado y chequeo de tipos en el IDE.
* Inmutables: un test no puede "ensuciar" datos compartidos por accidente;
  para variar un campo se usa ``dataclasses.replace(user, city="X")``.

Los modelos de *respuesta* de la API (lo que el sistema devuelve) viven en
``framework/api/schemas.py`` y usan Pydantic, porque ahí sí necesitamos validación estricta.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Title = Literal["Mr", "Mrs"]

# Países que ofrece el <select> de registro. Si la UI cambia, falla un único lugar.
SUPPORTED_COUNTRIES: tuple[str, ...] = (
    "India",
    "United States",
    "Canada",
    "Australia",
    "Israel",
    "New Zealand",
    "Singapore",
)


@dataclass(frozen=True)
class User:
    """Cuenta de usuario tal como se registra en AutomationExercise."""

    name: str
    email: str
    password: str
    title: Title
    birth_day: int
    birth_month: int
    birth_year: int
    first_name: str
    last_name: str
    company: str
    address1: str
    address2: str
    country: str
    state: str
    city: str
    zipcode: str
    mobile_number: str

    @property
    def full_name(self) -> str:
        """Nombre completo como lo muestra la página de checkout (``Mr. Ana Pérez``)."""
        return f"{self.title}. {self.first_name} {self.last_name}"

    def to_api_form(self) -> dict[str, str]:
        """Serializa al formato ``form-data`` que espera ``POST /api/createAccount``.

        Nota: la API usa nombres distintos a la UI (``firstname`` vs ``first_name``,
        ``birth_date`` vs ``birth_day``). Este mapeo existe solo aquí.
        """
        return {
            "name": self.name,
            "email": self.email,
            "password": self.password,
            "title": self.title,
            "birth_date": str(self.birth_day),
            "birth_month": str(self.birth_month),
            "birth_year": str(self.birth_year),
            "firstname": self.first_name,
            "lastname": self.last_name,
            "company": self.company,
            "address1": self.address1,
            "address2": self.address2,
            "country": self.country,
            "zipcode": self.zipcode,
            "state": self.state,
            "city": self.city,
            "mobile_number": self.mobile_number,
        }

    def __repr__(self) -> str:
        # Evita que la contraseña aparezca en logs/reportes si alguien loguea el objeto entero.
        return f"User(email={self.email!r}, name={self.name!r})"


@dataclass(frozen=True)
class PaymentCard:
    """Tarjeta de pago (datos ficticios: el sitio no procesa pagos reales)."""

    name_on_card: str
    number: str
    cvc: str
    expiry_month: str
    expiry_year: str

    def __repr__(self) -> str:
        return f"PaymentCard(name_on_card={self.name_on_card!r}, number=****{self.number[-4:]})"
