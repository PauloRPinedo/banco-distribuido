# Diagramas PlantUML

Este archivo contiene los diagramas del modelo de datos y del flujo principal en
formato PlantUML. Cada bloque puede copiarse en:

- [PlantUML Web Server](https://www.plantuml.com/plantuml/uml/);
- [PlantText](https://www.planttext.com/);
- Visual Studio Code o Cursor con una extensión compatible con PlantUML;
- Visual Paradigm mediante importación o reproducción del modelo.

Para renderizar localmente se necesita Java y PlantUML:

```bash
plantuml archivo.puml
```

## 1. Diagrama entidad-relación

```plantuml
@startuml modelo_datos
title Banco distribuido - Modelo de datos persistentes

hide circle
skinparam linetype ortho
skinparam shadowing false
skinparam entity {
  BackgroundColor White
  BorderColor #2F5597
  HeaderBackgroundColor #D9EAF7
}

entity "USUARIO" as usuario {
  * id : UUID <<PK>>
  --
  * nombre : VARCHAR(120)
  * email : VARCHAR(255) <<UK>>
  * fecha_creacion : TIMESTAMP
}

entity "CUENTA" as cuenta {
  * id : VARCHAR(64) <<PK>>
  --
  * usuario_id : UUID <<FK>>
  * saldo_centavos : BIGINT
  * fecha_creacion : TIMESTAMP
  * estado : VARCHAR(20)
}

entity "OPERACION" as operacion {
  * id : UUID <<PK>>
  --
  * tipo : VARCHAR(25)
  cuenta_origen_id : VARCHAR(64) <<FK>>
  cuenta_destino_id : VARCHAR(64) <<FK>>
  * valor_centavos : BIGINT
  * fecha_hora : TIMESTAMP
  * estado : VARCHAR(20)
}

entity "SERVIDOR" as servidor {
  * id : VARCHAR(32) <<PK>>
  --
  * direccion : VARCHAR(255) <<UK>>
  * rol_actual : VARCHAR(20)
  * activo : BOOLEAN
  * ultima_actualizacion : TIMESTAMP
}

entity "REGISTRO_REPLICACION" as replicacion {
  * operacion_id : UUID <<PK, FK>>
  * servidor_id : VARCHAR(32) <<PK, FK>>
  --
  * fecha_confirmacion : TIMESTAMP
  * confirmada : BOOLEAN
}

usuario ||--o{ cuenta : posee
cuenta |o--o{ operacion : "cuenta origen"
cuenta |o--o{ operacion : "cuenta destino"
operacion ||--o{ replicacion : recibe
servidor ||--o{ replicacion : registra

note right of operacion
  CREACION:
    destino obligatorio
  DEPOSITO:
    destino obligatorio
  RETIRO:
    origen obligatorio
  TRANSFERENCIA:
    origen y destino obligatorios
end note

note bottom of cuenta
  saldo_centavos >= 0
  El dinero nunca usa FLOAT
end note

@enduml
```

## 2. Diagrama UML de clases persistentes

```plantuml
@startuml clases_persistencia
title Banco distribuido - Clases persistentes

skinparam classAttributeIconSize 0
skinparam shadowing false

class Usuario {
  +UUID id
  +String nombre
  +String email
  +DateTime fechaCreacion
}

class Cuenta {
  +String id
  +long saldoCentavos
  +DateTime fechaCreacion
  +EstadoCuenta estado
}

enum EstadoCuenta {
  ACTIVA
  BLOQUEADA
  CERRADA
}

class Operacion {
  +UUID id
  +TipoOperacion tipo
  +long valorCentavos
  +DateTime fechaHora
  +EstadoOperacion estado
}

enum TipoOperacion {
  CREACION
  DEPOSITO
  RETIRO
  TRANSFERENCIA
}

enum EstadoOperacion {
  PENDIENTE
  CONFIRMADA
  RECHAZADA
  CANCELADA
}

class Servidor {
  +String id
  +String direccion
  +RolServidor rolActual
  +boolean activo
  +DateTime ultimaActualizacion
}

enum RolServidor {
  PRIMARIO
  REPLICA
  CANDIDATO
}

class RegistroReplicacion {
  +UUID operacionId
  +String servidorId
  +DateTime fechaConfirmacion
  +boolean confirmada
}

Usuario "1" -- "0..*" Cuenta : posee
Cuenta "0..1" <-- "0..*" Operacion : origen
Cuenta "0..1" <-- "0..*" Operacion : destino
Operacion "1" -- "0..*" RegistroReplicacion
Servidor "1" -- "0..*" RegistroReplicacion
Cuenta --> EstadoCuenta
Operacion --> TipoOperacion
Operacion --> EstadoOperacion
Servidor --> RolServidor

@enduml
```

## 3. Diagrama de secuencia de una transferencia

```plantuml
@startuml secuencia_transferencia
title Banco distribuido - Confirmación de transferencia

actor Cliente
participant "Servidor primario" as Primario
database "Persistencia primaria" as DBP
participant "Servidor réplica" as Replica
database "Persistencia réplica" as DBR

Cliente -> Primario: transferir(op_id, origen, destino, valor)
activate Primario

Primario -> DBP: consultar operación por op_id

alt operación ya confirmada
  DBP --> Primario: resultado existente
  Primario --> Cliente: mismo resultado
else operación nueva
  Primario -> DBP: validar cuentas y saldo

  alt datos inválidos o saldo insuficiente
    Primario -> DBP: guardar estado RECHAZADA
    Primario --> Cliente: operación rechazada
  else operación válida
    Primario -> DBP: guardar operación PENDIENTE
    Primario -> Replica: replicar operación
    activate Replica
    Replica -> DBR: guardar operación
    DBR --> Replica: persistida
    Replica --> Primario: confirmación
    deactivate Replica

    Primario -> DBP: registrar confirmación
    Primario -> DBP: debitar origen y acreditar destino
    Primario -> DBP: cambiar estado a CONFIRMADA
    Primario --> Cliente: operación confirmada
  end
end

deactivate Primario
@enduml
```

## 4. Diagrama de componentes simplificado

```plantuml
@startuml componentes
title Banco distribuido - Componentes principales

skinparam componentStyle rectangle

actor Cliente

component "API / CLI" as API
component "Dominio bancario" as Dominio
component "Replicación" as Replicacion
component "Persistencia" as Persistencia
component "Elección de primario" as Eleccion

database "Datos persistentes\nUsuario, Cuenta,\nOperación, Servidor,\nRegistroReplicación" as Datos

Cliente --> API
API --> Dominio
Dominio --> Replicacion
Replicacion --> Persistencia
Persistencia --> Datos
Eleccion --> Replicacion

@enduml
```

## 5. Convenciones

| Símbolo | Significado |
|---|---|
| `PK` | Clave primaria |
| `FK` | Clave foránea |
| `UK` | Clave única |
| `1` / `||` | Exactamente uno |
| `0..1` / `o|` | Cero o uno |
| `0..*` / `o{` | Cero o muchos |

Los diagramas deben actualizarse junto con el modelo de datos en
[`entregables/05-modelo-de-datos/`](entregables/05-modelo-de-datos/) si cambia
alguna entidad, relación o regla de negocio.
