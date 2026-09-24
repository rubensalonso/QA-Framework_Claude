"""Contratos (esquemas) de las respuestas de la API de AutomationExercise.

Decisión de diseño: ``extra="forbid"`` en los modelos de dominio. Si el backend agrega,
renombra o elimina un campo, el test de contrato falla y lo detectamos *antes* de que
rompa a un consumidor. Es intencionalmente estricto: ese es el propósito de un contract test.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class UserType(_StrictModel):
    """Segmento de usuario de una categoría (Women/Men/Kids)."""

    usertype: str


class Category(_StrictModel):
    """Categoría de un producto."""

    usertype: UserType
    category: str


class Product(_StrictModel):
    """Producto del catálogo."""

    id: int = Field(gt=0)
    name: str = Field(min_length=1)
    price: str = Field(pattern=r"^Rs\. \d+$")
    brand: str = Field(min_length=1)
    category: Category


class Brand(_StrictModel):
    """Marca del catálogo."""

    id: int = Field(gt=0)
    brand: str = Field(min_length=1)


class UserDetail(_StrictModel):
    """Detalle de cuenta devuelto por ``getUserDetailByEmail``."""

    id: int
    name: str
    email: str
    title: str
    birth_day: str
    birth_month: str
    birth_year: str
    first_name: str
    last_name: str
    company: str
    address1: str
    address2: str
    country: str
    state: str
    city: str
    zipcode: str


class ProductsResponse(_StrictModel):
    """Respuesta de ``productsList`` y ``searchProduct``."""

    responseCode: int  # noqa: N815 - el nombre lo impone la API
    products: list[Product]


class BrandsResponse(_StrictModel):
    """Respuesta de ``brandsList``."""

    responseCode: int  # noqa: N815
    brands: list[Brand]


class UserDetailResponse(_StrictModel):
    """Respuesta de ``getUserDetailByEmail``."""

    responseCode: int  # noqa: N815
    user: UserDetail


class MessageResponse(_StrictModel):
    """Respuesta genérica ``{responseCode, message}`` (errores y operaciones de escritura)."""

    responseCode: int  # noqa: N815
    message: str
