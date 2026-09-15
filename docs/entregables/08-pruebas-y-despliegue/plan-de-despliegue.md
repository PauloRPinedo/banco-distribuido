# Plan de despliegue

Ejecuta las decisiones de
[`../../docs/adr/ADR-0001-persistencia-replicacao-implantacao.md`](../../docs/adr/ADR-0001-persistencia-replicacao-implantacao.md)
y [`ADR-0002-stack-tecnologico-e-implantacao.md`](../../docs/adr/ADR-0002-stack-tecnologico-e-implantacao.md).
Ver el diagrama en
[`../03-arquitectura/diagrama-de-despliegue.md`](../03-arquitectura/diagrama-de-despliegue.md).

## Topología

- 3 instancias de **backend** (Nodo A, B, C) — contenedor Docker con FastAPI.
- 3 instancias de **PostgreSQL**, una por nodo, **separadas** de su backend
  (decisión del equipo, ver `ADR-0002-...md`, sección "Recomendación: dónde
  corre el backend") — 6 instancias en total para los 3 nodos.
- **Balanceador en AWS Lambda** (Function URL) y **frontend en Vercel** —
  ninguno de los dos es una instancia (ver `ADR-0002-...md`, sección
  "Recomendación: dónde corre el balanceador y el frontend").
- Misma VPC/red privada para las 6 instancias de nodo; Lambda y Vercel
  quedan fuera de la VPC, hablándole a los nodos por su API pública.

## Requisitos de red

| Puerto/regla | Entre quién | Público u interno |
|---|---|---|
| Function URL de Lambda / Vercel | Usuario → balanceador/frontend | Público (HTTPS) |
| API HTTP del nodo (8001) | Lambda (balanceador) → cualquier nodo | Público, pero solo alcanzable con la dirección exacta — ver nota |
| `/interno/replicar`, `/interno/votar`, `/interno/log`, `/interno/estado` | Entre nodos A, B, C | Interno a la VPC — no exponer a internet |
| PostgreSQL (5432) | Backend de un nodo → **su propia** instancia de Postgres, únicamente | Interno a la VPC, abierto solo hacia esa IP de backend |

**Nota:** como Lambda no vive dentro de la VPC de los nodos (a menos que se
configure explícitamente esa integración, con más complejidad y sin
beneficio claro aquí), la API de cada nodo necesita una IP pública — pero
sigue protegida por *security group* para aceptar solo el rango de IPs de
salida de Lambda, no internet en general. Alternativa más simple si se
prefiere evitar esto: correr el balanceador en una instancia dentro de la
misma VPC en vez de Lambda — vuelve a sumar una instancia, pero simplifica
la red. Ver el trade-off en `ADR-0002-...md`.

## Procedimiento

Ver el detalle completo, con comandos, en
[`../../../projeto-final/GUIA-DESPLIEGUE.md`](../../../projeto-final/GUIA-DESPLIEGUE.md).
Resumen:

1. Crear las 6 instancias de nodo en la misma VPC y *security group*.
2. En cada instancia de Postgres, correr el DDL de
   [`../05-modelo-de-datos/modelo-fisico.md`](../05-modelo-de-datos/modelo-fisico.md).
3. Desplegar el backend de cada nodo, apuntando por red a **su propia**
   instancia de Postgres (nunca a la de otro nodo) y a las direcciones
   internas de los otros dos nodos (`config/cluster.json`, mismo formato
   que ya define `docs/SPECS.md` §9).
4. **Probar cada dirección con `curl`/`psql` antes de subir el clúster
   completo** (mismo paso que ya exige `docs/SPECS.md` §9 — una regla de
   *firewall* mal puesta se ve como "elección que no converge" o "no
   conecta a la BD", y hace perder horas buscando en el lugar equivocado).
5. Desplegar la función Lambda del balanceador (imagen de contenedor,
   `CLUSTER_CONFIG_JSON` con las direcciones públicas de los 3 nodos) y el
   frontend en Vercel (`vercel deploy`).
6. Confirmar el estado del clúster desde CU-13 antes de la demo.

## Guion de la demostración en vivo

1. Mostrar CU-13 (estado del clúster): 3 nodos activos, A primario.
2. Hacer una transferencia (CU-04) y una conversión (CU-05) desde el
   frontend.
3. Abrir una cuenta de ahorro (CU-14) y un plazo fijo (CU-15); mostrar el
   extracto (CU-07) después de que el *tick* acredite el interés.
4. Lanzar una transferencia externa (CU-16) con el *stub* configurado a
   latencia alta, y mientras sigue `PENDIENTE`, hacer un depósito sobre la
   misma cuenta desde otra pestaña — mostrar que se confirma de inmediato,
   sin esperar al sistema externo.
5. Mostrar la auditoría (CU-08) con el total correcto por moneda.
6. Usar CU-12 para derribar el nodo primario.
7. Mostrar CU-13 de nuevo: nuevo primario, `epoch` mayor.
8. Repetir la transferencia pendiente (si la hubo) y mostrar que no se
   duplicó el dinero.
9. Cerrar con la auditoría (CU-08): mismo total que al inicio.

## Costo esperado

Ver el análisis completo de *free tier* en `ADR-0001-...md` y `ADR-0002-...md`.
Con backend y base de datos en instancias **separadas**, son 6 instancias de
nodo (no 3) — el doble de horas del *free tier* de AWS EC2 (750 h/mes
compartidas entre todas las instancias) se agota al doble de rápido. Con
instancias detenidas fuera de las sesiones de prueba, sigue siendo viable
dentro de $0-5, pero deja menos margen — Oracle Cloud Always Free (sin
límite de 12 meses) es la alternativa más cómoda para mantener las 6
instancias arriba más tiempo sin vigilar el reloj del *free tier*.
Balanceador (Lambda) y frontend (Vercel) no suman a esta cuenta — corren en
sus propias capas gratuitas, permanentes, así que no valía la pena
convertirlos en una séptima instancia solo por consistencia.
