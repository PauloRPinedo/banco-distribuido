# Requisitos funcionales (RF)

Fuente original: `docs/proposta_banco_distribuido_simples.pdf`, sección 8. Se
agregaron RF-19 a RF-21 por la ampliación de alcance (monedas múltiples,
multi-cuenta) decidida durante el Prototipo 1/2, RF-23 a RF-25 por la
ampliación de productos financieros (ahorro, plazo fijo, transferencia
externa) pedida por el profesor, y RF-26 por la autenticación mínima que
`modelo-de-negocio.md` ya listaba dentro de alcance pero no estaba
implementada. La columna **Estado** y la de
**endpoint/caso de prueba** viven en
[`../08-pruebas-y-despliegue/matriz-trazabilidad-completa.md`](../08-pruebas-y-despliegue/matriz-trazabilidad-completa.md)
para no mantener la misma información en dos tablas.

| ID | Requisito | Prioridad |
|---|---|---|
| RF-01 | Permitir crear cuentas con saldo inicial definido | Alta |
| RF-02 | Permitir consultar el saldo de cualquier cuenta | Alta |
| RF-03 | Permitir depósito y retiro en una cuenta | Alta |
| RF-04 | Permitir transferencia entre cuentas de la misma moneda | Alta |
| RF-05 | Garantizar que una transferencia sea atómica: se aplican los dos lados, o ninguno | Alta |
| RF-06 | Rechazar transferencias que dejarían el saldo negativo | Alta |
| RF-07 | Garantizar que una lectura vea un estado consistente | Alta |
| RF-08 | Hacer que operaciones concurrentes sobre la misma cuenta entren en conflicto, sin corromper el saldo | Alta |
| RF-09 | Elegir automáticamente un nuevo primario cuando el actual falla | Alta |
| RF-10 | Confirmar una escritura al cliente solo después de replicarla en la mayoría de los nodos | Alta |
| RF-11 | Continuar atendiendo aunque uno de los servidores esté fuera de servicio | Alta |
| RF-12 | Recuperar el estado de un servidor reiniciado y reintegrarlo al sistema | Alta |
| RF-13 | Resolver automáticamente operaciones interrumpidas por falla del cliente o del primario | Alta |
| RF-14 | Ofrecer una auditoría del total de dinero en circulación | Alta |
| RF-15 | Exponer métricas de desempeño y estado de los servidores | Media |
| RF-16 | Permitir inyectar fallas durante la ejecución con fines de prueba | Media |
| RF-17 | Dar, vía cliente de línea de comandos o interfaz web, acceso a todas las operaciones | Media |
| RF-18 | Permitir configurar, al inicio, cuáles son los 2 o 3 servidores participantes | Baja — **en revisión** |
| RF-19 | Permitir que una cuenta se denomine en una de tres monedas (BRL, USD, PEN) | Alta |
| RF-20 | Permitir transferencias con conversión entre cuentas de distinta moneda, aplicando una tasa de cambio configurada | Alta |
| RF-21 | Permitir que un usuario posea varias cuentas y transfiera entre sus propias cuentas | Media |
| RF-22 | Permitir consultar el extracto de operaciones de una cuenta | Alta |
| RF-23 | Permitir abrir una cuenta de ahorro que acredita interés periódicamente a una tasa configurada | Media |
| RF-24 | Permitir abrir un depósito a plazo fijo con tasa y fecha de vencimiento, bloqueando retiros y transferencias de salida antes de esa fecha | Media |
| RF-25 | Permitir transferencias hacia sistemas externos interoperables, confirmadas de forma asíncrona sin bloquear el resto de operaciones sobre la cuenta origen | Media |
| RF-26 | Permitir que un usuario inicie sesión con email y contraseña, recibiendo un token de sesión firmado con una llave simétrica compartida por todos los nodos | Alta |

## Nota sobre RF-22

El PDF de la propuesta lista el extracto como funcionalidad (F-05 en
`docs/proposta.md`) pero nunca le asignó un RF propio en su tabla de
requisitos — un vacío del documento original. Se agrega aquí para que CU-07
tenga a qué requisito trazar.

## Nota sobre RF-18

El equipo señaló que modelar la configuración de nodos como un requisito
**funcional** (algo que el usuario final pide) no termina de convencer — es
más una decisión de **infraestructura/despliegue** que una funcionalidad del
banco. Queda anotado aquí como pendiente de replantear (posiblemente como
parte de [`../03-arquitectura/vista-general.md`](../03-arquitectura/vista-general.md)
en vez de la tabla de RF), sin resolverlo unilateralmente hasta que el equipo
lo decida.
