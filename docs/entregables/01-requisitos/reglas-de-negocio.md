# Reglas de negocio (RN)

Consolida las reglas del PDF de la propuesta (sección 4), las reglas de
integridad descritas en
[`../05-modelo-de-datos/modelo-logico.md`](../05-modelo-de-datos/modelo-logico.md),
y las que se agregaron con el alcance de monedas múltiples y multi-cuenta.
Cada caso de uso en
[`../02-casos-de-uso/`](../02-casos-de-uso/) referencia estas reglas por ID —
no se repite el texto completo en cada CU.

| ID | Regla |
|---|---|
| RN-01 | El saldo de una cuenta nunca puede quedar negativo |
| RN-02 | El dinero nunca se crea ni se destruye en una operación dentro de la misma moneda |
| RN-03 | Una transferencia es atómica: se aplican las dos puntas (débito y crédito), o ninguna |
| RN-04 | Todas las cuentas del sistema están en el mismo grupo replicado; no se dividen clientes entre servidores distintos |
| RN-05 | Un usuario puede poseer varias cuentas, en la misma o distinta moneda; una cuenta pertenece a un único usuario |
| RN-06 | Una conversión de moneda registra la tasa aplicada en el momento de la operación; no se recalcula después con la tasa vigente al consultar |
| RN-07 | Una escritura solo se confirma al cliente después de replicarse en la mayoría de los nodos |
| RN-08 | El identificador de operación (`op_id`) es único; una operación repetida con el mismo `op_id` no se vuelve a aplicar |
| RN-09 | Una confirmación de réplica se registra una sola vez por servidor y por operación |
| RN-10 | Los servidores pueden caer o responder lento, pero no actúan de forma maliciosa (fallas por colapso, no bizantinas) |
| RN-11 | Una autotransferencia (entre dos cuentas del mismo usuario) exige que ambas cuentas existan y sean distintas entre sí |
| RN-12 | Un depósito a plazo fijo no admite `RETIRO` ni ser cuenta origen de una `TRANSFERENCIA` antes de su `fecha_vencimiento` |
| RN-13 | El interés de una cuenta de ahorro o de un depósito a plazo fijo se acredita como una operación `INTERES` más — nunca se escribe directamente sobre `saldo_centavos` |
| RN-14 | Una `TRANSFERENCIA_EXTERNA` debita la cuenta origen de inmediato y queda `PENDIENTE` hasta que el sistema externo confirme o rechace; si rechaza o no responde a tiempo, el monto se devuelve con una operación de reverso, nunca reescribiendo el saldo — mientras tanto, el resto de operaciones sobre esa cuenta se siguen sirviendo (no quedan bloqueadas por la espera externa) |
| RN-15 | La contraseña de un usuario nunca se guarda en texto plano ni cifrada de forma reversible — solo como el resultado de una función de hash de un solo sentido |
| RN-16 | El token de sesión se firma con una llave simétrica compartida por todos los nodos del clúster, para que cualquier nodo pueda validar una sesión sin tener que consultar al nodo que la emitió |

## Regla fuera de alcance que cambió

El PDF original excluye explícitamente "interfaz gráfica web" del alcance
(regla 7 de la sección 4). El proyecto **se desvía de esto a propósito**: hoy
se está construyendo un frontend web (ver `docs/adr/ADR-0002-...md` y
`ADR-0003-linha-grafica.md`). Se deja registrado aquí como desvío consciente,
siguiendo el mismo patrón que `docs/SPECS.md` §11 usa para documentar
desvíos frente a la propuesta original — para que se pueda explicar en la
defensa por qué se hizo, no para que pase desapercibido.
