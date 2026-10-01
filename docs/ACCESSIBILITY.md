# Accesibilidad

El framework audita las páginas principales con [axe-core](https://github.com/dequelabs/axe-core)
contra **WCAG 2.0 y 2.1, niveles A y AA** (el estándar que exigen la mayoría de las normativas).

```bash
pytest -m a11y                       # auditoría completa (Chromium)
pytest -m a11y -k TestAxeEngine      # solo los tests del motor (offline, no usan el sitio)
```

## Estado actual: el sitio NO cumple WCAG 2.1 AA

**Decisión del proyecto: no se usa baseline.** Los 6 tests de páginas del sitio fallan mientras existan
violaciones graves, para que el incumplimiento sea visible en cada corrida en lugar de quedar registrado
como deuda aceptada. En CI corren en un job propio, **"Accesibilidad (WCAG 2.1 AA)"**, separado de "UI":
su rojo conocido no tapa la señal de los tests funcionales.

Hallazgos de la primera auditoría (01/10/2026, Chromium):

| Regla | Impacto | Elementos | Problema para el usuario |
|---|---|---|---|
| `button-name` | crítico | `#subscribe` (footer, todas las páginas), `#submit_search` | Botones con solo un ícono: el lector de pantalla los anuncia como "botón" sin decir qué hacen |
| `label` | crítico | `#quantity` (detalle de producto), `input[type=file]` (contacto) | Campos sin etiqueta: no se sabe qué ingresar |
| `link-name` | grave | Flechas de los carruseles de la home | Links sin texto accesible |
| `color-contrast` | grave | 108 elementos en las 6 páginas (naranja sobre blanco, títulos del slider) | Texto difícil de leer con baja visión |

Son defectos del sitio bajo prueba, no del framework. En un proyecto real, cada fila sería un ticket.

## Cómo decide si un test falla: baseline con "trinquete" (opcional)

El framework soporta un baseline de violaciones conocidas, por si el proyecto decide en el futuro tolerar
la deuda actual y detectar solo empeoramientos (habitual cuando el equipo no puede corregir todo de una vez).

Si existe `test_data/a11y_baseline.json`, la comparación funciona así:

| Situación | Resultado |
|---|---|
| Violación **nueva** de impacto `serious` o `critical` | ❌ El test falla |
| Violación ya registrada en `test_data/a11y_baseline.json` | ✅ Se tolera (deuda conocida) |
| Violación `moderate` o `minor` | ✅ Se reporta en Allure, no falla |
| Una violación del baseline **ya no ocurre** | ⚠️ `A11yBaselineOutdatedWarning`: quitarla del baseline |

El baseline **solo puede achicarse**: cada regla corregida se quita, y si reaparece, el test lo detecta.
Así la accesibilidad del sitio puede mejorar, pero nunca empeorar en silencio.

## Actualizar el baseline

```bash
pytest -m a11y                              # genera reports/a11y/<pagina>.json
python scripts/update_a11y_baseline.py      # imprime +agregadas / -corregidas y actualiza el archivo
```

Con resultados descargados de un artifact de CI: `--results ruta/a/reports/a11y`.

> Agregar una regla al baseline es **aceptar una deuda de accesibilidad**. Hacelo en un PR propio,
> con el diff visible, nunca como efecto colateral de otro cambio.

## Qué revisar ante un fallo

El mensaje lista cada violación nueva con el selector de los elementos afectados y un link a la
explicación de la regla (`dequeuniversity.com`). En Allure, el adjunto `axe <pagina>` tiene el
detalle completo.

## Limitaciones

La auditoría automática detecta aproximadamente un tercio de los problemas de accesibilidad
(contraste, textos alternativos, nombres accesibles, estructura ARIA). No reemplaza la prueba manual
con lector de pantalla ni la navegación solo con teclado.
