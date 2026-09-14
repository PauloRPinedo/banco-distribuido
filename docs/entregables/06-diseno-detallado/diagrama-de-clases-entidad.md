# Diagrama de clases — entidad

Representa el modelo de dominio (capa `dominio`, ver
[`../04-modulos/mapa-de-modulos.md`](../04-modulos/mapa-de-modulos.md)). Es la
traducción a clases del modelo lógico de
[`../05-modelo-de-datos/modelo-logico.md`](../05-modelo-de-datos/modelo-logico.md).

```mermaid
classDiagram
    class Usuario {
        +UUID id
        +String nombre
        +String email
        +String passwordHash
        +DateTime fechaCreacion
    }

    class Cuenta {
        +String id
        +String usuarioId
        +Moneda moneda
        +long saldoCentavos
        +DateTime fechaCreacion
        +EstadoCuenta estado
        +TipoProducto tipoProducto
        +BigDecimal tasaInteres
        +DateTime fechaUltimoInteres
        +DateTime fechaVencimiento
        +debitar(montoCentavos)
        +acreditar(montoCentavos)
        +admiteSalida(fechaActual) boolean
    }

    class Operacion {
        +UUID id
        +TipoOperacion tipo
        +String cuentaOrigenId
        +String cuentaDestinoId
        +long valorCentavos
        +Moneda monedaOrigen
        +Moneda monedaDestino
        +BigDecimal tasaAplicada
        +long valorDestinoCentavos
        +String sistemaExternoId
        +String referenciaExterna
        +DateTime fechaHora
        +EstadoOperacion estado
    }

    class TasaCambio {
        +Moneda monedaOrigen
        +Moneda monedaDestino
        +BigDecimal valor
        +DateTime vigenteDesde
        +convertir(montoCentavos) long
    }

    class SistemaExterno {
        +String id
        +String nombre
        +String codigo
        +boolean activo
    }

    class Moneda {
        <<enumeration>>
        BRL
        USD
        PEN
    }
    class EstadoCuenta {
        <<enumeration>>
        ACTIVA
        BLOQUEADA
        CERRADA
    }
    class TipoProducto {
        <<enumeration>>
        CORRIENTE
        AHORRO
        PLAZO_FIJO
    }
    class TipoOperacion {
        <<enumeration>>
        CREACION
        DEPOSITO
        RETIRO
        TRANSFERENCIA
        CAMBIO
        INTERES
        TRANSFERENCIA_EXTERNA
    }
    class EstadoOperacion {
        <<enumeration>>
        PENDIENTE
        CONFIRMADA
        RECHAZADA
        CANCELADA
    }

    Usuario "1" --> "0..*" Cuenta : posee
    Cuenta "0..1" <-- "0..*" Operacion : origen
    Cuenta "0..1" <-- "0..*" Operacion : destino
    Operacion ..> TasaCambio : usa (si tipo = CAMBIO)
    Operacion ..> SistemaExterno : envia a (si tipo = TRANSFERENCIA_EXTERNA)
    Cuenta --> Moneda
    Cuenta --> EstadoCuenta
    Cuenta --> TipoProducto
    Operacion --> TipoOperacion
    Operacion --> EstadoOperacion
```

Estas clases no tienen métodos de red ni de acceso a Postgres — esas
responsabilidades están en las capas de interfaz y servicio (ver
[`diagrama-de-clases-interfaz.md`](diagrama-de-clases-interfaz.md) y
[`diagrama-de-clases-servicio.md`](diagrama-de-clases-servicio.md)), siguiendo
la misma separación que ya tenía `dominio/` en Prototipo 1.

No hay clases `Servidor` ni `RegistroReplicacion` aquí: representan el
mecanismo de replicación del clúster, no el dominio bancario — ver el porqué
en la última sección de
[`../05-modelo-de-datos/modelo-conceptual-er.md`](../05-modelo-de-datos/modelo-conceptual-er.md).
`SistemaExterno` sí es una clase de dominio, aunque también sea "externa" al
clúster: el negocio necesita saber a quién se le envió cada transferencia,
igual que necesita `TasaCambio`.
