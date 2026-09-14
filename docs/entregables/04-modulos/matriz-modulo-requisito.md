# Matriz módulo × requisito

`X` = el módulo es donde ese requisito se implementa principalmente (puede
tocar otros módulos de forma secundaria).

| Módulo | RF relacionados | RNF relacionados |
|---|---|---|
| `dominio` | RF-01 a RF-06, RF-14, RF-19 a RF-24 | RNF-01 |
| `repositorio` | RF-12 | RNF-02, RNF-09 |
| `cluster` | RF-07 a RF-13, RF-23, RF-24 (tick de interés) | RNF-01, RNF-02, RNF-03, RNF-06, RNF-11 |
| `integraciones` | RF-25 | — |
| `autenticacion` | RF-26 | — |
| `api` | RF-15, RF-16, RF-17, RF-25, RF-26 | RNF-07 |
| `frontend` | RF-17 | — |
| `cli` | RF-17 | RNF-09 |
| `balanceador` | RF-13 (encuentra al primario, sigue `409`) | RNF-03, RNF-11 |

Esta es la contraparte de
[`../02-casos-de-uso/matriz-caso-de-uso-vs-rf.md`](../02-casos-de-uso/matriz-caso-de-uso-vs-rf.md):
esa matriz dice **qué caso de uso** cumple cada RF desde el punto de vista del
actor; esta dice **en qué módulo de código** se implementa desde el punto de
vista del desarrollador. La vista operacional completa (RF/RNF × endpoint ×
caso de prueba × estado) está en
[`../08-pruebas-y-despliegue/matriz-trazabilidad-completa.md`](../08-pruebas-y-despliegue/matriz-trazabilidad-completa.md).
