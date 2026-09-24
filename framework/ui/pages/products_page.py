"""Catálogo de productos: listado, búsqueda y filtros por categoría/marca."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

from framework.core.step import step
from framework.ui.components.modals import AddedToCartModal
from framework.ui.pages.base_page import BasePage
from framework.utils.parsing import parse_price


class ProductsPage(BasePage):
    """Página ``/products`` y sus variantes filtradas (búsqueda, categoría, marca)."""

    PATH = "/products"
    # También cubre las vistas filtradas, que reutilizan el mismo layout.
    URL_PATTERN = re.compile(r"/(products|category_products/\d+|brand_products/[^/]+)(\?.*)?$")

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.grid: Locator = page.locator(".features_items")
        self.grid_title: Locator = self.grid.locator("h2.title")
        self.product_cards: Locator = self.grid.locator(".product-image-wrapper")
        self.search_input: Locator = page.locator("#search_product")
        self.search_button: Locator = page.locator("#submit_search")
        self.category_panel: Locator = page.locator("#accordian")
        self.brands_panel: Locator = page.locator(".brands_products")
        self.cart_modal = AddedToCartModal(page)

    @property
    def loaded_indicator(self) -> Locator:
        """El título de la grilla de productos."""
        return self.grid_title

    # ------------------------------------------------------------ consultas
    def product_names(self) -> list[str]:
        """Nombres de todos los productos visibles en la grilla."""
        return [n.strip() for n in self.product_cards.locator(".productinfo p").all_inner_texts()]

    def product_prices(self) -> list[int]:
        """Precios de todos los productos visibles, ya parseados a entero."""
        return [parse_price(p) for p in self.product_cards.locator(".productinfo h2").all_inner_texts()]

    def card_by_id(self, product_id: int) -> Locator:
        """Tarjeta de un producto identificada por su id (estable, a diferencia del índice)."""
        return self.product_cards.filter(has=self.page.locator(f"a[href='/product_details/{product_id}']"))

    # ------------------------------------------------------------ acciones
    @step("Buscar '{term}'")
    def search(self, term: str) -> None:
        """Busca productos y espera a que la grilla muestre los resultados.

        Args:
            term: Texto a buscar.
        """
        self.submit_search(term)
        # Esperar el título evita leer la grilla vieja (la de antes de recargar).
        expect(self.grid_title).to_have_text(re.compile("Searched Products", re.IGNORECASE))

    def submit_search(self, term: str) -> None:
        """Envía la búsqueda y espera la navegación, sin asumir que el resultado es una grilla.

        Útil para payloads maliciosos: la respuesta puede ser la grilla o una página de bloqueo
        del WAF, y es el test quien decide qué desenlace es aceptable.

        Args:
            term: Texto a buscar.
        """
        self.search_input.fill(term)
        self.search_button.click()
        # La búsqueda navega a /products?search=...; se espera la URL nueva y su DOM.
        expect(self.page).to_have_url(re.compile(r"[?&]search="))
        self.page.wait_for_load_state("domcontentloaded")

    @step("Agregar producto id={product_id} al carrito")
    def add_to_cart(self, product_id: int, *, continue_shopping: bool = True) -> None:
        """Agrega un producto desde la grilla.

        Args:
            product_id: Id del producto.
            continue_shopping: Si ``True`` cierra el modal; si ``False`` lo deja abierto
                para que el test elija 'View Cart'.
        """
        card = self.card_by_id(product_id)
        card.scroll_into_view_if_needed()
        # Al hacer hover, un overlay animado cubre el botón original. Se reproduce el gesto del
        # usuario (hover + click en el botón del overlay) para no pelear contra la animación.
        card.hover()
        card.locator(".product-overlay .add-to-cart").click()
        self.cart_modal.should_be_visible()
        if continue_shopping:
            self.cart_modal.continue_shopping()

    @step("Ver detalle del producto id={product_id}")
    def view_product(self, product_id: int) -> None:
        """Abre el detalle de un producto.

        Args:
            product_id: Id del producto.
        """
        self.card_by_id(product_id).get_by_role("link", name="View Product").click()

    @step("Filtrar por categoría {parent} > {child}")
    def filter_by_category(self, parent: str, child: str) -> None:
        """Expande una categoría del panel lateral y elige una subcategoría.

        Args:
            parent: Categoría principal (``Women``, ``Men``, ``Kids``).
            child: Subcategoría (``Dress``, ``Tshirts``...).
        """
        self.category_panel.locator(f"a[href='#{parent}']").click()
        sub_panel = self.page.locator(f"#{parent}")
        # El panel se despliega con animación de Bootstrap; esperar visibilidad antes del click.
        expect(sub_panel).to_be_visible()
        sub_panel.get_by_role("link", name=child).click()

    @step("Filtrar por marca '{brand}'")
    def filter_by_brand(self, brand: str) -> None:
        """Filtra el catálogo por marca.

        Args:
            brand: Nombre de la marca tal como figura en el panel (``Polo``, ``H&M``...).
        """
        self.brands_panel.locator(f"a[href='/brand_products/{brand}']").click()
