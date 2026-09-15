# Modelo lógico

Entidades con atributos, tipos y restricciones, sin atarse todavía a la
sintaxis de un motor específico (eso es [`modelo-fisico.md`](modelo-fisico.md)).
Formaliza las entidades de
[`modelo-conceptual-er.md`](modelo-conceptual-er.md): Usuario, Cuenta (con
moneda propia), Operación (incluyendo conversión, interés y transferencia
externa), Tasa de cambio y Sistema externo. No incluye `Servidor` ni
`RegistroReplicacion` — ver el porqué en la sección final de
`modelo-conceptual-er.md`.

## Usuario

| Campo | Tipo | Restricciones |
|---|---|---|
| `id` | UUID | PK |
| `nombre` | VARCHAR(120) | NOT NULL |
| `email` | VARCHAR(255) | NOT NULL, UNIQUE |
| `password_hash` | VARCHAR(255) | NOT NULL — nunca la contraseña en texto plano ni cifrada de forma reversible (RN-15) |
| `fecha_creacion` | TIMESTAMP | NOT NULL |

## Cuenta

| Campo | Tipo | Restricciones |
|---|---|---|
| `id` | VARCHAR(64) | PK |
| `usuario_id` | UUID | FK → Usuario.id, NOT NULL |
| `moneda` | VARCHAR(3) | NOT NULL, CHECK IN ('BRL','USD','PEN') |
| `saldo_centavos` | BIGINT | NOT NULL, DEFAULT 0, CHECK ≥ 0 |
| `fecha_creacion` | TIMESTAMP | NOT NULL |
| `estado` | VARCHAR(20) | NOT NULL, DEFAULT 'ACTIVA' — ACTIVA / BLOQUEADA / CERRADA |
| `tipo_producto` | VARCHAR(20) | NOT NULL, DEFAULT 'CORRIENTE' — CORRIENTE / AHORRO / PLAZO_FIJO (RF-23, RF-24) |
| `tasa_interes` | NUMERIC(9,6) | NULL — solo AHORRO (tasa periódica) y PLAZO_FIJO (tasa del plazo); NULL en CORRIENTE |
| `fecha_ultimo_interes` | TIMESTAMP | NULL — solo AHORRO; última vez que se acreditó interés |
| `fecha_vencimiento` | TIMESTAMP | NULL — solo PLAZO_FIJO; antes de esta fecha no se admite `RETIRO` ni salida en `TRANSFERENCIA` (RN-12) |

Restricción por tipo de producto:

| `tipo_producto` | `tasa_interes` | `fecha_ultimo_interes` | `fecha_vencimiento` |
|---|---|---|---|
| CORRIENTE | NULL | NULL | NULL |
| AHORRO | Obligatoria, > 0 | Obligatoria (= fecha de creación al abrir) | NULL |
| PLAZO_FIJO | Obligatoria, > 0 | NULL | Obligatoria, posterior a `fecha_creacion` |

## Operación

| Campo | Tipo | Restricciones |
|---|---|---|
| `id` | UUID | PK — también es el `op_id` de deduplicación (RN-08) |
| `tipo` | VARCHAR(25) | NOT NULL — CREACION / DEPOSITO / RETIRO / TRANSFERENCIA / CAMBIO / INTERES / TRANSFERENCIA_EXTERNA |
| `cuenta_origen_id` | VARCHAR(64) | FK → Cuenta.id, NULL |
| `cuenta_destino_id` | VARCHAR(64) | FK → Cuenta.id, NULL |
| `valor_centavos` | BIGINT | NOT NULL, CHECK ≥ 0 — monto en la moneda de origen |
| `moneda_origen` | VARCHAR(3) | NULL — solo en `CAMBIO` |
| `moneda_destino` | VARCHAR(3) | NULL — solo en `CAMBIO` |
| `tasa_aplicada` | NUMERIC(18,8) | NULL — solo en `CAMBIO`; fija en el momento (RN-06) |
| `valor_destino_centavos` | BIGINT | NULL — solo en `CAMBIO`; resultado de aplicar la tasa |
| `sistema_externo_id` | VARCHAR(32) | FK → SistemaExterno.id, NULL — solo en `TRANSFERENCIA_EXTERNA` |
| `referencia_externa` | VARCHAR(64) | NULL — solo en `TRANSFERENCIA_EXTERNA`; identificador que da el sistema externo al confirmar, sirve para conciliar |
| `fecha_hora` | TIMESTAMP | NOT NULL |
| `estado` | VARCHAR(20) | NOT NULL — PENDIENTE / CONFIRMADA / RECHAZADA / CANCELADA |

Uso de las cuentas y campos según el tipo:

| Tipo | Origen | Destino | Campos propios |
|---|---|---|---|
| CREACION | NULL | Obligatoria | — |
| DEPOSITO | NULL | Obligatoria | — |
| RETIRO | Obligatoria (no `PLAZO_FIJO` antes de vencer, RN-12) | NULL | — |
| TRANSFERENCIA | Obligatoria (no `PLAZO_FIJO` antes de vencer, RN-12) | Obligatoria, distinta, **misma moneda** | — |
| CAMBIO | Obligatoria | Obligatoria, distinta, **moneda distinta** | `moneda_origen`, `moneda_destino`, `tasa_aplicada`, `valor_destino_centavos` obligatorios |
| INTERES | NULL | Obligatoria — la cuenta `AHORRO`/`PLAZO_FIJO` que gana el interés | — (RN-13) |
| TRANSFERENCIA_EXTERNA | Obligatoria (cuenta local) | NULL — el destino no es una cuenta de este sistema | `sistema_externo_id` obligatorio; `referencia_externa` se completa al confirmar (RN-14) |

## Sistema externo

Contraparte fuera del clúster a la que se le envía una `TRANSFERENCIA_EXTERNA`
(RF-25) — es dato de negocio (el extracto del cliente debe poder mostrar a
quién se le mandó la plata), no infraestructura del clúster; no confundir con
el mecanismo de replicación descrito en la sección final de
[`modelo-conceptual-er.md`](modelo-conceptual-er.md).

| Campo | Tipo | Restricciones |
|---|---|---|
| `id` | VARCHAR(32) | PK |
| `nombre` | VARCHAR(120) | NOT NULL |
| `codigo` | VARCHAR(20) | NOT NULL, UNIQUE — código de ruteo hacia esa contraparte |
| `activo` | BOOLEAN | NOT NULL, DEFAULT TRUE |

## Tasa de cambio

| Campo | Tipo | Restricciones |
|---|---|---|
| `moneda_origen` | VARCHAR(3) | PK compuesta |
| `moneda_destino` | VARCHAR(3) | PK compuesta, distinta de `moneda_origen` |
| `valor` | NUMERIC(18,8) | NOT NULL, > 0 |
| `vigente_desde` | TIMESTAMP | NOT NULL |

Tasa **fija, configurada en el sistema** — no se consulta una API externa en
tiempo real (ver `docs/adr/ADR-0002-...md`). Un cambio de tasa se hace
insertando una nueva fila con `vigente_desde` posterior; las operaciones ya
registradas conservan su `tasa_aplicada` propia.
