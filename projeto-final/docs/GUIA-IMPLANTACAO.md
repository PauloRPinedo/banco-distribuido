# Guia de implantação

Cobre os 4 serviços de `projeto-final/`, como os subir localmente, como os
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
| `postgres-a` / `postgres-b` / `postgres-c` | Armazenamento local de cada nó — sem réplica nativa: replica a aplicação (ver [`PROPOSTA-ARQUITETURA-AWS.md`, 2.4](PROPOSTA-ARQUITETURA-AWS.md#24-porque-é-que-as-bases-de-dados-não-comunicam-entre-si)) | Contentor, porta 5432 | Instância EC2 própria por nó, **separada** do seu backend |
| `balanceador` | Encontra o primário, reenvia, segue o `409` | Contentor, porta 8000 | **AWS Lambda** (Function URL) — não é uma instância |
| `frontend` | React compilado | Contentor Nginx, porta 8080 | **Vercel** — não é uma instância |

**6 instâncias EC2** no total (3 backend + 3 Postgres). O balanceador e o
frontend não contam como instância: o balanceador não tem estado próprio, e
o frontend são ficheiros estáticos.

## Local, com um só comando

```bash
cd projeto-final
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
<conteúdo de projeto-final/backend/db/esquema.sql>
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
derrube a base sem aviso. O que **falta** para dinheiro real, e fica de fora
de propósito: cópias de segurança (`pg_dump` agendado, arquivo do WAL).

Não se configura nenhuma réplica do Postgres: nada de `wal_level = replica`,
`primary_conninfo` nem `pg_hba.conf` a aceitar outras bases. Só o backend do
mesmo nó se liga a cada Postgres, e a 5432 só se abre para o IP desse backend.

### Passo 3 — Subir o backend (o mesmo terminal no navegador)

> Se os backends já correm uma versão anterior (a de dois nós, com `PARES` e
> `ROL`), não basta reconstruir a imagem: o esquema da base mudou. Segue
> [`GUIA-RECONSTRUIR-EC2.md`](GUIA-RECONSTRUIR-EC2.md).

Primeiro, envia o código para o GitHub se ainda não o fizeste (`git push`) —
é a forma mais simples de o trazer para cada instância sem usar `scp`. Para
cada uma das 3 instâncias `backend-X`: botão **Connect** → EC2 Instance
Connect, como no Passo 2, e aí:

```bash
sudo dnf install -y git   # o Amazon Linux 2023 não o traz de fábrica
git clone https://github.com/PauloRPinedo/banco-distribuido.git
cd banco-distribuido/projeto-final/backend
docker build -t backend .

# Quem são os três nós: o MESMO ficheiro nas 3 instâncias, com os IPs
# PRIVADOS dos três backends (os nós falam entre si dentro da VPC).
sudo mkdir -p /etc/banco
sudo tee /etc/banco/cluster.json >/dev/null <<'JSON'
{"nos": [
  {"id": "A", "endereco": "<IP_PRIVADO_backend-a>", "porta": 8001},
  {"id": "B", "endereco": "<IP_PRIVADO_backend-b>", "porta": 8001},
  {"id": "C", "endereco": "<IP_PRIVADO_backend-c>", "porta": 8001}],
 "heartbeat_ms": 150, "timeout_eleicao_ms": [800, 1500],
 "timeout_replicacao_ms": 500, "semente": 42}
JSON

docker run -d --name backend-a -p 8001:8001 \
  --restart unless-stopped \
  -v /etc/banco/cluster.json:/config/cluster.json:ro \
  -e CLUSTER_CONFIG=/config/cluster.json \
  -e NO_ID=A -e PORTA=8001 \
  -e PGHOST=<IP_PRIVADO_postgres-a> -e PGPORT=5432 -e PGDATABASE=banco \
  -e PGUSER=banco -e PGPASSWORD='<a-senha-do-postgres-deste-no>' \
  -e SECRET_KEY='<a-mesma-secret-key-nos-3-backends>' \
  -e CHAVE_ADMIN='<outra-chave-so-para-quem-regista-taxas>' \
  backend
```

Sem `CLUSTER_CONFIG` o nó arranca **sozinho**: diz-se primário, não replica
nada, e cada base fica com dados diferentes. A `SECRET_KEY` tem de ser a mesma
nos três porque, além de assinar os tokens, dela se deriva a chave com que os
nós falam entre si (`/interno/replicar`, `/interno/votar`, `/interno/log`
recusam com `403` quem não a tem — ver `backend/banco/autenticacao/chaves.py`).
Não se define `FALHAS_ATIVAS`: na AWS `POST /admin/falha` fica desligado,
porque derrubaria o nó a pedido de qualquer um.

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
   montou o backend — basta `cd banco-distribuido/projeto-final/balanceador`
   e `git pull`).

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

Com o repositório ligado: seleciona a pasta `projeto-final/frontend` como
*root directory* → **Deploy**. Não acrescentes variáveis de ambiente, o
`vercel.json` já resolve o reenvio.

### Passo 6 — Verificar de ponta a ponta

Por esta ordem, de dentro para fora. Troca `IP_X` pelos IPs dos backends. De
casa, a porta 8001 só responde se o teu IP estiver no *security group*
`banco-backend`; senão, testa a partir de outro backend.

**1. Cada nó está de pé e há um só primário.**

```bash
for ip in IP_A IP_B IP_C; do curl -sS -m 3 http://$ip:8001/interno/estado; echo; done
curl -sS http://IP_A:8001/interno/cluster; echo           # a vista do primário sobre os três
curl -sS -X POST http://IP_A:8001/interno/replicar \
  -H 'Content-Type: application/json' -d '{}'; echo       # sem a chave do cluster: 403 nao_e_par_do_cluster
```

Só um diz `primário`, e os três têm o mesmo `epoch` e o mesmo `lider`. Os
índices (`ultimo_indice`, `indice_commit`, `ultimo_aplicado`) são iguais, ou
ficam iguais no batimento seguinte.

**2. A Lambda chega ao primário.**

```text
<FUNCTION_URL>/saude                          -> {"balanceador":"ativo"}
<FUNCTION_URL>/interno/estado                 -> o estado do primário
https://<site>.vercel.app/api/interno/estado  -> o mesmo
```

Se o Vercel dá 502 e o ponto 1 funciona, a Lambda não alcança os backends: a
VPC, o *security group* ou um `CLUSTER_CONFIG_JSON` desatualizado.

**3. O painel.** No site: criar utilizador, abrir conta, depositar, extrato.
Com outro utilizador, numa janela anónima, abre uma conta e anota o número
(`0001 / ...`); com o primeiro, transfere para esse número e confirma o
titular. Recarrega em `/inicio`: tem de aparecer o mesmo ecrã, não um 404 (é o
*rewrite* `/(.*) → /index.html` do `vercel.json`).

**4. As três bases ficaram iguais.** Em cada `postgres-X`:

```bash
docker exec postgres-a psql -U banco -d banco -Atc \
  "SELECT count(*), sum(saldo_centavos), md5(string_agg(id || ':' || saldo_centavos, ',' ORDER BY id)) FROM conta"
```

As três linhas têm de ser iguais. Um nó que acabou de voltar alcança os outros
em segundos.

**5. Queda do primário.** Na consola, **Stop instance** no backend que for
primário (não *Terminate*). Em menos de 2 s, outro nó diz `primário` com o
`epoch` + 1, e o site continua a escrever. **Start instance**: o contentor
volta (`--restart unless-stopped`) como réplica e alcança os outros.

Os testes requisito a requisito estão em
[`GUIA-TESTES-RF-RNF.md`](GUIA-TESTES-RF-RNF.md); os de falhas pela consola, em
[`GUIA-TOLERANCIA-A-FALHAS.md`](GUIA-TOLERANCIA-A-FALHAS.md).

### Desligar tudo no fim

Consola do EC2 → **Instances** → seleciona as 6 → **Instance state** →
**Stop instance** (não "Terminate"). O "Stop" conserva os discos (o
Postgres com os seus dados) e deixa de cobrar computação enquanto está
parada — na sessão seguinte, seleciona-as outra vez e **Start instance**,
sem repetir os passos 1-3.

---

## CI/CD

[`.github/workflows/projeto-final.yml`](../../.github/workflows/projeto-final.yml),
na raiz do repositório (o único sítio onde o GitHub lê workflows). Corre só
quando muda `projeto-final/`, em três etapas:

1. **Testes** — o backend inteiro contra um Postgres de serviço (incluído o
   teste do cluster com três processos e `kill -9`), o balanceador, e o
   `npm run build` do painel. Corre também nos *pull requests*.
2. **Build e publicação** (só em `push` para `main`) — imagem do `backend`
   para o GitHub Container Registry
   (`ghcr.io/paulorpinedo/banco-distribuido/projeto-final/backend`), e a do
   `balanceador` (`Dockerfile.lambda`) para o ECR se `AWS_ROLE_ARN` existir.
3. **Implantação** — **desligada** até se definir a variável de repositório
   `IMPLANTACAO_ATIVA=true`. Implanta um nó de cada vez (os outros dois
   mantêm a maioria) por SSH e depois atualiza o Lambda.

Para a implantação, cada instância `backend-X` precisa de dois ficheiros em
`/etc/banco/`: o `cluster.json` do Passo 3 e `backend-X.env` com
`NO_ID`, `PORTA`, `PGHOST`…`PGPASSWORD`, `SECRET_KEY`, `CHAVE_ADMIN` e
`CLUSTER_CONFIG=/config/cluster.json` — os segredos ficam na máquina, nunca no
git. No GitHub: segredos `SSH_HOST_A`/`B`/`C`, `SSH_USER`, `SSH_KEY`; variáveis
`AWS_ROLE_ARN`, `AWS_REGION`, `ECR_REGISTRY`.
