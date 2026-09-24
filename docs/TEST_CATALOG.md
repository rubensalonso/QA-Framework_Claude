# Catálogo de casos de prueba

**168 tests** en total (cada combinación parametrizada cuenta como uno): 40 unit · 50 API · 64 UI · 14 performance.
Regenerar el listado: `pytest --collect-only -q`.

Leyenda de tipo: ✅ positivo · ❌ negativo / borde · 🔒 seguridad · 🔁 E2E

## Trazabilidad con los test cases oficiales

AutomationExercise publica [26 test cases](https://automationexercise.com/test_cases). Cobertura:

| TC oficial | Descripción | Test del framework |
|---|---|---|
| TC1 | Register User | `test_register_and_delete_user` |
| TC2 | Login con credenciales válidas | `test_login_with_valid_credentials` |
| TC3 | Login con credenciales inválidas | `test_login_with_wrong_password`, `test_login_with_invalid_credentials` |
| TC4 | Logout | `test_logout` |
| TC5 | Registro con email existente | `test_signup_with_existing_email` |
| TC6 | Contact Us | `test_submit_contact_form_with_attachment` |
| TC7 | Página Test Cases | `test_main_menu_navigation[test_cases_link]` |
| TC8 | Productos y detalle | `test_product_list_and_detail` |
| TC9 | Buscar producto | `test_search_shows_related_products` |
| TC10 | Suscripción en home | `test_subscribe_from_footer[home]` |
| TC11 | Suscripción en carrito | `test_subscribe_from_footer[cart]` |
| TC12 | Agregar productos al carrito | `test_add_multiple_products` |
| TC13 | Cantidad en el carrito | `test_product_quantity_from_detail` |
| TC14 | Registrarse durante el checkout | `test_register_during_checkout` |
| TC15 | Registrarse antes del checkout | cubierto por `logged_in_user` + `test_place_order_and_download_invoice` |
| TC16 | Login antes del checkout | `test_place_order_and_download_invoice` |
| TC17 | Quitar productos del carrito | `test_remove_product_empties_cart`, `test_remove_one_of_many` |
| TC18 | Categorías | `test_filter_by_category` |
| TC19 | Marcas | `test_filter_by_brand` |
| TC20 | Buscar y verificar carrito tras login | `test_cart_persists_after_login` |
| TC21 | Review de producto | `test_write_review` |
| TC22 | Recommended items | `test_add_from_recommended_items` |
| TC23 | Direcciones en el checkout | `test_place_order_and_download_invoice` (paso "Verificar direcciones") |
| TC24 | Descargar factura | `test_place_order_and_download_invoice` |
| TC25 | Scroll up con flecha | `test_scroll_up_with_arrow` |
| TC26 | Scroll up sin flecha | `test_scroll_up_without_arrow` |

APIs oficiales 1–14: todas cubiertas en `tests/api/` (ver secciones siguientes).

## API — `tests/api/`

### Catálogo (`test_catalog_api.py`)

| Test | Tipo | Valida |
|---|---|---|
| `test_get_products_returns_catalog` | ✅ | API 1: 200 + contrato Pydantic estricto |
| `test_product_ids_are_unique` | ✅ | Integridad: sin ids duplicados |
| `test_products_belong_to_known_segments` | ✅ | Integridad: segmentos Women/Men/Kids |
| `test_products_rejects_unsupported_methods` ×3 | ❌ | API 2: POST/PUT/DELETE → 405 |
| `test_get_brands_returns_list` | ✅ | API 3: 200 + contrato |
| `test_brands_are_consistent_with_products` | ✅ | Consistencia entre endpoints |
| `test_brands_rejects_unsupported_methods` ×3 | ❌ | API 4: POST/PUT/DELETE → 405 |
| `test_search_returns_relevant_products` ×4 | ✅ | API 5: resultados relevantes |
| `test_search_is_case_insensitive` | ✅ | `top` == `TOP` |
| `test_search_without_matches_returns_empty_list` | ❌ | Lista vacía, no error |
| `test_search_with_empty_term_returns_full_catalog` | ❌ | Término vacío (documenta comportamiento) |
| `test_search_without_parameter_returns_400` | ❌ | API 6: parámetro faltante → 400 |
| `test_search_handles_malicious_payloads` ×9 | 🔒 | SQLi, XSS, path traversal, SSTI, Unicode, string largo |

### Cuentas y autenticación (`test_accounts_api.py`)

| Test | Tipo | Valida |
|---|---|---|
| `test_valid_credentials` | ✅ | API 7: login válido |
| `test_wrong_password` | ❌ | Contraseña incorrecta → 404 |
| `test_email_is_case_sensitive` | ❌ | El email no se normaliza (documenta comportamiento) |
| `test_invalid_credentials` ×4 | ❌🔒 | API 10: data-driven desde `test_data/invalid_logins.json` |
| `test_missing_parameters` ×3 | ❌ | API 8: sin email / sin password / sin ambos → 400 |
| `test_delete_method_not_supported` | ❌ | API 9: DELETE → 405 |
| `test_full_account_lifecycle` | 🔁 | API 11-14: crear → consultar → actualizar → eliminar → verificar |
| `test_unicode_data_round_trip` | ❌ | Acentos, ñ, ø, ü persisten sin corrupción |
| `test_duplicate_email_is_rejected` | ❌ | Email duplicado → 400 |
| `test_create_account_missing_required_field` ×5 | ❌ | Cada campo obligatorio faltante → 400 con mensaje específico |
| `test_delete_nonexistent_account` | ❌ | → 404 |
| `test_delete_with_wrong_password_keeps_account` | ❌🔒 | No borra y la cuenta sigue operativa |
| `test_get_detail_of_unknown_email` | ❌ | → 404 |

## UI — `tests/ui/`

### Autenticación (`test_authentication.py`)

| Test | Tipo | Valida |
|---|---|---|
| `test_register_and_delete_user` | 🔁 | TC1 completo, datos precargados, sesión y baja |
| `test_signup_with_existing_email` | ❌ | TC5 |
| `test_signup_blocked_by_invalid_email_format` | ❌ | Validación HTML5, sin submit |
| `test_login_with_valid_credentials` | ✅ | TC2 + visibilidad de Logout / Login |
| `test_logout` | ✅ | TC4 + la sesión realmente terminó |
| `test_login_with_wrong_password` | ❌ | TC3 |
| `test_login_with_invalid_credentials` ×4 | ❌🔒 | Data-driven; distingue bloqueo del navegador vs error del servidor |
| `test_login_client_side_validation` ×3 | ❌ | Email vacío / password vacío / email mal formado, prueba que no hubo submit |
| `test_password_field_is_masked` | 🔒 | `type="password"` |

### Catálogo (`test_products.py`)

| Test | Tipo | Valida |
|---|---|---|
| `test_product_list_and_detail` | ✅ | TC8 |
| `test_ui_catalog_matches_api` | ✅ | Híbrido: UI == API |
| `test_all_prices_are_positive` | ✅ | Integridad de precios |
| `test_search_shows_related_products` ×3 | ✅ | TC9, con la API como oráculo |
| `test_search_without_results` | ❌ | Grilla vacía sin error |
| `test_search_does_not_execute_injected_scripts` ×5 | 🔒 | XSS/SQLi: ningún `alert()` se ejecuta |
| `test_filter_by_category` ×3 | ✅ | TC18 (Women/Men/Kids) |
| `test_filter_by_brand` ×3 | ✅ | TC19, con la API como oráculo |
| `test_write_review` | ✅ | TC21 |
| `test_review_requires_fields` | ❌ | Campos obligatorios |

### Carrito (`test_cart.py`)

| Test | Tipo | Valida |
|---|---|---|
| `test_add_multiple_products` | ✅ | TC12: precio × cantidad = total |
| `test_product_quantity_from_detail` | ✅ | TC13 |
| `test_same_product_twice_accumulates_quantity` | ❌ | No duplica filas |
| `test_quantity_boundaries` ×2 | ❌ | Valores límite 1 y 99 |
| `test_remove_product_empties_cart` | ✅ | TC17 |
| `test_remove_one_of_many` | ❌ | Borrado parcial |
| `test_empty_cart_message` | ❌ | Estado vacío |
| `test_guest_checkout_requires_login` | ❌ | Modal de login para invitados |
| `test_cart_persists_after_login` | 🔁 | TC20 |
| `test_add_from_recommended_items` | ✅ | TC22 |

### Checkout (`test_checkout.py`)

| Test | Tipo | Valida |
|---|---|---|
| `test_place_order_and_download_invoice` | 🔁 | TC16/23/24: direcciones, total, pago, factura descargada y leída |
| `test_cart_is_empty_after_order` | ✅ | Post-condición del pedido |
| `test_register_during_checkout` | 🔁 | TC14 |
| `test_payment_requires_card_data` | ❌ | Tarjeta vacía no confirma |

### Contacto, suscripción y navegación (`test_contact_and_home.py`)

| Test | Tipo | Valida |
|---|---|---|
| `test_submit_contact_form_with_attachment` | ✅ | TC6: upload + diálogo JS aceptado |
| `test_dismiss_dialog_does_not_submit` | ❌ | Diálogo cancelado |
| `test_invalid_email_blocks_submission` | ❌ | Validación HTML5 |
| `test_subscribe_from_footer` ×2 | ✅ | TC10/TC11 |
| `test_subscribe_with_invalid_email` | ❌ | Email inválido |
| `test_home_page_loads` | ✅ | Smoke de la home |
| `test_main_menu_navigation` ×6 | ✅ | TC7 + todos los links del menú |
| `test_scroll_up_with_arrow` | ✅ | TC25 |
| `test_scroll_up_without_arrow` | ✅ | TC26 |

## Performance — `tests/performance/`

| Test | Valida |
|---|---|
| `test_page_load_within_budget` ×5 | TTFB, DOMContentLoaded y Load de 5 páginas críticas |
| `test_core_web_vitals` ×5 | LCP y CLS (solo Chromium) |
| `test_p95_latency_within_sla` ×4 | p95 de 4 endpoints de lectura |

## Unit — `tests/unit/`

40 tests sobre el propio framework: parseo de precios, percentiles, enmascarado de secretos en logs
y en `repr`, unicidad e inmutabilidad de factories, patrón de bloqueo de ads y detección de muros anti-bot.
