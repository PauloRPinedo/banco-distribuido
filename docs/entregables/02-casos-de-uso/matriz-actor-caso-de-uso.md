# Matriz actor × caso de uso

`X` = el actor inicia o participa directamente en el caso de uso.

| Caso de uso | Cliente | Administrador | Ingeniero de pruebas | Nodo (sistema) | Sistema externo |
|---|---|---|---|---|---|
| CU-01 Crear cuenta | X | | | | |
| CU-02 Consultar saldo | X | | | | |
| CU-03 Depositar y retirar | X | | | | |
| CU-04 Transferir (misma moneda) | X | | | X | |
| CU-05 Transferir con conversión | X | | | X | |
| CU-06 Autotransferencia | X | | | X | |
| CU-07 Consultar extracto | X | | | | |
| CU-08 Auditar total | | X | | | |
| CU-09 Continuar con primario caído | X | | | X | |
| CU-10 Recuperar estado al reiniciar | | X | | X | |
| CU-11 Operaciones concurrentes | X | | | X | |
| CU-12 Provocar falla para pruebas | | | X | X | |
| CU-13 Ver estado del clúster | | X | | X | |
| CU-14 Abrir cuenta de ahorro | X | | | X | |
| CU-15 Abrir depósito a plazo fijo | X | | | X | |
| CU-16 Transferir a sistema externo | X | | | X | X |
| CU-17 Iniciar sesión | X | | | | |

## Diagrama de casos de uso

```mermaid
flowchart LR
    Cliente((Cliente))
    Admin((Administrador))
    Tester((Ingeniero de pruebas))
    Externo((Sistema externo))

    subgraph Sistema[Banco distribuido]
        CU01([CU-01 Crear cuenta])
        CU02([CU-02 Consultar saldo])
        CU03([CU-03 Depositar y retirar])
        CU04([CU-04 Transferir misma moneda])
        CU05([CU-05 Transferir con conversion])
        CU06([CU-06 Autotransferencia])
        CU07([CU-07 Consultar extracto])
        CU08([CU-08 Auditar total])
        CU09([CU-09 Continuar con primario caido])
        CU10([CU-10 Recuperar estado])
        CU11([CU-11 Operaciones concurrentes])
        CU12([CU-12 Provocar falla])
        CU13([CU-13 Ver estado del cluster])
        CU14([CU-14 Abrir cuenta de ahorro])
        CU15([CU-15 Abrir plazo fijo])
        CU16([CU-16 Transferir a sistema externo])
        CU17([CU-17 Iniciar sesion])
    end

    Cliente --> CU01
    Cliente --> CU02
    Cliente --> CU03
    Cliente --> CU04
    Cliente --> CU05
    Cliente --> CU06
    Cliente --> CU07
    Cliente --> CU14
    Cliente --> CU15
    Cliente --> CU16
    Cliente --> CU17
    Cliente -.-> CU09
    Cliente -.-> CU11

    Admin --> CU08
    Admin --> CU13
    Admin -.-> CU10

    Tester --> CU12
    CU12 -.include.-> CU09

    Externo -.-> CU16
```
