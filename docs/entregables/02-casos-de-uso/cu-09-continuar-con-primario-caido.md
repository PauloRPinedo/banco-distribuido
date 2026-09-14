# CU-09 — Continuar operando con el primario caído

| Campo | Valor |
|---|---|
| Actor principal | Cliente (indirectamente) |
| Actores secundarios | Nodo primario, nodos réplica |
| Requisitos relacionados | RF-09, RF-10, RF-11 |
| Casos de prueba relacionados | [`plan-de-pruebas.md`](../08-pruebas-y-despliegue/plan-de-pruebas.md#cu-09) |
| Pantalla | No aplica — es una propiedad del sistema, no una acción que el cliente dispara desde una pantalla (ver [`acciones-del-sistema.md`](acciones-del-sistema.md)) |

## Descripción

Cuando el primario deja de responder, las réplicas lo detectan por ausencia
de *heartbeat*, eligen un nuevo primario por mayoría de votos, y el sistema
sigue aceptando escrituras — sin que el cliente necesite hacer nada más que
reintentar su operación contra el nuevo primario.

## Precondición

El clúster tiene al menos 3 nodos (con 2, la caída de uno deja al superviviente
sin mayoría — ver `docs/SPECS.md` §9).

## Postcondición

Un nuevo primario fue elegido, con `epoch` mayor al anterior, y el sistema
vuelve a aceptar escrituras.

## Flujo principal

| # | Acción del actor | Respuesta del sistema |
|---|---|---|
| 1 | — (el primario deja de enviar *heartbeat*) | Las réplicas detectan la ausencia tras el `timeout` de elección sorteado |
| 2 | — | Una réplica se postula como candidata, incrementa su `epoch` y pide voto a las demás |
| 3 | — | Si obtiene mayoría de votos, se convierte en el nuevo primario y envía *heartbeat* inmediato |
| 4 | El cliente reintenta su operación pendiente | El nuevo primario la procesa con el mismo `op_id`, sin duplicar el dinero |

## Flujos alternativos

| # | Condición | Respuesta del sistema |
|---|---|---|
| 2a | Dos réplicas se postulan al mismo tiempo (empate) | Ninguna alcanza mayoría; se sortea un nuevo `timeout` y se repite la elección con un `epoch` mayor |

## Excepciones

| # | Condición | Respuesta del sistema |
|---|---|---|
| E1 | No hay mayoría de nodos vivos para elegir un primario | El sistema queda en modo solo lectura; no se aceptan escrituras |
| E2 | El primario antiguo vuelve a estar disponible | Al ver un `epoch` mayor al suyo, se despromueve a réplica sin haber confirmado nada más |

## Reglas de negocio asociadas

| ID regla | Descripción breve |
|---|---|
| RN-07 | Una escritura solo se confirma tras la mayoría |
| RN-08 | El `op_id` es único; una operación repetida no se vuelve a aplicar |

## Diagrama de estados

Ver el diagrama de estados del rol de un nodo en
[`../06-diseno-detallado/diagrama-de-estados-nodo.md`](../06-diseno-detallado/diagrama-de-estados-nodo.md) —
este caso de uso es, en esencia, ese diagrama disparado por la ausencia de
*heartbeat*.

## Cómo se valida

No con una pantalla, sino con la prueba: matar el proceso del primario en
medio de transferencias concurrentes, y verificar que la auditoría (CU-08) da
el mismo total antes y después. Ver
[`../08-pruebas-y-despliegue/plan-de-pruebas.md`](../08-pruebas-y-despliegue/plan-de-pruebas.md)
y CU-12 (mecanismo para provocar la caída de forma controlada).

## Notas de trazabilidad

Corresponde a la historia de usuario 8 del PDF de la propuesta.
