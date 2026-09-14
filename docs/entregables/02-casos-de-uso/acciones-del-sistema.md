# Acciones del sistema

Lista plana de todo lo que el sistema permite hacer, antes de entrar al
detalle de cada caso de uso. Sirve como *checklist* rápido de cobertura: si
algo del negocio no está aquí, no tiene caso de uso todavía.

| # | Acción | Caso de uso | Requiere autenticación de dueño |
|---|---|---|---|
| 1 | Crear una cuenta con saldo inicial y moneda | CU-01 | No (alta) |
| 2 | Consultar el saldo de una cuenta | CU-02 | Sí |
| 3 | Depositar en una cuenta | CU-03 | No (cualquiera puede depositar a una cuenta existente) |
| 4 | Retirar de una cuenta | CU-03 | Sí |
| 5 | Transferir entre cuentas de la misma moneda | CU-04 | Sí (cuenta origen) |
| 6 | Transferir entre cuentas de distinta moneda (con conversión) | CU-05 | Sí (cuenta origen) |
| 7 | Transferir entre dos cuentas propias (autotransferencia) | CU-06 | Sí |
| 8 | Consultar el extracto de operaciones de una cuenta | CU-07 | Sí |
| 9 | Auditar el total de dinero en circulación | CU-08 | No (rol administrador) |
| 10 | Seguir operando con un servidor caído | CU-09 | — (propiedad del sistema) |
| 11 | Recuperar el estado de un servidor reiniciado | CU-10 | — (automático) |
| 12 | Procesar operaciones concurrentes sin corromper saldos | CU-11 | — (propiedad del sistema) |
| 13 | Provocar una falla controlada (caída, aislamiento, retraso) | CU-12 | No (rol ingeniero de pruebas) |
| 14 | Ver el estado del clúster (nodos, rol, epoch) | CU-13 | No (rol administrador) |
| 15 | Abrir una cuenta de ahorro con interés periódico | CU-14 | No (alta) |
| 16 | Abrir un depósito a plazo fijo | CU-15 | No (alta) |
| 17 | Transferir a un sistema externo (interoperable) | CU-16 | Sí (cuenta origen) |
| 18 | Iniciar sesión con email y contraseña | CU-17 | No (es lo que la establece) |

Las acciones 10, 11 y 12 son **propiedades del sistema**, no botones en una
pantalla — se validan con pruebas automatizadas y con la demo en vivo, no con
una interfaz de usuario. Por eso sus casos de uso no tienen mockup propio (ver
la nota en cada uno).
