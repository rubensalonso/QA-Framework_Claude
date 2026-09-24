"""Flujo de compra: revisión del pedido, pago y confirmación."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Download, Locator, Page

from framework.core.step import step
from framework.data.models import PaymentCard
from framework.ui.pages.base_page import BasePage
from framework.utils.parsing import parse_price


@dataclass(frozen=True)
class Address:
    """Dirección tal como se muestra en el checkout."""

    full_name: str
    lines: tuple[str, ...]  # empresa, dirección 1, dirección 2 (en ese orden)
    city_state_zip: str
    country: str
    phone: str


class CheckoutPage(BasePage):
    """Página ``/checkout``: direcciones, detalle del pedido y comentario."""

    PATH = None  # requiere sesión y carrito con productos
    URL_PATTERN = re.compile(r"/checkout$")

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.delivery_address: Locator = page.locator("#address_delivery")
        self.invoice_address: Locator = page.locator("#address_invoice")
        self.order_rows: Locator = page.locator("#cart_info tbody tr[id^='product-']")
        # La última fila de la tabla contiene "Total Amount"; se identifica por texto, no por índice.
        self.total_amount: Locator = (
            page.locator("#cart_info tbody tr").filter(has_text="Total Amount").locator(".cart_total_price")
        )
        self.comment: Locator = page.locator("textarea[name='message']")
        self.place_order_button: Locator = page.get_by_role("link", name="Place Order")

    @property
    def loaded_indicator(self) -> Locator:
        """El bloque de dirección de entrega."""
        return self.delivery_address

    @staticmethod
    def _read_address(block: Locator) -> Address:
        """Parsea un bloque de dirección (``<ul>`` con ``<li>`` de clases semánticas)."""
        return Address(
            full_name=block.locator(".address_firstname").inner_text().strip(),
            lines=tuple(t.strip() for t in block.locator(".address_address1").all_inner_texts()),
            city_state_zip=" ".join(block.locator(".address_city").inner_text().split()),
            country=block.locator(".address_country_name").inner_text().strip(),
            phone=block.locator(".address_phone").inner_text().strip(),
        )

    def delivery(self) -> Address:
        """Dirección de entrega mostrada."""
        return self._read_address(self.delivery_address)

    def invoice(self) -> Address:
        """Dirección de facturación mostrada."""
        return self._read_address(self.invoice_address)

    def total(self) -> int:
        """Importe total del pedido."""
        return parse_price(self.total_amount.inner_text())

    @step("Agregar comentario al pedido y confirmar")
    def place_order(self, comment: str = "") -> PaymentPage:
        """Escribe un comentario opcional y avanza al pago.

        Args:
            comment: Texto libre para el pedido.

        Returns:
            Página de pago verificada.
        """
        if comment:
            self.comment.fill(comment)
        self.place_order_button.click()
        return PaymentPage(self.page).should_be_loaded()


class PaymentPage(BasePage):
    """Página ``/payment``."""

    PATH = None
    URL_PATTERN = re.compile(r"/payment$")

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.name_on_card: Locator = page.locator("[data-qa='name-on-card']")
        self.card_number: Locator = page.locator("[data-qa='card-number']")
        self.cvc: Locator = page.locator("[data-qa='cvc']")
        self.expiry_month: Locator = page.locator("[data-qa='expiry-month']")
        self.expiry_year: Locator = page.locator("[data-qa='expiry-year']")
        self.pay_button: Locator = page.locator("[data-qa='pay-button']")

    @property
    def loaded_indicator(self) -> Locator:
        """El campo de nombre en la tarjeta."""
        return self.name_on_card

    @step("Pagar con tarjeta")
    def pay(self, card: PaymentCard) -> OrderPlacedPage:
        """Completa los datos de la tarjeta y confirma el pago.

        Args:
            card: Tarjeta ficticia (se enmascara en logs).

        Returns:
            Página de confirmación verificada.
        """
        self.name_on_card.fill(card.name_on_card)
        self.card_number.fill(card.number)
        self.cvc.fill(card.cvc)
        self.expiry_month.fill(card.expiry_month)
        self.expiry_year.fill(card.expiry_year)
        self.pay_button.click()
        return OrderPlacedPage(self.page).should_be_loaded()


class OrderPlacedPage(BasePage):
    """Confirmación 'ORDER PLACED!'."""

    PATH = None
    URL_PATTERN = re.compile(r"/payment_done/\d+$")

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.heading: Locator = page.locator("[data-qa='order-placed']")
        self.confirmation: Locator = self.heading.locator("xpath=following-sibling::p[1]")
        self.download_invoice_link: Locator = page.get_by_role("link", name="Download Invoice")
        self.continue_button: Locator = page.locator("[data-qa='continue-button']")

    @property
    def loaded_indicator(self) -> Locator:
        """El encabezado de pedido confirmado."""
        return self.heading

    @step("Descargar factura en {target_dir}")
    def download_invoice(self, target_dir: Path) -> Path:
        """Descarga la factura y la guarda en disco.

        Decisión de diseño: ``expect_download`` registra la espera *antes* del click,
        evitando la condición de carrera de escuchar el evento después de dispararlo.

        Args:
            target_dir: Carpeta destino (usar ``tmp_path`` de pytest para aislar tests).

        Returns:
            Ruta del archivo descargado.
        """
        with self.page.expect_download() as download_info:
            self.download_invoice_link.click()
        download: Download = download_info.value
        # Validar que la descarga terminó sin error antes de guardarla.
        failure = download.failure()
        if failure:
            raise AssertionError(f"La descarga de la factura falló: {failure}")
        target = target_dir / download.suggested_filename
        download.save_as(target)
        self.logger.info("Factura descargada en %s", target)
        return target
