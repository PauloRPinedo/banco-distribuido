# Diccionario de datos

Campo por campo, con su descripción y la regla de negocio que protege, cuando
aplica. Complementa a [`modelo-logico.md`](modelo-logico.md) (que dice el tipo
y la restricción) con el **porqué** de cada campo.

## Usuario

| Campo | Descripción |
|---|---|
| `id` | Identificador único del usuario, generado por el sistema al registrarse |
| `nombre` | Nombre completo, solo informativo |
| `email` | Identifica al usuario; único en todo el sistema |
| `password_hash` | Resultado de una función de hash de un solo sentido (`PBKDF2-HMAC-SHA256` con sal), nunca la contraseña ni una versión reversible de ella (RN-15) — usado en CU-17 para verificar el inicio de sesión |
| `fecha_creacion` | Momento del alta del usuario |

## Cuenta

| Campo | Descripción |
|---|---|
| `id` | Identificador de la cuenta, visible al cliente |
| `usuario_id` | Dueño de la cuenta — un usuario puede tener varias (RN-05) |
| `moneda` | Una de BRL/USD/PEN; fija desde la creación, no cambia después |
| `saldo_centavos` | Saldo en centavos enteros de la moneda de la cuenta, nunca `float` (mismo principio que Prototipo 1, ver `docs/SPECS.md` §3.1) |
| `fecha_creacion` | Momento de creación de la cuenta |
| `estado` | Si la cuenta puede operar (`ACTIVA`) o no |
| `tipo_producto` | Qué producto es: `CORRIENTE` (sin interés, sin plazo), `AHORRO` (interés periódico) o `PLAZO_FIJO` (interés único al vencer, sin retiros antes) — RF-23, RF-24 |
| `tasa_interes` | Tasa que se aplica al calcular la operación `INTERES`: periódica en `AHORRO`, del plazo completo en `PLAZO_FIJO` |
| `fecha_ultimo_interes` | Solo `AHORRO` — marca desde cuándo contar el próximo período de interés; la revisa el mismo *tick* periódico del primario que ya dispara el `heartbeat` (RF-09), no un proceso nuevo |
| `fecha_vencimiento` | Solo `PLAZO_FIJO` — hasta que no se cumple, `RETIRO` y la salida de una `TRANSFERENCIA` se rechazan (RN-12) |

## Operación

| Campo | Descripción |
|---|---|
| `id` | Identificador único; funciona también como `op_id` para deduplicación (RN-08) — si el cliente reintenta con el mismo `id`, se devuelve el resultado ya guardado |
| `tipo` | Qué clase de movimiento es |
| `cuenta_origen_id` / `cuenta_destino_id` | Según el tipo (ver tabla en `modelo-logico.md`) |
| `valor_centavos` | Monto en la moneda de origen |
| `moneda_origen` / `moneda_destino` | Solo se llenan en una conversión (`CAMBIO`) |
| `tasa_aplicada` | La tasa vigente **al momento** de la conversión — queda fija para siempre en esta fila (RN-06); nunca se recalcula al consultar el extracto después |
| `valor_destino_centavos` | Resultado de aplicar `tasa_aplicada` a `valor_centavos` — se guarda ya calculado, no se deriva en cada lectura |
| `sistema_externo_id` | A qué contraparte externa se le envió el dinero, solo en `TRANSFERENCIA_EXTERNA` (RF-25) |
| `referencia_externa` | El identificador que el sistema externo devuelve al confirmar — permite conciliar esa operación con el registro del otro lado si hace falta reclamar |
| `fecha_hora` | Cuándo el primario aceptó la operación |
| `estado` | En qué punto del ciclo de vida está — `PENDIENTE` hasta que la mayoría confirma (RN-07); en `TRANSFERENCIA_EXTERNA` además queda `PENDIENTE` mientras se espera la respuesta del sistema externo (RN-14) |

## Tasa de cambio

| Campo | Descripción |
|---|---|
| `moneda_origen` / `moneda_destino` | El par de monedas al que aplica esta tasa |
| `valor` | Cuántas unidades de `moneda_destino` equivalen a 1 unidad de `moneda_origen` |
| `vigente_desde` | Desde cuándo rige este valor — permite tener historial de tasas sin borrar las anteriores |

## Sistema externo

| Campo | Descripción |
|---|---|
| `id` | Identificador interno de la contraparte |
| `nombre` | Nombre informativo, para mostrar en el extracto del cliente |
| `codigo` | Código de ruteo usado para dirigir la transferencia hacia esa contraparte |
| `activo` | Si hoy se le pueden enviar transferencias; una contraparte inactiva rechaza nuevas `TRANSFERENCIA_EXTERNA` sin intentar contactarla |

No hay entradas para `Servidor` ni `RegistroReplicacion`: quién es cada nodo y
quién confirmó una escritura es estado del mecanismo de replicación, no un
dato del negocio — ver el porqué en la última sección de
[`modelo-conceptual-er.md`](modelo-conceptual-er.md). `SistemaExterno` sí es
una entidad de negocio, aunque también sea "externa" al clúster: a diferencia
de `Servidor`, el cliente sí pregunta por ella (a quién le mandó su dinero).
