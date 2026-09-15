# Matriz de trazabilidad completa

La vista operacional: cada RF/RNF con su endpoint real, su caso de prueba y su
estado de implementación. Complementa (no repite) a
[`../02-casos-de-uso/matriz-caso-de-uso-vs-rf.md`](../02-casos-de-uso/matriz-caso-de-uso-vs-rf.md)
(vista de negocio: CU × RF) y a
[`../04-modulos/matriz-modulo-requisito.md`](../04-modulos/matriz-modulo-requisito.md)
(vista de código: módulo × RF/RNF).

**Estado** usa el mismo vocabulario que `docs/ROADMAP.md`: `hecho`, `en curso`,
`no iniciado`.

## Requisitos funcionales

| RF | Endpoint | Caso de prueba | Estado |
|---|---|---|---|
| RF-01 | `POST /cuentas` | [CU-01](../08-pruebas-y-despliegue/plan-de-pruebas.md#cu-01) | no iniciado |
| RF-02 | `GET /cuentas/{id}` | [CU-02](plan-de-pruebas.md#cu-02) | no iniciado |
| RF-03 | `POST /cuentas/{id}/deposito`, `/retiro` | [CU-03](plan-de-pruebas.md#cu-03) | no iniciado |
| RF-04 | `POST /transferencias` | [CU-04](plan-de-pruebas.md#cu-04) | no iniciado |
| RF-05 | `POST /transferencias` (misma entrada de log) | [CU-04](plan-de-pruebas.md#cu-04) | no iniciado |
| RF-06 | `POST /cuentas/{id}/retiro`, `/transferencias` | [CU-03](plan-de-pruebas.md#cu-03), [CU-04](plan-de-pruebas.md#cu-04) | no iniciado |
| RF-07 | Todas las rutas de lectura | [CU-02](plan-de-pruebas.md#cu-02), [CU-11](plan-de-pruebas.md#cu-11) | no iniciado |
| RF-08 | `POST /transferencias`, `/deposito`, `/retiro` | [CU-11](plan-de-pruebas.md#cu-11) | no iniciado |
| RF-09 | `POST /interno/votar` | [CU-09](plan-de-pruebas.md#cu-09) | no iniciado |
| RF-10 | `POST /interno/replicar` | [CU-04](plan-de-pruebas.md#cu-04), [CU-09](plan-de-pruebas.md#cu-09) | no iniciado |
| RF-11 | `GET /interno/estado` | [CU-09](plan-de-pruebas.md#cu-09), [CU-13](plan-de-pruebas.md#cu-13) | no iniciado |
| RF-12 | Arranque del proceso (sin ruta HTTP) | [CU-10](plan-de-pruebas.md#cu-10) | no iniciado |
| RF-13 | Cualquier ruta de escritura (por `op_id`) | [CU-04](plan-de-pruebas.md#cu-04), [CU-09](plan-de-pruebas.md#cu-09) | no iniciado |
| RF-14 | `GET /auditoria` | [CU-08](plan-de-pruebas.md#cu-08) | no iniciado |
| RF-15 | `GET /admin/metricas` | — | no iniciado |
| RF-16 | `POST /admin/falla` | [CU-12](plan-de-pruebas.md#cu-12) | no iniciado |
| RF-17 | Frontend web y `banco.cli` | Todos los CU con pantalla | no iniciado |
| RF-18 | — (en revisión, ver `../01-requisitos/requisitos-funcionales.md`) | — | en revisión |
| RF-19 | `POST /cuentas` (campo `moneda`) | [CU-01](plan-de-pruebas.md#cu-01) | no iniciado |
| RF-20 | `POST /transferencias/conversion` | [CU-05](plan-de-pruebas.md#cu-05) | no iniciado |
| RF-21 | `POST /transferencias/autotransferencia` | [CU-06](plan-de-pruebas.md#cu-06) | no iniciado |
| RF-22 | `GET /cuentas/{id}/extracto` | [CU-07](plan-de-pruebas.md#cu-07) | no iniciado |
| RF-23 | `POST /cuentas/ahorro` (interés vía *tick* interno, sin ruta HTTP propia) | [CU-14](plan-de-pruebas.md#cu-14) | no iniciado |
| RF-24 | `POST /cuentas/plazo-fijo` | [CU-15](plan-de-pruebas.md#cu-15) | no iniciado |
| RF-25 | `POST /transferencias/externa` | [CU-16](plan-de-pruebas.md#cu-16) | no iniciado |
| RF-26 | `POST /auth/login` | [CU-17](plan-de-pruebas.md#cu-17) | no iniciado |

## Requisitos no funcionales

| RNF | Métrica | Caso de prueba | Estado |
|---|---|---|---|
| RNF-01 | 0 discrepancias en la suma de saldos | [CU-08](plan-de-pruebas.md#cu-08), [CU-09](plan-de-pruebas.md#cu-09) | no iniciado |
| RNF-02 | 100% de operaciones confirmadas sobreviven a `SIGKILL` | [CU-09](plan-de-pruebas.md#cu-09) | no iniciado |
| RNF-03 | Failover medido < 2 s | [CU-09](plan-de-pruebas.md#cu-09) | no iniciado |
| RNF-04 | ≥ 500 TPS (meta de medición) | Benchmark (sección "Rendimiento" de `plan-de-pruebas.md`) | no iniciado |
| RNF-05 | p99 < 200 ms | Benchmark | no iniciado |
| RNF-06 | Misma semilla ⇒ mismo resultado | [CU-08](plan-de-pruebas.md#cu-08), [CU-11](plan-de-pruebas.md#cu-11) | no iniciado |
| RNF-07 | 100% de eventos clave logueados | — | no iniciado |
| RNF-08 | 100% de módulos con código+prueba+documentación | Toda la sección [`../04-modulos/`](../04-modulos/) | no iniciado |
| RNF-09 | Un comando, 0 pasos manuales | — (en revisión, ver `../01-requisitos/requisitos-no-funcionales.md`) | en revisión |
| RNF-10 | 100% de componentes con fallas documentadas | Este documento + README de cada módulo | no iniciado |
| RNF-11 | Responde con ≥ 1 de 2-3 nodos activos | [CU-09](plan-de-pruebas.md#cu-09) | no iniciado |

Todos los estados están en `no iniciado` porque el código de esta ampliación
de alcance (multi-moneda, Postgres, frontend) todavía no se ha escrito — esta
matriz se actualiza a medida que cada pieza se implementa, siguiendo la misma
disciplina de `docs/ROADMAP.md` (una subfase solo cuenta como hecha con
código, pruebas y documentación).
