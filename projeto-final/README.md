# Projeto final

Tercera etapa del [Banco Distribuido](../README.md) — pila expandida
(Postgres, balanceador propio, frontend en React, autenticación, Docker y
CI/CD) decidida en `docs/adr/ADR-0002` y `docs/entregables/`, más las
subfases de `docs/ROADMAP.md` §"Etapa 3" (inyección de fallas, métricas,
*benchmark*).

`prototipo-2/` se mantiene vacía y tal como está en el ROADMAP (Python puro,
sin Postgres ni frontend) — esta etapa no la reemplaza, la reutiliza cuando
su protocolo de replicación esté listo (ver más abajo).

## Qué hay aquí

| Carpeta | Qué es |
|---|---|
| `backend/` | Un nodo (FastAPI + Postgres, en instancias separadas en real) — dominio, repositorio, integraciones, autenticación, servicio, api |
| `balanceador/` | Encuentra al primario y reenvía — sin estado propio, por eso va en **AWS Lambda** en real (`Dockerfile.lambda` + `Mangum`), no en una instancia — ver `docs/adr/ADR-0002-...md` |
| `frontend/` | React + Vite, sirve las pantallas de `docs/entregables/02-casos-de-uso/` — en real va en **Vercel**, no en una instancia |
| `db/schema.sql` | El DDL de `docs/entregables/05-modelo-de-datos/modelo-fisico.md`, listo para cargar |
| `config/cluster.exemplo.json` | Lista de nodos — la usan tanto el backend como el balanceador |
| `GUIA-DESPLIEGUE.md` | Servicios, comandos, despliegue manual y CI/CD |
| `GUIA-REPLICA-POSTGRESQL.md` | Por qué la réplica la hace la app, no Postgres |

## Cómo correrlo

```bash
cd projeto-final
cp config/cluster.exemplo.json config/cluster.json
SECRET_KEY=$(openssl rand -hex 32) docker compose up --build
```

Ver [`GUIA-DESPLIEGUE.md`](GUIA-DESPLIEGUE.md) para el resto (despliegue
real y CI/CD).

## Qué funciona hoy y qué falta — honesto, no omitido

Probado de punta a punta con `docker compose up` (registro, login,
crear cuenta, depositar, extracto, auditoría, todo a través del
balanceador):

- [x] `dominio/` (copiado de Prototipo 1) — RF-01 a RF-08
- [x] Persistencia real en Postgres (`repositorio/`) para cuenta corriente
- [x] Balanceador — encuentra al primario, sigue `409`; probado también como
      función Lambda (evento de Function URL simulado, `Mangum` responde 200)
- [x] Autenticación (RF-26) — hash de contraseña, token con llave simétrica,
      validado sin llamada de red entre nodos
- [x] Frontend React (login + consulta de saldo) hablando con el
      balanceador
- [x] Docker + `docker-compose.yml` para las 4 piezas en local
- [x] Pipeline de CI/CD (pruebas + build + publicación en ghcr.io/ECR;
      despliegue real pendiente de los secretos de AWS/SSH/Vercel)

**Pendiente** (ver `TODO`/`PENDIENTE.md` en el código, y `docs/ROADMAP.md`
§3.0 y §3.1 en adelante):

- [ ] Replicación real entre nodos (`banco/cluster/nodo.py` es un *stub*:
      todo nodo se comporta como primario porque no hay con quién competir
      el rol) — **hoy, si matas el proceso de un nodo, los datos que solo
      él tenía se pierden**; las 2-3 bases no quedan sincronizadas todavía
- [ ] Multi-moneda, conversión, ahorro/plazo fijo, transferencia externa
      (RF-19 a RF-25) — `banco/dominio/PENDIENTE.md`
- [ ] Inyección de fallas, métricas, panel web, *benchmark* (`docs/ROADMAP.md`
      3.1 a 3.4)
