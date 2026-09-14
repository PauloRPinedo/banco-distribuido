# Diagrama de secuencia — elección y failover

Comportamiento del clúster, no de una pantalla — es lo que sostiene a
[`../02-casos-de-uso/cu-09-continuar-con-primario-caido.md`](../02-casos-de-uso/cu-09-continuar-con-primario-caido.md)
por debajo. Sigue el protocolo descrito en `docs/SPECS.md` §8.

## Descripción

Muestra la secuencia completa desde que el primario deja de enviar
*heartbeat* hasta que un nuevo primario queda operando: detección por
*timeout*, postulación con `epoch` incrementado, voto de las réplicas según
las tres condiciones de `SPECS.md` §8.2, y el *heartbeat* inmediato al
asumir.

```mermaid
sequenceDiagram
    participant A as Nodo A (primario)
    participant B as Nodo B (réplica)
    participant C as Nodo C (réplica)

    Note over A,C: Primario A deja de responder (caído o aislado)
    B->>B: pasa timeout_eleccion sin heartbeat de A
    B->>B: incrementa epoch, se postula como candidato
    B->>C: POST /interno/votar (epoch, id=B, ultimo_indice, ultimo_epoch)
    C->>C: evalua las 3 condiciones (epoch >= el suyo, no voto este epoch, log al menos tan actualizado)
    C-->>B: voto concedido
    Note over B: mayoria alcanzada (2 de 3, contandose a si mismo)
    B->>B: se asume PRIMARIO en el nuevo epoch
    B->>C: heartbeat inmediato (nuevo epoch)
    B->>B: registra entrada noop en su propio epoch
    Note over A: A vuelve a estar disponible
    A->>C: heartbeat con epoch antiguo
    C-->>A: rechazado, epoch menor
    A->>A: se despromueve a REPLICA
```

## Por qué la entrada `noop`

El nuevo primario B registra una operación `noop` en su propio `epoch` antes
de aceptar escrituras de clientes. Una entrada heredada del primario anterior
—aunque esté en la mayoría de los nodos— no puede confirmarse solo por conteo
de réplicas hasta que el `epoch` actual tenga al menos una entrada propia
confirmada; confirmar la `noop` primero arrastra a todo lo anterior de forma
segura. El razonamiento completo está en `docs/SPECS.md` §8.4.

Ver el ciclo de vida del rol de un nodo en
[`diagrama-de-estados-nodo.md`](diagrama-de-estados-nodo.md).
