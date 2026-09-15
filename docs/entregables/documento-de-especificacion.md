# Documento de especificación — Banco Distribuido

Índice completo del documento técnico. Cada sección vive en su propio
archivo — ver [`README.md`](README.md) para el porqué de esta organización.

## 0. Identificación

| Número USP | Nombre |
|---|---|
| 18404636 | Jefferson Daniel Flores Montenegro |
| 18514632 | Cristhian Jesus Maylle Briceño |
| 17819748 | Paulo Sebastian Rojo Pinedo |

Fuente original: [`../docs/proposta_banco_distribuido_simples.pdf`](../docs/proposta_banco_distribuido_simples.pdf).
Feedback y decisiones metodológicas de esta ampliación:
[`../docs/revisao_e_recomendacoes.md`](../docs/revisao_e_recomendacoes.md).

## 1. Introducción y alcance

Un banco distribuido donde 2-3 servidores mantienen una única copia lógica de
las cuentas, en tres monedas (BRL, USD, PEN), con conversión entre ellas y
multi-cuenta por usuario. Además de la cuenta corriente, ofrece cuenta de
ahorro con interés periódico, depósito a plazo fijo, y transferencias hacia
sistemas externos interoperables. Ver el detalle en
[`01-requisitos/modelo-de-negocio.md`](01-requisitos/modelo-de-negocio.md).

## 2. Requisitos

- [Requisitos funcionales](01-requisitos/requisitos-funcionales.md)
- [Requisitos no funcionales](01-requisitos/requisitos-no-funcionales.md)
- [Modelo de negocio](01-requisitos/modelo-de-negocio.md)
- [Reglas de negocio](01-requisitos/reglas-de-negocio.md)

## 3. Casos de uso

Índice completo, actores, y las dos matrices de trazabilidad en
[`02-casos-de-uso/README.md`](02-casos-de-uso/README.md).

## 4. Arquitectura

- [Vista general](03-arquitectura/vista-general.md)
- [Diagrama de componentes](03-arquitectura/diagrama-de-componentes.md)
- [Diagrama de despliegue](03-arquitectura/diagrama-de-despliegue.md)
- Decisiones de arquitectura: [`../docs/adr/`](../docs/adr/) (ADR-0001 persistencia y replicación,
  ADR-0002 stack y despliegue, ADR-0003 línea gráfica)

## 5. Módulos

- [Mapa de módulos](04-modulos/mapa-de-modulos.md)
- [Diagrama de paquetes](04-modulos/diagrama-de-paquetes.md)
- [Matriz módulo × requisito](04-modulos/matriz-modulo-requisito.md)

## 6. Modelo de datos

- [Modelo conceptual (E-R)](05-modelo-de-datos/modelo-conceptual-er.md)
- [Modelo lógico](05-modelo-de-datos/modelo-logico.md)
- [Modelo físico (DDL PostgreSQL)](05-modelo-de-datos/modelo-fisico.md)
- [Diccionario de datos](05-modelo-de-datos/diccionario-de-datos.md)

## 7. Diseño detallado (Análisis y Diseño de Sistemas)

Regla de dónde vive cada diagrama: si pertenece a un único caso de uso y está
al mismo nivel de negocio que ese caso de uso, vive **dentro** de su archivo
en [`02-casos-de-uso/`](02-casos-de-uso/) — no se repite aquí. Solo entra a
esta carpeta lo que no tiene un único dueño (comportamiento del clúster, como
la elección) o lo que es la misma historia contada para otro lector (una
vista técnica de implementador, distinta de la vista de negocio ya dibujada
en el caso de uso).

- [Diagrama de clases — entidad](06-diseno-detallado/diagrama-de-clases-entidad.md)
- [Diagrama de clases — interfaz](06-diseno-detallado/diagrama-de-clases-interfaz.md)
- [Diagrama de clases — servicio](06-diseno-detallado/diagrama-de-clases-servicio.md)
- Secuencia — transferencia (misma moneda), con conversión, y a sistema externo: viven dentro de cada caso de uso, no repetidas aquí — [CU-04](02-casos-de-uso/cu-04-transferir-misma-moneda.md#diagrama-de-secuencia-nivel-de-protocolo), [CU-05](02-casos-de-uso/cu-05-transferir-con-conversion.md#diagrama-de-secuencia), [CU-16](02-casos-de-uso/cu-16-transferir-sistema-externo.md#diagrama-de-secuencia-con-operación-concurrente-sobre-la-misma-cuenta)
- [Secuencia — elección y failover](06-diseno-detallado/diagrama-de-secuencia-eleccion-y-failover.md) (no pertenece a un único CU — ver la nota de esta sección)
- [Estados — rol de un nodo](06-diseno-detallado/diagrama-de-estados-nodo.md)
- [Actividades — conversión de moneda (vista técnica)](06-diseno-detallado/diagrama-de-actividades-cambio-moneda.md)
- [Actividades — tick periódico de interés y vencimiento](06-diseno-detallado/diagrama-de-actividades-tick-interes.md)

## 8. Tecnología

- [Stack tecnológico](07-tecnologia/stack-tecnologico.md)

## 9. Pruebas y despliegue

- [Plan de pruebas](08-pruebas-y-despliegue/plan-de-pruebas.md)
- [Matriz de trazabilidad completa (RF/RNF × endpoint × prueba × estado)](08-pruebas-y-despliegue/matriz-trazabilidad-completa.md)
- [Plan de despliegue](08-pruebas-y-despliegue/plan-de-despliegue.md)

## 10. Riesgos y decisiones abiertas

| Punto | Dónde se discute | Estado |
|---|---|---|
| RF-18 como requisito funcional | [`01-requisitos/requisitos-funcionales.md`](01-requisitos/requisitos-funcionales.md) | En revisión por el equipo |
| Framework de frontend | [`07-tecnologia/stack-tecnologico.md`](07-tecnologia/stack-tecnologico.md) | Pendiente |
| Framework de backend | [`07-tecnologia/stack-tecnologico.md`](07-tecnologia/stack-tecnologico.md) | Pendiente |
| Regla "sin dependencias externas" de `CONVENCOES.md` | [`../docs/adr/ADR-0002-stack-tecnologico-e-implantacao.md`](../docs/adr/ADR-0002-stack-tecnologico-e-implantacao.md) | Pendiente de decidir si se reescribe |
| Interfaz gráfica web, excluida en la propuesta original | [`01-requisitos/reglas-de-negocio.md`](01-requisitos/reglas-de-negocio.md) | Desvío consciente, documentado |

## 11. Trazabilidad — dónde vive cada tipo de rastreo

Para no mantener la misma información en varias tablas, cada matriz responde
una pregunta distinta:

| Matriz | Pregunta que responde |
|---|---|
| [`02-casos-de-uso/matriz-actor-caso-de-uso.md`](02-casos-de-uso/matriz-actor-caso-de-uso.md) | ¿Qué actor usa qué caso de uso? |
| [`02-casos-de-uso/matriz-caso-de-uso-vs-rf.md`](02-casos-de-uso/matriz-caso-de-uso-vs-rf.md) | ¿Qué caso de uso cumple qué RF? |
| [`04-modulos/matriz-modulo-requisito.md`](04-modulos/matriz-modulo-requisito.md) | ¿En qué módulo de código se implementa cada RF/RNF? |
| [`08-pruebas-y-despliegue/matriz-trazabilidad-completa.md`](08-pruebas-y-despliegue/matriz-trazabilidad-completa.md) | ¿Qué endpoint, qué prueba, y en qué estado está cada RF/RNF? |
