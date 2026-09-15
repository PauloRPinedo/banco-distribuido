# Matriz de trazabilidad: caso de uso × requisito funcional

`X` = el RF se cumple (total o parcialmente) dentro de ese caso de uso.

| Caso de uso | RF-01 | RF-02 | RF-03 | RF-04 | RF-05 | RF-06 | RF-07 | RF-08 | RF-09 | RF-10 | RF-11 | RF-12 | RF-13 | RF-14 | RF-19 | RF-20 | RF-21 | RF-22 | RF-23 | RF-24 | RF-25 | RF-26 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CU-01 Crear cuenta | X | | | | | | | | | | | | | | X | | | | | | | |
| CU-02 Consultar saldo | | X | | | | | X | | | | | | | | | | | | | | | |
| CU-03 Depositar y retirar | | | X | | | X | | | | | | | | | | | | | | | | |
| CU-04 Transferir (misma moneda) | | | | X | X | X | X | X | | X | | | X | | | | | | | | | |
| CU-05 Transferir con conversión | | | | | X | X | | X | | X | | | X | | | X | | | | | | |
| CU-06 Autotransferencia | | | | X | X | X | | X | | X | | | X | | | | X | | | | | |
| CU-07 Consultar extracto | | | | | | | X | | | | | | | | | | | X | | | | |
| CU-08 Auditar total | | | | | | | | | | | | | | X | | | | | | | | |
| CU-09 Continuar con primario caído | | | | | | | | | X | X | X | | | | | | | | | | | |
| CU-10 Recuperar estado al reiniciar | | | | | | | | | | | | X | | | | | | | | | | |
| CU-11 Operaciones concurrentes | | | | | | | X | X | | | | | | | | | | | | | | |
| CU-12 Provocar falla para pruebas | | | | | | | | | | | | | | | | | | | | | | |
| CU-13 Ver estado del clúster | | | | | | | | | X | | X | | | | | | | | | | | |
| CU-14 Abrir cuenta de ahorro | X | | | | | | | | | | | | | | X | | | | X | | | |
| CU-15 Abrir depósito a plazo fijo | X | | | | | | | | | | | | | | X | | | | | X | | |
| CU-16 Transferir a sistema externo | | | | | | X | X | X | | X | | | X | | | | | | | | X | |
| CU-17 Iniciar sesión | | | | | | | | | | | | | | | | | | | | | | X |

RF-15, RF-16 y RF-17 no aparecen en la matriz de casos de uso porque son
transversales (métricas, inyección de fallas como mecanismo — no como caso de
uso de negocio — y acceso vía CLI/web). Su cobertura real, con endpoint y caso
de prueba, está en
[`../08-pruebas-y-despliegue/matriz-trazabilidad-completa.md`](../08-pruebas-y-despliegue/matriz-trazabilidad-completa.md).

RF-16 (inyectar fallas) es, en rigor, el **mecanismo** que usa CU-12 para
existir — por eso CU-12 no marca ningún RF de negocio: su propósito es probar
otros requisitos (RF-09 a RF-13), no cumplir uno propio.
