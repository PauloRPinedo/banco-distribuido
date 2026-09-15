# Guía de réplica con PostgreSQL

Responde una pregunta concreta que ya se discutió largo en el diseño: **¿la
réplica la hace Postgres o la hace la aplicación?** — la hace **la
aplicación**. Esta guía explica cómo, y por qué no se usa `streaming
replication` nativo ni ningún servicio gestionado (RDS Multi-AZ, Cloud SQL
HA, etc.).

## La decisión, en una frase

Cada nodo tiene **su propio** Postgres, completo e independiente — los 3
Postgres nunca se conectan entre sí y no se hablan directamente. El módulo
`cluster` (backend) es el que decide qué escritura replicar hacia los otros
nodos y cuándo darla por confirmada — ver la Decisión 1 de
[`docs/adr/ADR-0001-persistencia-replicacao-implantacao.md`](../docs/adr/ADR-0001-persistencia-replicacao-implantacao.md).

## Por qué no `streaming replication` / RDS Multi-AZ / Cloud SQL HA

No es una limitación técnica — Postgres sabe hacer replicación nativa
perfectamente bien. Es que, si se delega ahí, **desaparece exactamente lo
que este proyecto evalúa**: RF-09 (elección de primario), RF-10
(confirmación por mayoría) y RF-13 (recuperación tras falla) dejan de tener
sentido si un motor de base de datos ya resuelve la disponibilidad por su
cuenta. Sería la "Opción B" que `ADR-0001` ya analizó y descartó.

Además, en la práctica: un servicio de replicación gestionado tiene HA de
pago en la capa gratuita de cualquier proveedor grande — no es una opción
"gratis" real para este proyecto (ver la tabla de `ADR-0001`, Decisión 2).

## Cómo se ve en la práctica: replicación por máquina de estados

En vez de copiar bytes de un disco a otro (lo que hace `streaming
replication`), se copia el **comando**:

1. El cliente manda una escritura al primario (ej. una transferencia).
2. El primario valida, y en vez de escribir directo, arma una entrada de
   log con la operación.
3. Envía esa misma entrada, por HTTP, a los otros 2 nodos
   (`POST /interno/replicar` — ver `docs/SPECS.md` §6.2, pendiente en
   `banco/cluster/nodo.py`, marcado `TODO(prototipo-2)`).
4. Cada nodo (primario incluido) aplica esa operación contra **su propio**
   Postgres local, con SQL normal (`INSERT`/`UPDATE`), usando exactamente el
   mismo código de dominio — no hay ninguna instrucción SQL "especial" de
   replicación.
5. El primario responde al cliente solo después de que la mayoría (2 de 3)
   confirmó haber aplicado la entrada.

El resultado: las 3 bases terminan con el mismo contenido, no porque
Postgres las sincronizó, sino porque las 3 corrieron la misma secuencia
determinista de comandos. Es el mismo principio que `dominio/` ya usa desde
Prototipo 1 (funciones puras, mismo resultado con el mismo log) — aquí se
extiende de "un proceso, un WAL" a "tres procesos, tres Postgres".

## Instalación de Postgres por nodo

Con Docker (recomendado, ver [`GUIA-DESPLIEGUE.md`](GUIA-DESPLIEGUE.md)):
cada nodo levanta su propio contenedor `postgres:16-alpine`, con el esquema
de [`db/schema.sql`](db/schema.sql) (copiado de
[`docs/entregables/05-modelo-de-datos/modelo-fisico.md`](../docs/entregables/05-modelo-de-datos/modelo-fisico.md))
cargado automáticamente al iniciar (`docker-entrypoint-initdb.d`).

**Nota honesta sobre "Docker vs. nativo" para Postgres**, porque no es una
elección sin matices: la imagen oficial de Postgres en Docker Hub está
pensada para prueba de concepto, desarrollo y aprendizaje — a nivel
profesional, un banco real en producción no correría `docker run postgres`
tal cual, sin más. Los caminos serios en producción real son (a) un motor
gestionado (RDS/Cloud SQL — descartado aquí a propósito, ver más arriba), o
(b) Postgres en contenedores pero con un operador especializado
(CloudNativePG, Crunchy Postgres, el operador de Zalando) sobre Kubernetes,
o (c) instalación nativa + herramientas dedicadas de respaldo
(`pgBackRest`/`barman`) + algo como Patroni para alta disponibilidad.

Para este proyecto, Docker simple sigue siendo la elección correcta —
porque es exactamente el caso de uso que esa misma literatura marca como
válido (aprendizaje/demo, no una base con dinero real), y porque usar la
misma imagen en tu `docker compose` local y en EC2 evita que la versión de
Postgres diverja entre "cómo lo pruebas" y "cómo lo despliegas". Los
`docker run` de `GUIA-DESPLIEGUE.md` ya incluyen `--restart unless-stopped`
y un límite de memoria — el mínimo que esa misma fuente pide para no
depender de la config por defecto del contenedor.

**Lo que falta, y queda fuera de alcance a propósito:** ninguna estrategia
de respaldo (WAL archiving, `pg_dump` programado) ni afinado de memoria más
allá del límite del contenedor — si esto fuera a manejar dinero real, esa
sería la primera brecha a cerrar antes que cualquier otra cosa.

Sin Docker, instalación nativa en cada instancia:

```bash
sudo apt install postgresql-16
sudo -u postgres createuser banco --pwprompt
sudo -u postgres createdb banco --owner banco
psql -U banco -d banco -f db/schema.sql
```

En ambos casos: **nada** de `pg_hba.conf` para aceptar conexiones de otros
nodos, **nada** de `wal_level = replica`, **nada** de `primary_conninfo` —
esas son justo las configuraciones de `streaming replication` que este
proyecto no usa. El único que se conecta al Postgres de un nodo es el
backend de **ese mismo** nodo — backend y Postgres viven en instancias
separadas (ver `docs/entregables/03-arquitectura/diagrama-de-despliegue.md`),
así que esa conexión sí cruza la red privada de la VPC, pero el puerto 5432
se abre únicamente hacia la IP del backend de ese nodo, nunca a internet ni
al resto de la VPC.

## Cómo verificar a mano que las 2-3 bases quedan iguales

Cuando la replicación real ya esté implementada (hoy es un `TODO` en
`banco/cluster/nodo.py`, ver `docs/ROADMAP.md` subfase 2.2):

```bash
# tras una transferencia confirmada, comparar los saldos en cada Postgres
docker exec projeto-final-postgres-a-1 psql -U banco -d banco -c "SELECT id, saldo_centavos FROM cuenta ORDER BY id;"
docker exec projeto-final-postgres-b-1 psql -U banco -d banco -c "SELECT id, saldo_centavos FROM cuenta ORDER BY id;"
docker exec projeto-final-postgres-c-1 psql -U banco -d banco -c "SELECT id, saldo_centavos FROM cuenta ORDER BY id;"
```

Las tres consultas deben devolver **exactamente** las mismas filas. Hoy
(sin la replicación implementada) esto falla a propósito — solo el
Postgres del nodo que atendió la escritura tiene los datos; es la prueba
más simple de que la subfase 2.2 del ROADMAP todavía está pendiente, no un
error de esta guía.

## Tasas de cambio y otros datos "que se llenan solos"

El mismo mecanismo de replicación aplica a `tasa_cambio` (RF-23/RF-24, ver
`docs/entregables/01-requisitos/reglas-de-negocio.md`): el *tick* periódico
del primario escribe la fila nueva, la replica igual que cualquier otra
escritura, y cada nodo la aplica a su propio Postgres — no hay una tabla
"compartida" en ningún sitio.
