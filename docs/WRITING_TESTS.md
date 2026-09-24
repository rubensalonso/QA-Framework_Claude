# Guía para escribir tests

Esta guía te lleva paso a paso por las tareas más comunes. Seguí las convenciones: un framework
es útil en la medida en que todo el equipo lo usa de la misma manera.

## 1. Anatomía de un buen test

```python
@allure.epic("UI")
@allure.feature("Carrito")
class TestCart:
    @pytest.mark.smoke  # 1. markers
    @allure.title("Agregar el mismo producto dos veces acumula la cantidad")  # 2. título legible
    def test_same_product_twice_accumulates_quantity(self, page: Page):  # 3. nombre descriptivo
        # Arrange — preparar el estado
        products_page = ProductsPage(page).open()

        # Act — la acción bajo prueba
        products_page.add_to_cart(1)
        products_page.add_to_cart(1)
        products_page.header.go_to_cart()

        # Assert — verificar el resultado (y solo eso)
        [item] = CartPage(page).should_be_loaded().items()
        assert item.quantity == 2
        assert item.total == item.price * 2
```

Checklist:

- [ ] **Un comportamiento por test.** Si el título necesita "y además...", son dos tests.
- [ ] **Nombre = comportamiento esperado**: `test_<qué>_<resultado>`, no `test_cart_1`.
- [ ] **Sin selectores ni URLs en el test.** Todo pasa por Page Objects o el cliente API.
- [ ] **Sin `time.sleep`.** Usá `expect(...)` que reintenta automáticamente.
- [ ] **Datos únicos** con factories; nunca emails o usuarios fijos compartidos.
- [ ] **Precondiciones por API** (`registered_user`) cuando no son lo que se está probando.
- [ ] **Limpieza garantizada**: si el test crea una cuenta, registrala en `account_cleanup` *antes* de crearla.
- [ ] **Mensajes en los `assert`** cuando el valor por sí solo no explica el fallo.
- [ ] **Markers correctos** (`ui`/`api` + `smoke`/`regression` + `negative`/`security`/`e2e` si aplica).

## 2. `expect` vs `assert`: cuándo usar cada uno

| Situación | Usar | Motivo |
|---|---|---|
| Estado de la UI (visible, texto, URL, valor) | `expect(locator).to_...` | Reintenta hasta el timeout: tolera renderizado asincrónico |
| Datos ya extraídos (listas, números, respuestas API) | `assert` | El dato ya es estático; no hay nada que esperar |

```python
expect(cart.empty_cart_message).to_be_visible()  # ✅ la UI puede tardar en actualizarse
assert item.quantity == 2  # ✅ item ya es un dato en memoria

assert cart.empty_cart_message.is_visible()  # ❌ se evalúa una sola vez → flaky
```

⚠️ **Trampa frecuente:** `expect(x).to_be_hidden()` justo después de un click pasa *instantáneamente*
si la página todavía no respondió. Preferí una aserción positiva que pruebe que la acción ocurrió
(p. ej. esperar el mensaje de error) o verificá que el estado previo se mantiene (el valor del input).

## 3. Agregar un Page Object

1. Crear `framework/ui/pages/wishlist_page.py`:

```python
class WishlistPage(BasePage):
    """Página /wishlist."""

    PATH = "/wishlist"
    URL_PATTERN = re.compile(r"/wishlist$")

    def __init__(self, page: Page) -> None:
        super().__init__(page)  # header y footer ya disponibles
        self.items: Locator = page.locator("[data-qa='wishlist-item']")
        self.clear_button: Locator = page.get_by_role("button", name="Clear")

    @property
    def loaded_indicator(self) -> Locator:
        """Elemento que garantiza que la página cargó."""
        return self.page.get_by_role("heading", name="My Wishlist")

    @step("Vaciar la wishlist")
    def clear(self) -> None:
        """Elimina todos los productos y espera a que la lista quede vacía."""
        self.clear_button.click()
        expect(self.items).to_have_count(0)
```

2. Exportarla en `framework/ui/pages/__init__.py`.

Reglas:

- Locators como atributos en `__init__` (son *lazy*: no buscan nada hasta usarse).
- Métodos con `@step("...")` para acciones de negocio; los títulos pueden usar `{parametro}`.
- Métodos de consulta (`items()`, `info()`) devuelven **dataclasses**, no locators ni dicts.
- Si una acción dispara algo asincrónico (AJAX, animación), el método **espera su efecto**
  antes de retornar (ver `CartPage.remove_product`).

## 4. Agregar un endpoint de API

1. Agregar la ruta en `Endpoints` (sin barra inicial).
2. Agregar el método en `AutomationExerciseApi` con `@step` y docstring.
3. Si la respuesta tiene una forma nueva, crear el esquema en `schemas.py`.
4. Test:

```python
def test_get_orders(self, api: AutomationExerciseApi, registered_user: User):
    response = api.get_orders(registered_user.email)

    orders = response.as_model(OrdersResponse)  # valida el contrato
    assert orders.responseCode == 200
```

Decidí el reintento conscientemente: operaciones que crean datos → `retry=False` (default de POST).

## 5. Tests data-driven

Para pocos casos, `parametrize` inline con `ids` legibles:

```python
@pytest.mark.parametrize("term", ["top", "jean", "dress"])
```

Para muchos casos o casos que mantiene alguien que no programa, un JSON en `test_data/`:

```python
@pytest.mark.parametrize("case", load_json("invalid_logins.json"), ids=lambda c: c["id"])
def test_invalid_credentials(self, api, case): ...
```

Cada caso del JSON debe tener un `id` único y descriptivo: es lo que aparece en el reporte.

## 6. Fixtures disponibles

| Fixture | Scope | Qué da |
|---|---|---|
| `page` | function | Página con contexto aislado, ads bloqueados y timeouts configurados |
| `api` | session | Cliente `AutomationExerciseApi` |
| `settings` | session | Configuración tipada |
| `new_user` | function | `User` con datos únicos, **sin** registrar |
| `registered_user` | function | `User` registrado por API; se elimina al terminar |
| `logged_in_user` | function | `registered_user` + sesión iniciada en `page` (solo UI) |
| `account_cleanup` | function | `account_cleanup(user)` → borra la cuenta al terminar |
| `tmp_path` | function | Carpeta temporal única (pytest), p. ej. para descargas |

## 7. Convenciones de código

- Type hints en todo el código de `framework/` (mypy estricto lo valida).
- Docstrings estilo Google en clases y métodos públicos del framework.
- Comentarios que explican **por qué**, no qué (el código ya dice qué).
- Antes de subir cambios: `ruff check . && ruff format . && mypy framework performance && pytest -m unit`.
