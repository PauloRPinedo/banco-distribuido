# Guia de implantação

Cobre os 4 serviços de `prototipo-2/`, como os subir localmente, como os
implantar "a sério" **a partir da consola web da AWS** (sem CLI), e o
pipeline de CI/CD.

Região: **`us-east-2` (Ohio)** — confirma-a no canto superior direito da
consola antes de criar o que quer que seja; o que se cria noutra região não
se vê entre si.

**Aviso honesto:** quase toda a implantação se faz com cliques. Há
exatamente **2 momentos** em que isso não chega — porque nenhuma consola da
AWS tem um botão para "correr este contentor Docker" nem para "construir
esta imagem": subir os contentores dentro de cada instância (Passos 2 e 3),
e construir/enviar a imagem do balanceador para o ECR (Passo 4). Para esses
dois usa-se o botão **"Connect"** da própria consola do EC2 — abre um
terminal **dentro do navegador**, sem instalar nada — e o **CloudShell**
(outro botão da consola, no canto superior direito) para o build da imagem.
Ambos fazem parte do portal, não são uma ferramenta à parte; o guia avisa
exatamente quando entram.

## Os serviços

| Serviço | O que faz | Local (`docker compose`) | A sério |
|---|---|---|---|
| `backend-a` / `backend-b` / `backend-c` | Backend FastAPI de cada nó | Contentor, porta 8001 | Instância EC2 própria por nó |
| `postgres-a` / `postgres-b` / `postgres-c` | Armazenamento local de cada nó — sem réplica nativa, ver [`GUIA-REPLICA-POSTGRESQL.md`](GUIA-REPLICA-POSTGRESQL.md) | Contentor, porta 5432 | Instância EC2 própria por nó, **separada** do seu backend |
| `balanceador` | Encontra o primário, reenvia, segue o `409` | Contentor, porta 8000 | **AWS Lambda** (Function URL) — não é uma instância |
| `frontend` | React compilado | Contentor Nginx, porta 8080 | **Vercel** — não é uma instância |

**6 instâncias EC2** no total (3 backend + 3 Postgres). O balanceador e o
frontend não contam como instância: o balanceador não tem estado próprio, e
o frontend são ficheiros estáticos.

## Local, com um só comando

```bash
cd prototipo-2
SECRET_KEY=$(openssl rand -hex 32) docker compose up --build
```

Frontend em `http://localhost:8080`. Desligar tudo: `docker compose down -v`.

---

## Implantação a sério, pela consola web

### Passo 0 — Chave SSH e *security groups*

**0.1 — Criar a chave** (para conseguir ligar-te às instâncias):
Consola → procura **"EC2"** → menu da esquerda, secção **Network & Security**
→ **Key Pairs** → botão **Create key pair**.
- Name: `banco-key`
- Key pair type: `RSA`
- Private key file format: `.pem`
- **Create key pair** → o `banco-key.pem` descarrega-se sozinho — guarda-o,
  faz falta mais à frente para o botão "Connect".

**0.2 — Grupo de segurança para os backends**: menu da esquerda → **Security
Groups** → **Create security group**.
- Security group name: `banco-backend`
- Description: `Backend API`
- VPC: a que aparece por omissão (não mexer)
- **Inbound rules** → **Add rule** (três vezes):
  1. Type: `SSH` — Source: `My IP` (assim só tu te ligas por SSH)
  2. Type: `SSH` — Source: `Custom` → `3.16.146.0/29` (o intervalo do próprio
     serviço **EC2 Instance Connect** em `us-east-2` — é quem realmente
     origina a ligação quando se usa o botão "Connect → No navegador web";
     sem esta regra esse botão não funciona, mesmo com `My IP` já posta. A
     AWS mostra este mesmo intervalo, num aviso amarelo ao ligar, se faltar)
  3. Type: `Custom TCP` — Port range: `8001` — Source: `Anywhere-IPv4`
     (`0.0.0.0/0`)

  *Porque a 8001 fica aberta a toda a internet, de propósito:* o Lambda (o
  balanceador) não vive dentro da rede privada, por isso precisa de chegar
  à API de cada nó a partir de fora. É uma simplificação consciente para a
  disciplina.

  **Endurecimento pendente (próximo passo, não bloqueia a implantação de
  hoje):** as rotas de dinheiro já exigem sessão (`banco/api/seguranca.py`,
  RF-26) — isso cobre o risco de alguém mover dinheiro sem token. O que
  continua aberto é a exposição de **rede**: ligar a função Lambda a esta
  mesma VPC permitiria substituir `0.0.0.0/0` na porta 8001 apenas pelo
  *security group* do balanceador, tal como já se fez com o Postgres. Não é
  necessário para a disciplina — é a melhoria seguinte, se se quiser fechar
  também a exposição de rede e não só a de aplicação.
- **Create security group**.

**0.3 — Grupo de segurança para o Postgres**: o mesmo botão **Create
security group** outra vez.
- Security group name: `banco-postgres`
- Description: `Postgres`
- **Inbound rules**:
  1. Type: `SSH` — Source: `My IP`
  2. Type: `SSH` — Source: `Custom` → `3.16.146.0/29` (intervalo do EC2
     Instance Connect em `us-east-2` — necessário para o botão "Connect → No
     navegador web", tal como em `banco-backend`)
  3. Type: `PostgreSQL` (já traz a porta 5432) — Source: escreve
     `banco-backend` na caixa e **seleciona o grupo** na lista que aparece
     (não um IP) — assim **só** os backends chegam ao Postgres, nunca a
     internet.
- **Create security group**.

### Passo 1 — Lançar as 6 instâncias, uma por zona de disponibilidade

**Porque é que isto importa:** se os 3 nós caírem na mesma zona de
disponibilidade (AZ) e essa zona falhar por inteiro (acontece, ainda que não
seja comum), perdem-se os 3 de uma vez — de nada serve o protocolo de
maioria se as 3 cópias estão ligadas ao mesmo sítio físico. A correção:
**cada nó (o seu backend + o seu Postgres, juntos) numa AZ diferente** — não
numa região diferente, isso criaria outro problema (ver a nota no fim).
`us-east-2` tem 3 zonas; distribui-se assim:

| Nó | Zona (AZ) |
|---|---|
| A (`postgres-a` + `backend-a`) | `us-east-2a` |
| B (`postgres-b` + `backend-b`) | `us-east-2b` |
| C (`postgres-c` + `backend-c`) | `us-east-2c` |

Repete-se este assistente **6 vezes** (muda o nome, a sub-rede/AZ e o
*security group* de cada vez, conforme o nó a que pertence). Consola do EC2
→ **Instances** → **Launch instance**.

1. **Name**: `postgres-a` (depois `postgres-b`, `postgres-c`, `backend-a`,
   `backend-b`, `backend-c`)
2. **Application and OS Images**: `Amazon Linux 2023` (aparece primeiro,
   marcada "Free tier eligible")
3. **Instance type**: `t3.micro` (marcada "Free tier eligible")
4. **Key pair**: `banco-key`
5. **Network settings** → **Edit**:
   - VPC: a de omissão
   - **Subnet**: escolhe explicitamente a sub-rede da AZ que cabe a esse nó
     segundo a tabela acima (a lista mostra o nome da zona, ex.
     "us-east-2a") — **não** deixes "No preference"; as duas instâncias do
     mesmo nó (`postgres-X` e `backend-X`) vão na **mesma** AZ entre si
     (para que a latência entre elas seja mínima), mas diferente da dos
     outros dois nós
   - Auto-assign public IP: `Enable`
   - Firewall (security groups): `Select existing security group` →
     `banco-postgres` (para as 3 `postgres-X`) ou `banco-backend` (para as 3
     `backend-X`)
6. **Advanced details** → desce até **User data** e cola exatamente isto
   (igual nas 6, instala o Docker):
   ```bash
   #!/bin/bash
   dnf install -y docker
   systemctl enable --now docker
   usermod -aG docker ec2-user
   ```
7. **Launch instance**.

Quando as 6 estiverem "Running" (~1 minuto), na lista de **Instances** clica
no ícone da roda dentada ⚙️ (canto superior direito da tabela) e ativa as
colunas **Private IPv4 addresses** e **Public IPv4 address** se não
aparecerem. Anota as 6 numa tabela tua — vão ser usadas no resto do guia.

**Não misturar os endereços:**

| Para quê | Que endereço usar |
|---|---|
| Um backend a falar com **o seu próprio** Postgres | IP **privado** de `postgres-X` |
| Os 3 backends entre si (quando o protocolo real existir) | IP **privado** de `backend-X` |
| O balanceador (Lambda) a falar com os backends | IP **público** de `backend-X` |

(os IPs privados de instâncias em AZ diferentes da mesma VPC alcançam-se
entre si sem configuração extra — uma VPC já abrange todas as zonas da
região; nada do que está acima muda por se terem distribuído os nós)

**Porque não distribuir por regiões diferentes em vez de AZ:** o protocolo
tem temporizadores finos (*heartbeat* a cada 150 ms, *timeout* de eleição de
800-1500 ms). Entre zonas da mesma região a latência é de <1-2 ms — o
protocolo não a nota. Entre regiões diferentes (ex. Ohio↔Califórnia) pode
ser de 50-100 ms, o suficiente para o sistema confundir "o outro nó está
longe" com "o outro nó caiu" e disparar eleições a toda a hora — trocava-se
um problema real (falha de uma zona) por um pior (o cluster nunca converge).
Multi-AZ é o nível certo de resiliência para este projeto; multi-região não.

### Passo 2 — Subir o Postgres (terminal no navegador, sem instalar nada)

Para cada uma das 3 instâncias `postgres-X`: na lista de **Instances**,
seleciona-a → botão **Connect** (em cima) → separador **EC2 Instance
Connect** → **Connect**. Abre-se um terminal num separador novo, **dentro do
navegador** — não é preciso PuTTY nem a chave `.pem` para isto.

Lá dentro, cola o conteúdo completo de [`backend/db/esquema.sql`](../backend/db/esquema.sql)
assim (abre-o no editor, copia tudo e cola-o entre as linhas `EOF`):

```bash
cat > esquema.sql <<'EOF'
<conteúdo de prototipo-2/backend/db/esquema.sql>
EOF
```

O esquema não se repete aqui de propósito: uma segunda cópia neste guia
desatualizava-se na primeira alteração a uma tabela.

Depois, no mesmo terminal, **gera uma senha forte** — nunca escrevas uma
senha real dentro deste ficheiro nem de nenhum ficheiro que suba para o
git; gera uma nova sempre que for precisa e guarda-a à parte (um gestor de
senhas, ou uma variável de ambiente local tua):

```bash
openssl rand -base64 24
```

### Comando adicional, se o Docker não ficou instalado

```bash
sudo dnf install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user
newgrp docker
```

Copia o que o `openssl` devolveu (é de uso único; não fica guardado em sítio
nenhum se fechares o terminal) e usa-o no comando seguinte, nas **3**
instâncias do Postgres — a mesma senha nas 3, para não haver confusões
depois:

```bash
docker run -d --name postgres-a -p 5432:5432 \
  --restart unless-stopped --memory=512m \
  -e POSTGRES_DB=banco -e POSTGRES_USER=banco -e POSTGRES_PASSWORD='<cola-aqui-o-que-o-openssl-devolveu>' \
  -v ~/esquema.sql:/docker-entrypoint-initdb.d/esquema.sql:ro \
  postgres:16-alpine
```

(troca `postgres-a` pelo nome real dessa instância)

`--restart unless-stopped` e `--memory=512m` não são decorativos — são
precisamente o que a literatura dá como o mínimo indispensável para correr o
Postgres em Docker sem que um reinício da instância ou um pico de memória
derrube a base sem aviso. Ver a nota completa (e o que **falta** para
produção real: cópias de segurança/arquivo do WAL) em
[`GUIA-REPLICA-POSTGRESQL.md`](GUIA-REPLICA-POSTGRESQL.md).

### Passo 3 — Subir o backend (o mesmo terminal no navegador)

Primeiro, envia o código para o GitHub se ainda não o fizeste (`git push`) —
é a forma mais simples de o trazer para cada instância sem usar `scp`. Para
cada uma das 3 instâncias `backend-X`: botão **Connect** → EC2 Instance
Connect, como no Passo 2, e aí:

```bash
sudo dnf install -y git   # o Amazon Linux 2023 não o traz de fábrica
git clone https://github.com/PauloRPinedo/banco-distribuido.git
cd banco-distribuido/prototipo-2/backend
docker build -t backend .
docker run -d --name backend-a -p 8001:8001 \
  --restart unless-stopped \
  -e NO_ID=A -e PORTA=8001 \
  -e PGHOST=172.31.12.43 -e PGPORT=5432 -e PGDATABASE=banco \
  -e PGUSER=banco -e PGPASSWORD='<a-mesma-senha-do-postgres-deste-no>' \
  -e SECRET_KEY='<a-mesma-secret-key-nos-3-backends>' \
  backend
```

Para recomeçar depois de um engano:

```bash
docker rm -f backend-a
```

(troca `backend-a`, `NO_ID=A` e o IP do Postgres conforme a instância; o
`--name` do contentor e o `NO_ID` são coisas diferentes — o primeiro serve só
para o identificar no `docker ps`, o segundo é o identificador real que o
protocolo usa (`config/cluster.json`, RN-09); se o repositório for privado,
o `git clone` pede utilizador/token)

**Antes de continuar, testa as 3 a partir do teu próprio navegador** (não é
preciso terminal para isto): abre `http://<IP_PUBLICO_backend-a>:8001/interno/estado`
num separador — tem de mostrar um JSON como
`{"no":"A","papel":"primario","epoch":1}` (aqui `"no":"A"` é o campo da
resposta, o `NO_ID` que configuraste — não o nome da instância). Repete com
`backend-b` e `backend-c`. Se alguma não responder, revê o *security group*
`banco-backend` (Passo 0.2) antes de continuar — uma porta mal posta agora
aparece depois como "eleição que não converge" e faz perder horas a procurar
no sítio errado.

### Passo 4 — O balanceador, no Lambda

Não é uma instância — é uma função. O código não muda entre local e Lambda
(`balanceador/encaminhador.py` é o mesmo); muda só a forma como é invocado
(`uvicorn` localmente, `Mangum` no Lambda — ver `balanceador/main.py`).

**4.1 — Criar o repositório de imagens**: consola → procura **"ECR"** →
**Create repository** → Visibility: `Private` → Repository name:
`banco-balanceador` → **Create repository**.

**4.2 — Construir e enviar a imagem** (este precisa mesmo do
**CloudShell** — o ícone de terminal na barra superior da consola, ao lado
do sino das notificações; faz parte do portal, não é algo que se instala).
Depois de aberto:

**Se o CloudShell disser "Não é possível criar o ambiente... a verificação
da sua conta está em curso"**: é uma restrição real da AWS para contas novas
(pode demorar até 2 dias) — não há nada a corrigir na configuração, só há
que contorná-la. Alternativa, com o mesmo critério de "portal, sem instalar
nada na máquina": usar uma instância `backend-X` que já tem Docker, ligando
com o **EC2 Instance Connect** (como no Passo 3).

1. EC2 → Instâncias → seleciona a instância → **Actions** → **Security** →
   **Modify IAM role** → **Create new IAM role** → Trusted entity:
   `AWS service`, Use case: `EC2` → marca `AmazonEC2ContainerRegistryPowerUser`
   → Role name: `backend-ecr-temporal` → **Create role** → volta, seleciona-o
   → **Update IAM role** (permissão temporária, só para poder fazer `push`;
   pode retirar-se depois).
2. **Connect** nessa mesma instância → EC2 Instance Connect, e corre aí os
   mesmos comandos de baixo (o repositório já está clonado desde que se
   montou o backend — basta `cd banco-distribuido/prototipo-2/balanceador`
   e `git pull`).

```bash
git clone https://github.com/PauloRPinedo/banco-distribuido.git
cd banco-distribuido/prototipo-2/balanceador

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws ecr get-login-password --region us-east-2 | docker login --username AWS \
  --password-stdin $ACCOUNT_ID.dkr.ecr.us-east-2.amazonaws.com

docker build -f Dockerfile.lambda -t banco-balanceador .
docker tag banco-balanceador $ACCOUNT_ID.dkr.ecr.us-east-2.amazonaws.com/banco-balanceador:latest
docker push $ACCOUNT_ID.dkr.ecr.us-east-2.amazonaws.com/banco-balanceador:latest
```

**4.3 — Papel para o Lambda se poder executar**: consola → procura
**"IAM"** → **Roles** → **Create role**.
- Trusted entity type: `AWS service`
- Use case: `Lambda`
- **Next** → procura e marca a política `AWSLambdaBasicExecutionRole` →
  **Next**
- Role name: `banco-lambda-papel` → **Create role**

**4.4 — Criar a função**: consola → procura **"Lambda"** → **Create
function**.
- Escolhe **Container image**
- Function name: `banco-balanceador`
- Container image URI: **Browse images** → repositório `banco-balanceador`
  → tag `latest`
- Change default execution role → `Use an existing role` → `banco-lambda-papel`
- **Create function**

**4.5 — Configurar a lista de nós**: dentro da função → separador
**Configuration** → **Environment variables** → **Edit** → **Add
environment variable**:
- Key: `CLUSTER_CONFIG_JSON`
- Value (uma única linha, com os **IPs públicos** dos 3 `backend-X` do
  Passo 1):
  ```
  {"nos":[{"id":"A","endereco":"<IP_PUBLICO_backend-a>","porta":8001},{"id":"B","endereco":"<IP_PUBLICO_backend-b>","porta":8001},{"id":"C","endereco":"<IP_PUBLICO_backend-c>","porta":8001}]}
  ```
- **Save**

**4.6 — Ativar a Function URL**: o mesmo separador **Configuration** →
**Function URL** (menu da esquerda, dentro da função) → **Create function
URL** → Auth type: `NONE` → **Save**. Copia o URL que aparece — faz falta no
Passo 5.

**Compromisso honesto:** sem um processo sempre ligado, perde-se a cache de
"quem é o primário" entre invocações a frio, e há *cold start* (centenas de
ms no primeiro pedido depois de estar inativo). Aceitável para uma
demonstração.

### Passo 5 — O frontend, no Vercel

O frontend fala sempre com `/api/...` (nunca com um URL completo — ver
`src/api/cliente.js`); em Docker, quem reenvia isso é o Nginx
(`nginx.conf`), mas o Vercel só serve ficheiros estáticos, sem esse
reenvio. Por isso `frontend/vercel.json` já traz uma regra de *rewrite* que
manda `/api/*` para a Function URL do Passo 4.6 — não é preciso configurar
nenhuma variável de ambiente para isto, o ficheiro já a traz escrita (a
Function URL não é um segredo: o modo de invocação é `NONE`, pensada para
ser pública).

> O `vercel.json` desta pasta ainda aponta para a Function URL do projeto
> final. Quando o Protótipo 2 tiver a sua própria função, troca-se aí.

**Se o repositório não for teu** (és colaborador, não dono — como neste
projeto): consola do Vercel (não da AWS): [vercel.com](https://vercel.com)
→ entra com a conta do GitHub → **Add New** → **Project** → **Import Git
Repository**. Se `banco-distribuido` não aparecer na lista, procura a
ligação **"Adjust GitHub App Permissions"** — leva à página de instalação da
GitHub App do Vercel, onde se pode **pedir acesso** a esse repositório em
concreto (o GitHub deixa pedi-lo a um colaborador com permissão de
escrita). Isso envia uma notificação ao dono do repositório (quem o criou),
que tem de a **aprovar** no GitHub (Settings → Integrations → Applications,
ou a ligação que recebe por correio/notificação). Depois de aprovada, o
repositório aparece na lista do Vercel.

Com o repositório ligado: seleciona a pasta `prototipo-2/frontend` como
*root directory* → **Deploy**. Não acrescentes variáveis de ambiente, o
`vercel.json` já resolve o reenvio.

### Passo 6 — Verificar de ponta a ponta

No navegador, abre o URL que o Vercel deu e repete o fluxo completo:
registo → login → criar conta → depositar. Também se pode abrir diretamente
`<FUNCTION_URL>/saude` num separador — tem de mostrar
`{"balanceador":"ativo"}`.

### Desligar tudo no fim

Consola do EC2 → **Instances** → seleciona as 6 → **Instance state** →
**Stop instance** (não "Terminate"). O "Stop" conserva os discos (o
Postgres com os seus dados) e deixa de cobrar computação enquanto está
parada — na sessão seguinte, seleciona-as outra vez e **Start instance**,
sem repetir os passos 1-3.

---

## CI/CD

`docs/ci-cd.yml`, em três etapas — isto sim é código (o GitHub
Actions não tem versão "por consola" real), mas só se mexe uma vez, ao
configurá-lo, não em cada implantação manual acima:

1. **Testes** — `unittest` do backend e do balanceador, sem BD nem rede.
2. **Build e publicação** — imagem do `backend` para o GitHub Container
   Registry, imagem do `balanceador` (com `Dockerfile.lambda`) para o ECR.
3. **Implantação** — por SSH para os nós, `aws lambda update-function-code`
   para o balanceador; o Vercel implanta-se sozinho a cada `push`.

O GitHub só lê workflows em `.github/workflows/` na **raiz** do repositório;
o ficheiro fica em `docs/` como referência e só corre se for copiado para lá.
Enquanto os segredos de AWS/SSH não existirem no GitHub, esses passos
falham — os testes e o *build* continuam a funcionar.
