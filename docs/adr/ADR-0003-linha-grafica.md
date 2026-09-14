# ADR-0003 — Línea gráfica del frontend

**Estado:** decidido.

Relacionado: [`ADR-0002-stack-tecnologico-e-implantacao.md`](ADR-0002-stack-tecnologico-e-implantacao.md).

---

## Contexto

`ADR-0002` fijó que el frontend sería "estilo aplicativo móvil, responsive"
pero sin definir una referencia visual concreta. Sin una referencia, cada
mockup termina con un criterio distinto (el primer intento del mockup de CU-05
usó un tema oscuro genérico, sin relación con el dominio del proyecto). Se
necesita una línea gráfica única, con una fuente de inspiración real, para que
los ~13 mockups de casos de uso sean consistentes entre sí.

## Decisión

Usar como referencia visual **Nubank** — banco digital brasileño, coherente
con la premisa propia del proyecto ("un banco moderno de Brasil"), con un
sistema de diseño maduro, reconocible y bien documentado.

### Paleta de colores

| Token | Valor | Uso |
|---|---|---|
| `--morado` | `#820AD1` | Color de marca. Botones primarios, elementos activos, montos destacados |
| `--morado-oscuro` | `#5A0791` | Estado presionado/hover del morado |
| `--morado-suave` | `#F3E8FC` | Fondos de chips, resaltados suaves sobre blanco |
| `--fondo` | `#F7F7F9` | Fondo general de la pantalla (gris muy claro, no blanco puro) |
| `--superficie` | `#FFFFFF` | Tarjetas y superficies elevadas |
| `--borde` | `#E7E7EC` | Bordes sutiles entre superficies |
| `--texto` | `#1A1A2E` | Texto principal |
| `--texto-tenue` | `#6B6B7B` | Texto secundario, etiquetas |
| `--exito` | `#00A868` | Montos positivos, confirmaciones |
| `--error` | `#E5484D` | Montos negativos, errores, saldo insuficiente |

Regla de uso: el morado se reserva para acciones y acentos — **no** se usan
fondos morados completos de pantalla. La base es siempre clara (`--fondo` /
`--superficie`), como en la propia aplicación de Nubank (la tarjeta física es
morada; la app es predominantemente blanca).

### Tipografía

Familia geométrica y redondeada, sin serifas. Nubank usa una fuente propia
("Nubank Sans"); como no está disponible públicamente, se usa como
equivalente **Inter** (Google Fonts) con una pila de respaldo de fuentes de
sistema, para que los mockups sigan viéndose bien sin conexión:

```css
font-family: 'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif;
```

Jerarquía: montos y saldos en peso `700` y tamaño grande (24–32px); títulos de
pantalla `600`; texto de cuerpo `400–500`; etiquetas en mayúsculas pequeñas
para campos de formulario.

### Componentes

- **Tarjetas**: fondo blanco, borde `1px solid var(--borde)`, radio `16px`,
  sombra suave (`0 2px 12px rgba(0,0,0,0.04)`) — nunca sombras duras ni bordes
  gruesos.
- **Botones primarios**: fondo `--morado`, texto blanco, radio `12px`, alto
  mínimo `52px` (objetivo táctil), sin bordes.
- **Campos de formulario**: fondo `--fondo` (no blanco, para distinguirse de
  la tarjeta que los contiene), radio `10px`, sin bordes visibles salvo al
  enfocar.
- **Iconografía**: lineal, trazo simple, sin relleno — nunca ilustraciones
  detalladas ni emojis como iconos.
- **Navegación**: barra inferior de pestañas, iconos + etiqueta, ítem activo en
  morado sobre fondo blanco.

### Espaciado

Base de `4px`. Separación entre secciones de una pantalla: `20–24px`. Padding
interno de tarjetas: `16–20px`.

## Consecuencias

- Todos los mockups de `entregables/02-casos-de-uso/mockups/` se rehacen con
  esta paleta y estos componentes — el mockup de CU-05 hecho antes de esta ADR
  queda obsoleto y se reemplaza.
- Como es una referencia de **otra marca**, el documento de defensa debe dejar
  claro que es una *inspiración de línea gráfica* para fines académicos, no una
  afirmación de asociación con Nubank.
- Al fijar una sola fuente (Inter) y una sola paleta, cualquier mockup nuevo
  que no siga esta tabla se considera una desviación a corregir, no una
  alternativa válida.
