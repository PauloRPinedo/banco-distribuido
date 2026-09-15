# Guía de despliegue

Cubre los 4 servicios de `projeto-final/`, cómo levantarlos en local, cómo
desplegarlos "en real" **desde la consola web de AWS** (sin CLI), y el
pipeline de CI/CD. Complementa (no repite)
[`docs/entregables/08-pruebas-y-despliegue/plan-de-despliegue.md`](../docs/entregables/08-pruebas-y-despliegue/plan-de-despliegue.md).

Región: **`us-east-2` (Ohio)** — confírmala arriba a la derecha de la
consola antes de crear nada; si creas algo en otra región no se ven entre sí.

**Aviso honesto:** casi todo el despliegue se hace a clics. Hay exactamente
**2 momentos** donde eso no alcanza — porque ninguna consola de AWS tiene un
botón para "correr este contenedor de Docker" ni para "construir esta
imagen": levantar los contenedores dentro de cada instancia (Paso 2 y 3), y
construir/subir la imagen del balanceador a ECR (Paso 4). Para esos dos uso
el botón **"Connect"** de la propia consola de EC2 — abre una terminal
**dentro del navegador**, sin instalar nada — y **CloudShell** (otro botón
de la consola, arriba a la derecha) para el build de la imagen. Ambos son
parte del portal, no una herramienta aparte; te aviso exactamente cuándo
tocan.

## Los servicios

| Servicio | Qué hace | En local (`docker compose`) | En real |
|---|---|---|---|
| `backend-a` / `backend-b` / `backend-c` | Backend FastAPI de cada nodo | Contenedor, puerto 8001 | Instancia EC2 propia por nodo |
| `postgres-a` / `postgres-b` / `postgres-c` | Almacenamiento local de cada nodo — sin réplica nativa, ver [`GUIA-REPLICA-POSTGRESQL.md`](GUIA-REPLICA-POSTGRESQL.md) | Contenedor, puerto 5432 | Instancia EC2 propia por nodo, **separada** de su backend |
| `balanceador` | Encuentra al primario, reenvía, sigue `409` | Contenedor, puerto 8000 | **AWS Lambda** (Function URL) — no es una instancia |
| `frontend` | React compilado | Contenedor Nginx, puerto 8080 | **Vercel** — no es una instancia |

**6 instancias EC2** en total (3 backend + 3 Postgres) — por qué
balanceador/frontend no cuentan como instancia, ver `docs/adr/ADR-0002-...md`.

## Local, con un solo comando

```bash
cd projeto-final
cp config/cluster.exemplo.json config/cluster.json
SECRET_KEY=$(openssl rand -hex 32) docker compose up --build
```

Frontend en `http://localhost:8080`. Apagar todo: `docker compose down -v`.

---

## Despliegue real, por consola web

### Paso 0 — Llave SSH y *security groups*

**0.1 — Crear la llave** (para poder conectarte a las instancias):
Consola → busca **"EC2"** → menú izquierdo, sección **Network & Security**
→ **Key Pairs** → botón **Create key pair**.
- Name: `banco-key`
- Key pair type: `RSA`
- Private key file format: `.pem`
- **Create key pair** → se descarga `banco-key.pem` sola — guárdala, la
  necesitas más adelante para el botón "Connect".

**0.2 — Grupo de seguridad para los backends**: menú izquierdo → **Security
Groups** → **Create security group**.
- Security group name: `banco-backend`
- Description: `Backend API`
- VPC: la que aparece por defecto (no toques esto)
- **Inbound rules** → **Add rule** (dos veces):
  1. Type: `SSH` — Source: `My IP` (así solo tú te conectas por SSH)
  2. Type: `SSH` — Source: `Custom` → `3.16.146.0/29` (el rango del propio
     servicio **EC2 Instance Connect** en `us-east-2` — es quien de verdad
     origina la conexión cuando usas el botón "Connect → En el navegador
     web"; sin esta regla ese botón no funciona, aunque `My IP` ya esté
     puesta. AWS te muestra este mismo rango si te falta, en un aviso
     amarillo al conectar)
  2. Type: `Custom TCP` — Port range: `8001` — Source: `Anywhere-IPv4`
     (`0.0.0.0/0`)

  *Por qué 8001 abierto a todo internet, a propósito:* Lambda (el
  balanceador) no vive dentro de tu red privada, así que necesita poder
  llegarle a la API de cada nodo desde afuera. Es una simplificación
  consciente para el curso — el detalle está en
  `docs/entregables/08-pruebas-y-despliegue/plan-de-despliegue.md`.

  **Pendiente de hardening (siguiente paso, no bloquea el despliegue de
  hoy):** las rutas de dinero ya exigen sesión (`banco/api/seguridad.py`,
  RF-26) — eso cubre el riesgo de que alguien mueva dinero sin token. Lo
  que sigue abierto es la exposición de **red**: conectar la función Lambda
  a esta misma VPC permitiría reemplazar `0.0.0.0/0` en el puerto 8001 por
  el *security group* del balanceador únicamente, igual que ya se hizo con
  Postgres. No es necesario para que el curso funcione — es la siguiente
  mejora si se quiere cerrar también la exposición de red, no solo la de
  aplicación.
- **Create security group**.

**0.3 — Grupo de seguridad para Postgres**: mismo botón **Create security
group** otra vez.
- Security group name: `banco-postgres`
- Description: `Postgres`
- **Inbound rules**:
  1. Type: `SSH` — Source: `My IP`
  2. Type: `SSH` — Source: `Custom` → `3.16.146.0/29` (rango de EC2 Instance
     Connect en `us-east-2` — necesario para el botón "Connect → En el
     navegador web", igual que en `banco-backend`)
  3. Type: `PostgreSQL` (ya trae el puerto 5432 solo) — Source: escribe
     `banco-backend` en el cuadro y **selecciona el grupo** de la lista que
     aparece (no una IP) — así **solo** los backends alcanzan Postgres,
     nunca internet.
- **Create security group**.

### Paso 1 — Lanzar las 6 instancias, una por zona de disponibilidad

**Por qué esto importa:** si los 3 nodos caen en la misma zona de
disponibilidad (AZ) y esa zona falla completa (pasa, aunque no es común),
pierdes los 3 a la vez — de nada sirve el protocolo de mayoría si las 3
copias están enchufadas al mismo lugar físico. La corrección: **cada nodo
(su backend + su Postgres, juntos) en una AZ distinta** — no región
distinta, eso sí generaría otro problema (ver la nota al final). `us-east-2`
tiene 3 zonas: asigna así:

| Nodo | Zona (AZ) |
|---|---|
| A (`postgres-a` + `backend-a`) | `us-east-2a` |
| B (`postgres-b` + `backend-b`) | `us-east-2b` |
| C (`postgres-c` + `backend-c`) | `us-east-2c` |

Repite este asistente **6 veces** (cambia el nombre, la subred/AZ y el
*security group* cada vez, según a qué nodo pertenece). Consola de EC2 →
**Instances** → **Launch instance**.

1. **Name**: `postgres-a` (luego `postgres-b`, `postgres-c`, `backend-a`,
   `backend-b`, `backend-c`)
2. **Application and OS Images**: `Amazon Linux 2023` (aparece primero,
   marcada "Free tier eligible")
3. **Instance type**: `t3.micro` (marcada "Free tier eligible")
4. **Key pair**: `banco-key`
5. **Network settings** → **Edit**:
   - VPC: la de por defecto
   - **Subnet**: elige explícitamente la subred de la AZ que le toca a ese
     nodo según la tabla de arriba (el desplegable muestra el nombre de la
     zona, ej. "us-east-2a") — **no** dejes "No preference"; las dos
     instancias del mismo nodo (`postgres-X` y `backend-X`) van en la
     **misma** AZ entre sí (para que su propia latencia sea mínima), pero
     distinta a la de los otros dos nodos
   - Auto-assign public IP: `Enable`
   - Firewall (security groups): `Select existing security group` →
     `banco-postgres` (para las 3 `postgres-X`) o `banco-backend` (para las
     3 `backend-X`)
6. **Advanced details** → baja hasta **User data**, pega exactamente esto
   (igual en las 6, instala Docker):
   ```bash
   #!/bin/bash
   dnf install -y docker
   systemctl enable --now docker
   usermod -aG docker ec2-user
   ```
7. **Launch instance**.

Cuando las 6 estén "Running" (~1 minuto), en la lista de **Instances**
haz clic en el ícono de engranaje ⚙️ (arriba a la derecha de la tabla) y
activa las columnas **Private IPv4 addresses** y **Public IPv4 address** si
no las ves. Anota las 6 en una tabla propia — las vas a usar todo el resto
de la guía.

**No mezcles las direcciones:**

| Para qué | Qué dirección usar |
|---|---|
| Un backend hablándole a **su propio** Postgres | IP **privada** de `postgres-X` |
| Los 3 backends entre sí (cuando exista el protocolo real) | IP **privada** de `backend-X` |
| El balanceador (Lambda) hablándole a los backends | IP **pública** de `backend-X` |

(las IPs privadas de instancias en distintas AZ de la misma VPC se alcanzan
entre sí sin configuración extra — una VPC ya abarca todas las zonas de la
región; no cambia nada de lo de arriba por haber repartido los nodos)

**Por qué no repartir en regiones distintas en vez de AZ:** el protocolo
tiene temporizadores finos (*heartbeat* cada 150ms, *timeout* de elección de
800-1500ms). Entre zonas de una misma región la latencia es de <1-2ms — no
lo nota el protocolo. Entre regiones distintas (ej. Ohio↔California) puede
ser de 50-100ms, suficiente para que el sistema confunda "el otro nodo está
lejos" con "el otro nodo se cayó" y dispare elecciones todo el tiempo — se
cambiaría un problema real (falla de una zona) por uno peor (el clúster
nunca converge). Multi-AZ es el nivel correcto de resiliencia para este
proyecto; multi-región no.

### Paso 2 — Levantar Postgres (terminal en el navegador, sin instalar nada)

Por cada una de las 3 instancias `postgres-X`: en la lista de **Instances**,
selecciónala → botón **Connect** (arriba) → pestaña **EC2 Instance
Connect** → **Connect**. Se abre una terminal en una pestaña nueva,
**dentro de tu navegador** — no necesitas PuTTY ni la llave `.pem` para esto.

Ahí adentro, pega el contenido completo de
[`projeto-final/db/schema.sql`](db/schema.sql) así (ábrelo en tu editor,
copia todo, y pégalo entre las líneas `EOF`):

```bash
cat > schema.sql <<'EOF'
-- Igual en los 2-3 nodos — copiado de
-- docs/entregables/05-modelo-de-datos/modelo-fisico.md. Cada nodo corre su
-- propia instancia; no se comparte una base de datos entre nodos (ver
-- GUIA-REPLICA-POSTGRESQL.md).

CREATE TABLE usuario (
    id              UUID PRIMARY KEY,
    nombre          VARCHAR(120) NOT NULL,
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    fecha_creacion  TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE cuenta (
    id                     VARCHAR(64) PRIMARY KEY,
    usuario_id             UUID NOT NULL REFERENCES usuario(id),
    moneda                 VARCHAR(3) NOT NULL CHECK (moneda IN ('BRL','USD','PEN')),
    saldo_centavos         BIGINT NOT NULL DEFAULT 0 CHECK (saldo_centavos >= 0),
    fecha_creacion         TIMESTAMP NOT NULL DEFAULT now(),
    estado                 VARCHAR(20) NOT NULL DEFAULT 'ACTIVA'
                           CHECK (estado IN ('ACTIVA','BLOQUEADA','CERRADA')),
    tipo_producto          VARCHAR(20) NOT NULL DEFAULT 'CORRIENTE'
                           CHECK (tipo_producto IN ('CORRIENTE','AHORRO','PLAZO_FIJO')),
    tasa_interes           NUMERIC(9,6) CHECK (tasa_interes IS NULL OR tasa_interes > 0),
    fecha_ultimo_interes   TIMESTAMP,
    fecha_vencimiento      TIMESTAMP,
    CONSTRAINT chk_producto_completo CHECK (
        (tipo_producto = 'CORRIENTE'
            AND tasa_interes IS NULL AND fecha_ultimo_interes IS NULL AND fecha_vencimiento IS NULL)
        OR (tipo_producto = 'AHORRO'
            AND tasa_interes IS NOT NULL AND fecha_ultimo_interes IS NOT NULL AND fecha_vencimiento IS NULL)
        OR (tipo_producto = 'PLAZO_FIJO'
            AND tasa_interes IS NOT NULL AND fecha_ultimo_interes IS NULL
            AND fecha_vencimiento IS NOT NULL AND fecha_vencimiento > fecha_creacion)
    )
);
CREATE INDEX idx_cuenta_usuario ON cuenta(usuario_id);

CREATE TABLE tasa_cambio (
    moneda_origen   VARCHAR(3) NOT NULL,
    moneda_destino  VARCHAR(3) NOT NULL,
    valor           NUMERIC(18,8) NOT NULL CHECK (valor > 0),
    vigente_desde   TIMESTAMP NOT NULL DEFAULT now(),
    PRIMARY KEY (moneda_origen, moneda_destino, vigente_desde),
    CHECK (moneda_origen <> moneda_destino)
);

CREATE TABLE sistema_externo (
    id      VARCHAR(32) PRIMARY KEY,
    nombre  VARCHAR(120) NOT NULL,
    codigo  VARCHAR(20) NOT NULL UNIQUE,
    activo  BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE operacion (
    id                      UUID PRIMARY KEY,
    tipo                    VARCHAR(25) NOT NULL
                            CHECK (tipo IN ('CREACION','DEPOSITO','RETIRO','TRANSFERENCIA','CAMBIO',
                                             'INTERES','TRANSFERENCIA_EXTERNA')),
    cuenta_origen_id        VARCHAR(64) REFERENCES cuenta(id),
    cuenta_destino_id       VARCHAR(64) REFERENCES cuenta(id),
    valor_centavos          BIGINT NOT NULL CHECK (valor_centavos >= 0),
    moneda_origen           VARCHAR(3),
    moneda_destino          VARCHAR(3),
    tasa_aplicada           NUMERIC(18,8),
    valor_destino_centavos  BIGINT,
    sistema_externo_id      VARCHAR(32) REFERENCES sistema_externo(id),
    referencia_externa      VARCHAR(64),
    fecha_hora              TIMESTAMP NOT NULL DEFAULT now(),
    estado                  VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE'
                            CHECK (estado IN ('PENDIENTE','CONFIRMADA','RECHAZADA','CANCELADA')),
    CONSTRAINT chk_cambio_completo CHECK (
        tipo <> 'CAMBIO'
        OR (moneda_origen IS NOT NULL AND moneda_destino IS NOT NULL
            AND tasa_aplicada IS NOT NULL AND valor_destino_centavos IS NOT NULL)
    ),
    CONSTRAINT chk_externa_completa CHECK (
        tipo <> 'TRANSFERENCIA_EXTERNA' OR sistema_externo_id IS NOT NULL
    )
);
CREATE INDEX idx_operacion_origen ON operacion(cuenta_origen_id, fecha_hora);
CREATE INDEX idx_operacion_destino ON operacion(cuenta_destino_id, fecha_hora);

EOF
```

Y luego, en la misma terminal, **genera una contraseña fuerte** — nunca
escribas una contraseña real dentro de este archivo ni de ningún archivo
que subas a git; genera una nueva cada vez que la necesites y guárdala
aparte (un gestor de contraseñas, o una variable de entorno local tuya):

```bash
openssl rand -base64 24
```

### Comando adicional, si no se instalo docker
```bash
sudo dnf install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
newgrp docker
```
Copia lo que te devuelva (es un solo uso de un momento; no queda guardado
en ningún lado si cierras la terminal) y úsalo en el siguiente comando, en
las **3** instancias de Postgres — la misma contraseña en las 3, para no
confundirte después:

```bash
docker run -d --name postgres-a -p 5432:5432 \
  --restart unless-stopped --memory=512m \
  -e POSTGRES_DB=banco -e POSTGRES_USER=banco -e POSTGRES_PASSWORD='<pega-aqui-lo-que-te-devolvio-openssl>' \
  -v ~/schema.sql:/docker-entrypoint-initdb.d/schema.sql:ro \
  postgres:16-alpine
```

(cambia `postgres-a` por el nombre real de esa instancia)

`--restart unless-stopped` y `--memory=512m` no son decorativos — son
justo lo que la literatura marca como el mínimo indispensable para correr
Postgres en Docker sin que un reinicio de la instancia o un pico de memoria
te tumbe la base sin avisar. Ver la nota completa (y lo que **falta** para
producción real: respaldo/WAL archiving) en
[`GUIA-REPLICA-POSTGRESQL.md`](GUIA-REPLICA-POSTGRESQL.md).

### Paso 3 — Levantar el backend (misma terminal en el navegador)

Primero, sube tu código a GitHub si todavía no lo hiciste (`git push`) —
es la forma más simple de traerlo a cada instancia sin usar `scp` desde tu
Windows. Por cada una de las 3 instancias `backend-X`: botón **Connect** →
EC2 Instance Connect, igual que en el Paso 2, y ahí:

```bash
sudo dnf install -y git   # Amazon Linux 2023 no lo trae de fábrica
git clone https://github.com/PauloRPinedo/banco-distribuido.git
cd banco-distribuido/projeto-final/backend
docker build -t backend .
docker run -d --name backend-a -p 8001:8001 \
  --restart unless-stopped \
  -e NODO_ID=A -e PUERTO=8001 \
  -e PGHOST=172.31.12.43 -e PGPORT=5432 -e PGDATABASE=banco \
  -e PGUSER=banco -e PGPASSWORD='<la-misma-contraseña-de-postgres-de-este-nodo>' \
  -e SECRET_KEY='<la-misma-secret-key-en-los-3-backends>' \
  backend
```
si me equivoco uso este comando para volver a empezar:

docker rm -f backend-b

(cambia `backend-a`, `NODO_ID=A` y la IP de Postgres según la instancia; el
`--name` del contenedor y `NODO_ID` son cosas distintas — el primero es solo
para identificarlo en `docker ps`, el segundo es el identificador real que
usa el protocolo (`config/cluster.json`, RN-09); si tu repositorio es
privado, `git clone` te va a pedir usuario/token — avísame y lo vemos aparte)

**Antes de seguir, prueba las 3 desde tu propio navegador** (no hace falta
terminal para esto): abre `http://<IP_PUBLICA_backend-a>:8001/interno/estado`
en una pestaña — debe mostrarte un JSON como
`{"nodo":"A","rol":"primario","epoch":1}` (aquí `"nodo":"A"` es el campo de
la respuesta, el `NODO_ID` que configuraste — no el nombre de la instancia).
Repite con `backend-b` y `backend-c`.
Si alguna no responde, revisa el *security group* `banco-backend` (Paso
0.2) antes de seguir — un puerto mal puesto ahora se ve después como
"elección que no converge" y hace perder horas buscando en el sitio
equivocado (`docs/SPECS.md` §9).

### Paso 4 — El balanceador, en Lambda

No es una instancia — es una función. El código no cambia entre local y
Lambda (`balanceador/enrutador.py` es el mismo); solo cambia cómo se invoca
(`uvicorn` en local, `Mangum` en Lambda — ver `balanceador/main.py`).

**4.1 — Crear el repositorio de imágenes**: consola → busca **"ECR"** →
**Create repository** → Visibility: `Private` → Repository name:
`banco-balanceador` → **Create repository**.

**4.2 — Construir y subir la imagen** (este sí necesita **CloudShell** — el
ícono de terminal en la barra superior de la consola, junto a la campana de
notificaciones; es parte del portal, no algo que instalas). Una vez abierto:

**Si CloudShell dice "No se puede crear el entorno... verificación de su
cuenta está en curso"**: es una restricción real de AWS para cuentas nuevas
(puede tardar hasta 2 días) — no hay nada que arreglar en tu configuración,
solo hay que evitarlo. Alternativa, con el mismo criterio de "portal, sin
instalar nada en tu máquina": usa una instancia `backend-X` que ya tiene
Docker, conectándote con **EC2 Instance Connect** (igual que en el Paso 3).

1. EC2 → Instancias → selecciona la instancia → **Actions** → **Security**
   → **Modify IAM role** → **Create new IAM role** → Trusted entity:
   `AWS service`, Use case: `EC2` → marca `AmazonEC2ContainerRegistryPowerUser`
   → Role name: `backend-ecr-temporal` → **Create role** → vuelve, selecciónalo
   → **Update IAM role** (permiso temporal, solo para poder hacer `push`; se
   puede quitar después).
2. **Connect** en esa misma instancia → EC2 Instance Connect, y corre ahí los
   mismos comandos de abajo (el repositorio ya está clonado de cuando
   montaste el backend — solo `cd banco-distribuido/projeto-final/balanceador`
   y `git pull`).

```bash
git clone https://github.com/PauloRPinedo/banco-distribuido.git
cd banco-distribuido/projeto-final/balanceador

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws ecr get-login-password --region us-east-2 | docker login --username AWS \
  --password-stdin $ACCOUNT_ID.dkr.ecr.us-east-2.amazonaws.com

docker build -f Dockerfile.lambda -t banco-balanceador .
docker tag banco-balanceador $ACCOUNT_ID.dkr.ecr.us-east-2.amazonaws.com/banco-balanceador:latest
docker push $ACCOUNT_ID.dkr.ecr.us-east-2.amazonaws.com/banco-balanceador:latest
```

**4.3 — Rol para que Lambda pueda ejecutarse**: consola → busca **"IAM"**
→ **Roles** → **Create role**.
- Trusted entity type: `AWS service`
- Use case: `Lambda`
- **Next** → busca y marca la política `AWSLambdaBasicExecutionRole` →
  **Next**
- Role name: `banco-lambda-rol` → **Create role**

**4.4 — Crear la función**: consola → busca **"Lambda"** → **Create
function**.
- Elige **Container image**
- Function name: `banco-balanceador`
- Container image URI: **Browse images** → repositorio `banco-balanceador`
  → tag `latest`
- Change default execution role → `Use an existing role` → `banco-lambda-rol`
- **Create function**

**4.5 — Configurar la lista de nodos**: dentro de la función →
pestaña **Configuration** → **Environment variables** → **Edit** → **Add
environment variable**:
- Key: `CLUSTER_CONFIG_JSON`
- Value (una sola línea, con las **IPs públicas** de los 3 `backend-X` del
  Paso 1):
  ```
  {"nos":[{"id":"A","endereco":"<IP_PUBLICA_backend-a>","porta":8001},{"id":"B","endereco":"<IP_PUBLICA_backend-b>","porta":8001},{"id":"C","endereco":"<IP_PUBLICA_backend-c>","porta":8001}]}
  ```
- **Save**

**4.6 — Activar la Function URL**: misma pestaña **Configuration** →
**Function URL** (menú de la izquierda, dentro de la función) → **Create
function URL** → Auth type: `NONE` → **Save**. Copia la URL que aparece —
la necesitas en el Paso 5.

**Trade-off honesto:** sin proceso siempre encendido, se pierde el caché de
"quién es primario" entre invocaciones frías, y hay *cold start* (cientos de
ms en la primera petición tras estar inactivo). Aceptable para una demo.

### Paso 5 — El frontend, en Vercel

El frontend le habla siempre a `/api/...` (nunca a una URL completa — ver
`src/api/cliente.js`); en Docker eso lo reenvía Nginx (`nginx.conf`), pero
Vercel solo sirve archivos estáticos, sin ese reenvío. Por eso
`frontend/vercel.json` ya trae una regla de *rewrite* que manda `/api/*` a
la Function URL del Paso 4.6 — no hay que configurar ninguna variable de
entorno para esto, el archivo ya la trae escrita (la Function URL no es un
secreto: su modo de invocación es `NONE`, pensada para ser pública).

**Si el repositorio no es tuyo** (eres colaborador, no dueño — como en este
proyecto): consola de Vercel (no de AWS): [vercel.com](https://vercel.com)
→ inicia sesión con tu cuenta de GitHub → **Add New** → **Project** →
**Import Git Repository**. Si `banco-distribuido` no aparece en la lista,
busca el enlace **"Adjust GitHub App Permissions"** (o "¿No ves tu
repositorio?") — te lleva a la página de instalación de la GitHub App de
Vercel, donde puedes **solicitar acceso** a ese repositorio puntual (GitHub
te deja pedirlo porque eres colaborador con permiso de escritura). Eso le
manda una notificación al dueño del repositorio (quien lo creó), que tiene
que **aprobarla** desde GitHub (Settings → Integrations → Applications, o
el enlace que le llega por correo/notificación). Una vez aprobada, el
repositorio aparece en tu lista de Vercel.

Con el repositorio ya conectado: selecciona la carpeta `projeto-final/frontend`
como *root directory* → **Deploy**. No agregues variables de entorno, el
`vercel.json` ya resuelve el reenvío.

### Paso 6 — Verificar de punta a punta

Desde el navegador, abre la URL que te dio Vercel y repite el flujo
completo: registro → login → crear cuenta → depositar. También puedes
abrir directo `<FUNCTION_URL>/salud` en una pestaña — debe mostrar
`{"balanceador":"activo"}`.

### Apagar todo al terminar

Consola de EC2 → **Instances** → selecciona las 6 → **Instance state** →
**Stop instance** (no "Terminate"). "Stop" conserva los discos (tu Postgres
con sus datos) y deja de cobrar cómputo mientras está detenida — para la
próxima sesión, selecciónalas de nuevo y **Start instance**, sin repetir
los pasos 1-3.

---

## CI/CD

`.github/workflows/ci-cd.yml`, en tres etapas — esto sí es código (GitHub
Actions no tiene versión "por consola" real), pero solo lo tocas una vez al
configurarlo, no en cada despliegue manual de arriba:

1. **Pruebas** — `unittest` del backend y del balanceador, sin BD ni red.
2. **Build y publicación** — imagen de `backend` a GitHub Container
   Registry, imagen de `balanceador` (con `Dockerfile.lambda`) a ECR.
3. **Despliegue** — por SSH a los nodos, `aws lambda update-function-code`
   para el balanceador, Vercel se despliega solo con cada `push`.

Mientras los secretos de AWS/SSH no existan en GitHub, esos pasos fallan —
pruebas y *build* siguen funcionando igual.
