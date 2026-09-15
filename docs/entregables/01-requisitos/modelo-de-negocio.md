# Modelo de negocio

## Propósito del sistema

Un banco distribuido donde 2 o 3 servidores mantienen una única copia lógica
de las cuentas de los clientes. Cada cuenta pertenece a un usuario y está
denominada en una de tres monedas (real brasileño, dólar estadounidense, sol
peruano). El sistema permite transferencias dentro de la misma moneda y entre
monedas distintas (con conversión a una tasa registrada), y garantiza que
ninguna operación crea ni destruye dinero — incluso si un servidor cae en
medio de una transacción.

Además de la cuenta corriente simple, el banco ofrece dos productos con
interés (cuenta de ahorro con interés periódico y depósito a plazo fijo) y
transferencias hacia sistemas externos al clúster (interoperables, RF-25) —
ver el detalle de los tres en
[`reglas-de-negocio.md`](reglas-de-negocio.md) (RN-12 a RN-14) y en
[`requisitos-funcionales.md`](requisitos-funcionales.md) (RF-23 a RF-25).

## Actores y su interés

| Actor | Qué quiere del sistema |
|---|---|
| Cliente | Mover su dinero (depositar, retirar, transferir, convertir entre monedas) con la confianza de que su saldo nunca se corrompe, incluso si un servidor falla a mitad de camino |
| Administrador | Ver el estado del clúster, auditar el total en circulación, confiar en que el sistema documenta sus propias fallas |
| Ingeniero de pruebas | Provocar fallas controladas (caída de nodo, retraso de red) para validar que la tolerancia a fallas funciona de verdad, no solo en el papel |
| Sistema externo (secundario) | No es una persona: la contraparte que confirma o rechaza una `TRANSFERENCIA_EXTERNA` (RF-25); en esta etapa es un *stub* simulado, no una integración real |

Ver el detalle de cada actor en [`../02-casos-de-uso/actores.md`](../02-casos-de-uso/actores.md).

## Reglas del negocio bancario (no de la infraestructura)

Las reglas que definen qué es "correcto" para el banco, independientemente de
cómo se implemente la réplica o el consenso, están en
[`reglas-de-negocio.md`](reglas-de-negocio.md). La distinción importa: una
regla de negocio (ej. "el saldo nunca es negativo") se prueba con datos; un
requisito no funcional de tolerancia a fallas (ej. RNF-03, failover en menos
de 2s) se prueba matando procesos. Ambos se necesitan, pero son pruebas de
naturaleza distinta — ver
[`../08-pruebas-y-despliegue/plan-de-pruebas.md`](../08-pruebas-y-despliegue/plan-de-pruebas.md).

## Alcance del negocio

| Dentro de alcance | Fuera de alcance |
|---|---|
| Cuentas en BRL, USD, PEN | Otras monedas o criptoactivos |
| Transferencias entre cuentas propias o de terceros | Préstamos, líneas de crédito, tarjetas |
| Conversión con tasa fija configurada en el sistema | Tasa de mercado en tiempo real (ver `docs/adr/ADR-0002-...md`) |
| Auditoría del total en circulación | Reportes fiscales o contables |
| Autenticación mínima para identificar al usuario dueño de una cuenta | Autenticación robusta, KYC, prevención de fraude |
| Cuenta de ahorro con interés periódico y depósito a plazo fijo (productos de depósito, tasa fija configurada por el sistema) | Fondos de inversión u otros productos con riesgo de mercado |
| Transferencias hacia sistemas externos interoperables, simuladas con un *stub* de latencia/fallas aleatorias | Integración real con una red interbancaria |
