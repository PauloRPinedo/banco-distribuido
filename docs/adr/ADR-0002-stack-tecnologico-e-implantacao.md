# ADR-0002 — Stack tecnológico, línea gráfica y despliegue

**Estado:** parcialmente decidido — falta cerrar dónde corre el backend.

Relacionado: [`ADR-0001-persistencia-replicacao-implantacao.md`](ADR-0001-persistencia-replicacao-implantacao.md),
[`revisao_e_recomendacoes.md`](../revisao_e_recomendacoes.md), [`entregables/05-modelo-de-datos/`](../entregables/05-modelo-de-datos/).

---

## Contexto

El proyecto pasó de "cada nodo es backend+persistencia en un solo proceso con WAL
propio" (lo que describe `SPECS.md` y lo que ya está construido en Prototipo 1) a
"frontend + backend + base de datos", con PostgreSQL como motor y un frontend
independiente estilo aplicativo móvil. Esta ADR fija las tecnologías concretas
que se derivan de esa decisión, y deja registrada la pieza que aún falta
definir: dónde corre el backend.

---

## Decisiones

### Frontend

| Aspecto | Decisión |
|---|---|
| Línea gráfica | Estilo aplicativo móvil, pero **responsive** — se prueba también en laptop, no solo en celular |
| Hosting | **Vercel**, por simplicidad |
| Framework | **Pendiente de precisar.** Recomendación: React (con Vite, no Next.js — no hace falta *server-side rendering* para este alcance) o, si el equipo no tiene experiencia con React, un CSS *mobile-first* simple (Tailwind o CSS plano con `flexbox`/`grid`) sobre HTML servido estático. Vercel funciona bien con cualquiera de las dos |

Pautas de la línea gráfica *mobile-first* para los mockups (sección de casos de uso):
- Una sola columna, ancho máximo pensado para pantalla de celular (~390px), que se estira con `max-width` en pantallas más anchas — no un diseño de escritorio que se "encoge".
- Botones y campos táctiles (altura mínima ~44px).
- Navegación inferior o superior simple, sin menús de escritorio con muchos niveles.

### Backend

| Aspecto | Decisión |
|---|---|
| Lenguaje | **Python** — el equipo ya lo conoce y reutiliza el dominio de Prototipo 1 (`dominio/dinheiro.py`, `operacoes.py` se pueden migrar casi sin cambios) |
| Framework | **Pendiente.** Recomendación: **FastAPI** — genera documentación OpenAPI automática (útil para la columna "endpoint" de la matriz de trazabilidad), tiene soporte async nativo para hablar con Postgres sin bloquear el hilo que atiende el heartbeat entre nodos, y es lo más parecido en espíritu a lo que ya tenían con `http.server` pero sin escribir el enrutamiento a mano |
| Hosting | EC2 (u Oracle/Google Cloud), **instancia separada de su Postgres** — ver "Recomendación: dónde corre el backend" |

### Base de datos

| Aspecto | Decisión |
|---|---|
| Motor | **PostgreSQL** (reemplaza el WAL en JSONL / SQLite que se había mencionado antes) |
| Hosting | **AWS EC2** (instancia propia con Postgres instalado a mano, no RDS), **separada de la instancia del backend** — alternativa **Google Cloud**, por créditos disponibles en esa cuenta |
| Replicación | Sigue siendo **responsabilidad del equipo**, no de Postgres. Cada nodo tiene su propio Postgres; el backend de cada nodo es quien decide qué replicar, cuándo confirmar por mayoría y quién es primario — igual que en el diseño de `SPECS.md`, solo que ahora el WAL vive en tablas Postgres en vez de un archivo JSONL. **No se activa `streaming replication` nativo de Postgres ni RDS Multi-AZ** — hacerlo movería la responsabilidad de RF-09 a RF-13 fuera del código del equipo (ver ADR-0001, Decisión 1) |

---

## Recomendación: dónde corre el backend

**Decisión del equipo (reemplaza la recomendación original de co-ubicar):**
backend y base de datos van en **instancias separadas**, una por cada uno —
para 2-3 nodos, son 2-3 instancias de backend **más** 2-3 instancias de
Postgres, nunca backend y Postgres compartiendo la misma instancia. Cada
backend sigue hablando **solo con su propia base de datos** (nunca con la
de otro nodo) — eso no cambia; lo único que cambia es que esa conexión
cruza la red interna de la VPC en vez de ser `localhost`.

La recomendación original (co-ubicar por latencia) queda registrada abajo
porque explica un costo real que el equipo decidió aceptar a propósito, no
por descuido:

1. **Latencia.** Cada operación bancaria ya implica: cliente → backend →
   Postgres → replicar a los otros nodos → esperar mayoría → responder. Con
   backend y Postgres en instancias separadas, ese primer salto (backend →
   su Postgres) ahora cruza la red interna en vez de ser un socket local —
   más cerca del límite de RNF-05 (p99 < 200 ms), aunque dentro de la misma
   VPC esa latencia adicional es de milisegundos, no de segundos.
2. **Complejidad de red:** se necesitan reglas de *firewall*/*security
   group* adicionales para que cada backend alcance su Postgres por la red
   (puerto 5432 interno a la VPC, nunca expuesto a internet) — un paso más
   que sumar a los que ya pedía `SPECS.md` §9 para la red **entre nodos**.

Ambos proveedores (AWS EC2, o Google Cloud/Oracle Cloud por créditos, ver
`ADR-0001`) siguen sirviendo para esta topología — lo que sigue sin cambiar
es que backend y Postgres de un mismo nodo deben estar en el **mismo
proveedor y la misma VPC/red privada**, para no cruzar internet en ese
salto (eso sí seguiría pegando directo contra RNF-05).

## Recomendación: dónde corre el balanceador y el frontend

**Ninguno de los dos va en una instancia — decisión posterior, por costo.**
Con 3 nodos y backend/Postgres separados ya son 6 instancias; agregar una
séptima solo para el balanceador+frontend era el costo que más crecía sin
aportar nada al protocolo evaluado. La diferencia con los nodos es
estructural, no una preferencia:

| | Nodos | Balanceador | Frontend |
|---|---|---|---|
| Estado propio | Sí (Postgres, `epoch`, rol) | No | No |
| Necesita estar siempre encendido | Sí (*heartbeat* cada 150ms) | No (solo responde peticiones) | No (estático) |
| Encaja en *pay-per-use*/hosting estático | No | Sí | Sí |

**Decisión:** balanceador en **AWS Lambda** (Function URL, sin API Gateway),
frontend en **Vercel**. Ninguno de los dos delega el protocolo evaluado —
siguen siendo el mismo `enrutador.py` propio y el mismo React propio, solo
cambia dónde corren. Detalle de despliegue en `projeto-final/GUIA-DESPLIEGUE.md`.

**Trade-off aceptado:** el balanceador pierde el caché de "quién es
primario" entre invocaciones frías, y hay latencia de arranque en frío —
aceptable para una demo, no ideal si RNF-04/RNF-05 se miden en serio contra
el balanceador (medirlos contra los nodos directamente sigue siendo válido).

---

## Consecuencias

- **Se abandona la regla "sin dependencias externas" de `CONVENCOES.md`** a
  partir de esta etapa: Postgres necesita un *driver* (`psycopg2` o `asyncpg`),
  y FastAPI es en sí mismo una dependencia. Esto es correcto para lo que se
  está construyendo ahora, pero **hay que decidir explícitamente** si esa regla
  se reescribe para Prototipo 2/Proyecto final, dejando Prototipo 1 intacto
  como etapa ya entregada (tal como pide `CONVENCOES.md`: "uma etapa entregue
  não se altera").
- El cumplimiento de RF-09 a RF-13 sigue dependiendo de que la replicación
  entre los Postgres de cada nodo la escriba el equipo — cambiar de motor de
  almacenamiento no cambia esa exigencia (ver ADR-0001).
- Al fijar Postgres, el modelo de datos deja de ser solo un "modelo lógico" y
  pasa a tener un modelo físico real — hecho en
  [`entregables/05-modelo-de-datos/modelo-fisico.md`](../entregables/05-modelo-de-datos/modelo-fisico.md)
  con el `CREATE TABLE` real (el antiguo `modelamiento_datos.md` que se
  menciona aquí fue reemplazado por esa carpeta).

## Pendiente de decisión

- [ ] Framework de frontend (React/Vite vs. HTML+CSS simple)
- [ ] Framework de backend (FastAPI vs. mantener `http.server` de la biblioteca
      estándar)
- [ ] Confirmar si el backend va en AWS EC2 o Google Cloud (debe coincidir con
      donde esté la base de datos de cada nodo)
- [ ] Reescribir (o no) la regla de "sin dependencias externas" de
      `CONVENCOES.md` para las etapas que vienen
