# Plan de pruebas

Cada caso de uso enlaza a su sección aquí (`plan-de-pruebas.md#cu-XX`). Se
agrupan en cuatro categorías, porque no todas se prueban de la misma forma —
mezclar "el saldo es correcto" con "el sistema tolera una caída" en el mismo
tipo de prueba es la razón por la que RN-01/02 y RNF-01/02/03 requieren
técnicas distintas (ver
[`../01-requisitos/modelo-de-negocio.md`](../01-requisitos/modelo-de-negocio.md)).

| Categoría | Qué prueba | Cómo |
|---|---|---|
| Unitarias | Reglas de negocio puras (RN-01 a RN-14) | `unittest`/`pytest` sobre el módulo `dominio`, sin red ni BD |
| Integración | Rutas HTTP, forma de las peticiones y respuestas | Cliente HTTP contra un nodo levantado en pruebas |
| Concurrencia | RF-07, RF-08, RN-01, RN-02 bajo carga; además, operaciones locales concurrentes con una `TRANSFERENCIA_EXTERNA` (RF-25) `PENDIENTE` | N hilos operando sobre las mismas cuentas, límite de tiempo, sin `sleep` fijo; `GatewayExterno` falso con latencia configurable para forzar la ventana `PENDIENTE` |
| Tolerancia a fallas | RF-09 a RF-13, RNF-01 a RNF-03 | `SIGKILL` al primario, aislamiento de red (CU-12), medición del tiempo de failover |
| Rendimiento | RNF-04, RNF-05 | *Benchmark* con concurrencia creciente (1, 2, 4, 8, 16, 32 clientes) |

## CU-01

Crear cuenta con saldo inicial válido y negativo (rechazo); moneda soportada y
no soportada (rechazo, RF-19).

## CU-02

Consultar saldo de cuenta existente e inexistente (E1); lectura marcada como
desactualizada contra una réplica.

## CU-03

Depósito y retiro válidos; retiro que deja saldo negativo (E1, RN-01); monto
no positivo (E2).

## CU-04

Transferencia válida entre cuentas de la misma moneda; saldo insuficiente
(E1); reintento con el mismo `op_id` tras simular la caída del primario a
mitad de la operación (RN-08) — ver también la prueba de tolerancia a fallas
más abajo.

## CU-05

Transferencia con conversión válida; tasa no configurada para el par de
monedas (4a); verificación de que `tasa_aplicada` queda fija en el registro
aunque la tasa configurada cambie después (RN-06).

## CU-06

Autotransferencia entre dos cuentas propias; rechazo si origen = destino
(E1); rechazo si la cuenta destino no pertenece al mismo usuario (E2).

## CU-07

Extracto de una cuenta con operaciones de los cinco tipos (`CREACION`,
`DEPOSITO`, `RETIRO`, `TRANSFERENCIA`, `CAMBIO`), verificando que una
conversión muestra la tasa aplicada.

## CU-08

Auditoría por moneda tras miles de operaciones sorteadas con semilla fija
(RNF-06) — la invariante de RN-02 debe sostenerse por cada moneda por
separado.

## CU-09

`SIGKILL` al proceso del primario en medio de transferencias concurrentes;
verificar que: (a) la auditoría da el mismo total antes y después, (b) el
nuevo primario asume en menos de 2 s (RNF-03), (c) el primario antiguo que
vuelve se despromueve sin confirmar nada.

## CU-10

Reiniciar un nodo detenido durante N operaciones; verificar que recupera su
estado exacto y se pone al día con el primario.

## CU-11

100 hilos retirando de la misma cuenta (el saldo nunca queda negativo, no se
pierde ninguna operación); dos transferencias cruzadas simultáneas
(`alice→bob` y `bob→alice`) sin interbloqueo, con límite de tiempo, 20
ejecuciones seguidas sin fallar una (mismo criterio que Prototipo 1).

## CU-12

Cada tipo de falla (`derribar`, `aislar`, `atrasar`, `limpiar`) aplicado y
verificado por separado; prueba de *split-brain*: aislar al primario, dejar
que los otros dos elijan uno nuevo, verificar que el antiguo no confirma nada
al reconectarse.

## CU-13

El estado mostrado coincide con `GET /interno/estado` de cada nodo real; un
nodo caído se marca como tal sin bloquear la vista de los demás.

## CU-14

Apertura de cuenta de ahorro con tasa válida; saldo inicial negativo
(rechazo). Acreditación de interés al vencer el período: verificar que se
registra como operación `INTERES` visible en el extracto (no como cambio
directo de `saldo_centavos`), y que sin mayoría el interés queda pendiente
para el próximo *tick* (E2).

## CU-15

Apertura de plazo fijo con fecha de vencimiento futura; fecha no futura
(rechazo, E2). Intentar `RETIRO`/`TRANSFERENCIA` antes de vencer (rechazo,
E3, RN-12); acreditación del interés completo al vencer y que la cuenta
vuelve a admitir salidas justo después.

## CU-16

Transferencia externa que el `GatewayExterno` (falso, en pruebas)
confirma; una que rechaza; una que agota el tiempo de espera — en los tres
casos, el total del sistema (RN-02) debe cuadrar. Prueba de concurrencia
dedicada: con el *stub* configurado a latencia alta, lanzar N operaciones más
sobre la misma cuenta origen mientras la externa sigue `PENDIENTE` y verificar
que se sirven sin esperar al *stub* (no quedan bloqueadas) y sin corromper el
saldo. `SIGKILL` al primario con una externa `PENDIENTE`: el nuevo primario
retoma la operación desde el log replicado (RF-13) en vez de reiniciar el
débito.

## CU-17

Login con contraseña correcta e incorrecta (E1/E2, mismo mensaje para no
revelar si el email existe); token emitido por un nodo se valida
correctamente en **otro** nodo distinto, sin ninguna llamada entre ellos —
verifica que la llave simétrica está bien compartida (RN-16).
