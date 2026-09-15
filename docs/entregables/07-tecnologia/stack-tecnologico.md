# Stack tecnológico

Resume las decisiones ya tomadas en
[`../../docs/adr/ADR-0002-stack-tecnologico-e-implantacao.md`](../../docs/adr/ADR-0002-stack-tecnologico-e-implantacao.md)
y [`ADR-0003-linha-grafica.md`](../../docs/adr/ADR-0003-linha-grafica.md). Ver
esos documentos para el porqué de cada elección — aquí solo la tabla
resumen y lo que sigue pendiente.

| Capa | Tecnología | Estado |
|---|---|---|
| Frontend — línea gráfica | Paleta y componentes inspirados en Nubank (morado `#820AD1`, tarjetas blancas, tipografía Inter) | Decidido |
| Frontend — framework | React (Vite) | Decidido |
| Frontend — hosting | **Vercel** — sin instancia propia, es estático | Decidido |
| Backend — lenguaje | Python | Decidido |
| Backend — framework | FastAPI | Decidido |
| Backend — hosting | EC2/Oracle Cloud, en contenedor Docker, en instancia **separada** de la base de datos de cada nodo | Decidido — ver ADR-0002 |
| Base de datos | PostgreSQL, una instancia por nodo, sin réplica nativa del motor | Decidido |
| Base de datos — hosting | Contenedor Docker en su propia instancia, separada del backend, sin RDS ni servicio gestionado | Decidido |
| Replicación entre nodos | Protocolo propio (log + quórum + elección), sobre HTTP | Decidido — es el núcleo evaluado por el curso |
| Balanceador | Servicio propio, sin estado, escrito por el equipo (no un balanceador gestionado tipo ALB) — enruta al primario vigente, sigue `409 primario_provavel` | Decidido |
| Balanceador — hosting | **AWS Lambda** (Function URL) — sin instancia propia, no tiene estado ni necesita estar siempre encendido | Decidido — ver ADR-0002 |
| Autenticación (RF-26) | Contraseña con `PBKDF2-HMAC-SHA256` (hash, nunca reversible); token de sesión firmado con `HMAC-SHA256` y una llave simétrica compartida por todos los nodos | Decidido — sin dependencia nueva, `hashlib`/`hmac` son de la librería estándar |
| Pasarela externa (RF-25) | *Stub* simulado en el propio backend (latencia y fallas aleatorias), sin integración real con un tercero | Decidido para esta etapa — ver [`../02-casos-de-uso/cu-16-transferir-sistema-externo.md`](../02-casos-de-uso/cu-16-transferir-sistema-externo.md) |
| Empaquetado | Docker (backend, y balanceador con una imagen aparte para Lambda); `docker-compose.yml` para levantar todo en local | Decidido |
| Integración/despliegue continuo | GitHub Actions: pruebas + build de imágenes en cada `push` a `main`; despliegue por SSH a los nodos, `aws lambda update-function-code` para el balanceador, Vercel despliega el frontend por su cuenta | Decidido — ver `GUIA-DESPLIEGUE.md` en `projeto-final/` |
| Comunicación cliente↔backend | HTTPS + JSON | Decidido |
| Pruebas | `unittest` de la biblioteca estándar | Decidido — `pytest` sería un `pip install` más en cada laptop, y quien lo tenga instalado corre estos archivos sin cambiarlos |
| Control de versiones | Git / GitHub (ya en uso) | Decidido |

## Lo que cambia respecto a Prototipo 1

| Prototipo 1 | Ahora |
|---|---|
| `http.server` de la biblioteca estándar | FastAPI (recomendado) |
| WAL en archivo JSONL | Tablas PostgreSQL (ver [`../05-modelo-de-datos/modelo-fisico.md`](../05-modelo-de-datos/modelo-fisico.md)) |
| Sin frontend, solo CLI | Frontend web, y **ningún CLI**: F-12 y RF-17 quedan sin cubrir (`docs/SPECS.md` 11.8) |
| Sin dependencias externas (`CONVENCOES.md`) | Se abandona esa regla a partir de esta etapa — ver la consecuencia anotada en `ADR-0002-...md` |

## Pendiente de decisión

Ver la lista completa en la sección final de
[`../../docs/adr/ADR-0002-stack-tecnologico-e-implantacao.md`](../../docs/adr/ADR-0002-stack-tecnologico-e-implantacao.md).
