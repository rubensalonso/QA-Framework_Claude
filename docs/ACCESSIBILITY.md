# Accesibilidad

El framework audita las páginas principales con [axe-core](https://github.com/dequelabs/axe-core)
contra **WCAG 2.0 y 2.1, niveles A y AA** (el estándar que exigen la mayoría de las normativas).

```bash
pytest -m a11y                       # auditoría completa (Chromium)
pytest -m a11y -k TestAxeEngine      # solo los tests del motor (offline, no usan el sitio)
```

## Cómo decide si un test falla: baseline con "trinquete"

Un sitio existente casi siempre tiene violaciones previas. Un test que exige "cero violaciones"
quedaría rojo para siempre y nadie lo miraría. Por eso:

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
