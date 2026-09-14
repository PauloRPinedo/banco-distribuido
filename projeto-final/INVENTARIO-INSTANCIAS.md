# Inventario de instancias desplegadas

Estado real de lo que hay corriendo en AWS — complementa (no repite) a
[`GUIA-DESPLIEGUE.md`](GUIA-DESPLIEGUE.md), que es el "cómo se hace" genérico
y reutilizable; este archivo es la "foto" de lo que existe hoy, y hay que
actualizarlo a mano cada vez que algo cambie (una instancia nueva, una
reiniciada, una terminada).

**Región:** `us-east-2` (Ohio)

## Decisión actual: 2 nodos, no 3 — por la cuota de vCPU de la cuenta

Mientras se aprueba el aumento de cuota de AWS (`Running On-Demand Standard
... instances`, ver `GUIA-DESPLIEGUE.md`), se trabaja con **2 nodos** (A y
B) en vez de los 3 que pide el diseño. Esto es una decisión consciente y
temporal, no el objetivo final — significa que, por ahora, el sistema
**no tolera ninguna caída sin perder disponibilidad de escritura** (con 2
nodos la mayoría es 2; perder cualquiera de los dos deja al otro sin
mayoría). El nodo C se agrega en cuanto AWS apruebe la cuota — ver el
Paso 1 de `GUIA-DESPLIEGUE.md` para relanzarlo en `us-east-2c`.

## Instancias

| Name | ID de instancia | Rol | Zona (AZ) | Tipo | IP pública | IP privada | Estado (al anotar) |
|---|---|---|---|---|---|---|---|
| `postgres-a` | `i-0794aefb11a9a02cb` | Postgres del nodo A | `us-east-2a` | `t3.micro` | `3.148.185.193` | `172.31.12.43` | En ejecución |
| `backend-a` | `i-0e051a5823e5833e3` | Backend del nodo A | `us-east-2a` | `t3.micro` | `3.129.73.132` | `172.31.12.211` | En ejecución |
| `postgres-b` | `i-0845c11b376c3b824` | Postgres del nodo B | `us-east-2b` | `t3.micro` | `3.16.21.151` | `172.31.28.108` | En ejecución |
| `backend-b` | `i-0829dbdfa5e7fb697` | Backend del nodo B | `us-east-2b` | `t3.micro` | `3.142.185.122` | `172.31.29.55` | Inicializando |

**Pendiente:** `postgres-c` / `backend-c` en `us-east-2c`, cuando se apruebe
la cuota de vCPU.

## Seguridad — qué NO va en este archivo

A propósito, esta tabla no incluye contraseñas de Postgres, `SECRET_KEY`, ni
ningún secreto — son datos que no deben quedar en un archivo versionado en
git (`INVENTARIO-INSTANCIAS.md` sí se sube al repositorio, a diferencia de
`config/cluster.json`, que está en `.gitignore`). Guárdalos aparte (un
gestor de contraseñas, o variables de entorno locales), no aquí.

## Direcciones para copiar a `config/cluster.json` / `CLUSTER_CONFIG_JSON`

```json
{
  "nos": [
    {"id": "A", "endereco": "172.31.12.211", "porta": 8001},
    {"id": "B", "endereco": "172.31.29.55", "porta": 8001}
  ]
}
```

(IP **privada** de cada `backend-X` — para el balanceador en Lambda, usar
en su lugar las IPs **públicas** de la tabla de arriba, ver
`GUIA-DESPLIEGUE.md` Paso 4.5)

## Nota sobre las IPs públicas

Cambian cada vez que se detiene y se vuelve a iniciar una instancia (salvo
que se reserve una IP elástica, que si no está asociada a una instancia
corriendo, cobra). Antes de cada sesión de prueba, vuelve a esta tabla y
actualízala con `aws ec2 describe-instances` o desde la consola — si el
balanceador o `cluster.json` quedan con una IP vieja, vas a ver errores de
conexión que parecen del protocolo pero son solo una IP desactualizada.
