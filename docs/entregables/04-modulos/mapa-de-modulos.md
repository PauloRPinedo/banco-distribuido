# Mapa de módulos

Basado en la estructura que tenía `prototipo-1/banco/` **cuando se entregó la
etapa 1** (4 paquetes: `dominio`, `persistencia`, `cluster`, `interface`),
adaptada a la nueva pila (PostgreSQL + FastAPI + frontend separado).

> `prototipo-1/` ya no tiene esa estructura: fue reconstruido sobre esta misma
> pila y hoy usa `dominio`, `repositorio`, `servico`, `api` — es decir, la de la
> columna izquierda de abajo, sin `cluster`, sin `integraciones` y sin
> `autenticacion`. Ver `docs/SPECS.md` 11.8. La columna "paquete origen" se lee
> como historia, no como el estado de esa carpeta hoy.

| Módulo | Paquete origen (Prototipo 1) | Responsabilidad | Cambia con el nuevo stack |
|---|---|---|---|
| `dominio` | `banco/dominio/` | Dinero en centavos, cuentas, operaciones, invariantes, conversión de moneda, interés y bloqueo de plazo fijo | Se agrega la lógica de conversión, multi-cuenta, interés (RF-23/RF-24) y RN-12; sigue sin importar red ni base de datos |
| `repositorio` | `banco/persistencia/` | Guardar y leer cuentas/operaciones | Pasa de WAL en archivo JSONL a tablas PostgreSQL — ver [`../05-modelo-de-datos/modelo-fisico.md`](../05-modelo-de-datos/modelo-fisico.md) |
| `cluster` | `banco/cluster/` | Locks por cuenta, replicación, quórum, elección, fencing por epoch, *tick* periódico (heartbeat + revisión de interés) | Se mantiene como responsabilidad del equipo (no delegada a Postgres) — ver `docs/adr/ADR-0001-...md` |
| `integraciones` | — (no existía) | Adaptador hacia sistemas externos para `TRANSFERENCIA_EXTERNA` (RF-25) | Nuevo — en esta etapa es un *stub* simulado (latencia y fallas aleatorias), no un cliente real |
| `autenticacion` | — (no existía) | Hash de contraseña y firma/verificación de token de sesión con llave simétrica (RF-26) | Nuevo — no depende de `cluster` ni `repositorio` de operaciones, solo de `RepositorioUsuarios` |
| `api` | `banco/interface/` (servidor HTTP) | Rutas HTTP, validación de forma, traducción de errores | Pasa de `http.server` a FastAPI |
| `cli` | `banco/cli.py` | Cliente de línea de comandos | **No se mantiene.** Ni esta etapa ni el Prototipo 1 reconstruido tienen CLI, así que F-12 y RF-17 quedan sin cubrir — ver `docs/SPECS.md` 11.8 |
| `frontend` | — (no existía) | Interfaz web para cliente y administrador | Nuevo — ver [`../02-casos-de-uso/`](../02-casos-de-uso/) |
| `balanceador` | — (no existía) | Enruta cada pedido al primario vigente (o a cualquier nodo si es lectura); sigue `409 nao_sou_primario` | Nuevo — servicio propio y separado, sin estado propio, no forma parte de ningún nodo (ver [`../03-arquitectura/diagrama-de-componentes.md`](../03-arquitectura/diagrama-de-componentes.md)) |

## Qué no cambia

`dominio` sigue siendo el módulo más importante de proteger: es el único que
puede probarse sin levantar un clúster ni una base de datos, y es donde vive
la invariante del dinero (RN-01, RN-02). Cualquier cambio de stack que
obligue a `dominio` a importar Postgres o HTTP directamente es una señal de
diseño incorrecto, no una simplificación válida.

Ver la relación módulo × requisito en
[`matriz-modulo-requisito.md`](matriz-modulo-requisito.md) y la relación de
dependencias entre módulos en [`diagrama-de-paquetes.md`](diagrama-de-paquetes.md).
