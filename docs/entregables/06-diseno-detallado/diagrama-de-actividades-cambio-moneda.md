# Diagrama de actividades — conversión de moneda (vista técnica)

El diagrama de actividades **orientado al usuario** ya está en
[`../02-casos-de-uso/cu-05-transferir-con-conversion.md`](../02-casos-de-uso/cu-05-transferir-con-conversion.md#diagrama-de-actividades).
Este es el mismo flujo, pero desde el punto de vista de las clases de
servicio y repositorio (ver
[`diagrama-de-clases-servicio.md`](diagrama-de-clases-servicio.md)) — útil
para quien va a implementar `ServicioTransferencias.transferirConConversion`.

## Descripción

Detalla qué llamadas concretas hace el servicio al repositorio en cada paso,
en vez de hablar en términos de "el sistema valida" como en la versión de
negocio.

```mermaid
flowchart TD
    A["ServicioTransferencias.transferirConConversion(origen, destino, monto, opId)"] --> B["RepositorioOperaciones.buscarPorOpId(opId)"]
    B --> C{"Ya existe esa operacion?"}
    C -- si --> D["Devolver el resultado guardado (idempotencia, RN-08)"]
    C -- no --> E["RepositorioCuentas.buscarPorId(origen) y (destino)"]
    E --> F{"Saldo de origen alcanza?"}
    F -- no --> Z1["Marcar RECHAZADA, no llamar a Replicacion"]
    F -- si --> G["RepositorioTasaCambio.tasaVigente(monedaOrigen, monedaDestino)"]
    G --> H{"Tasa existe?"}
    H -- no --> Z2["Marcar RECHAZADA: tasa no disponible"]
    H -- si --> I["Calcular valorDestinoCentavos = monto * tasa"]
    I --> J["RepositorioOperaciones.guardar(operacion PENDIENTE, tasa incluida)"]
    J --> K["ServicioReplicacion.esperarMayoria(operacion)"]
    K --> L{"Mayoria confirmo?"}
    L -- no --> Z3["Dejar PENDIENTE, responder sin_quorum"]
    L -- si --> M["Cuenta.debitar(origen), Cuenta.acreditar(destino)"]
    M --> N["Marcar CONFIRMADA"]
```

## Nota de implementación

El cálculo `valorDestinoCentavos = monto * tasa` debe hacerse con aritmética
de enteros/decimales exactos (`BigDecimal`/`NUMERIC`, nunca `float`) — mismo
principio de `docs/SPECS.md` §3.1, ahora aplicado también a la conversión, no
solo a la representación del dinero en una sola moneda.
