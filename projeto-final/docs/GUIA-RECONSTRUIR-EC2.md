# Trocar o que corre nos EC2 por esta versão

Adaptado da guia de reconstrução do Jefferson (`GUIA-REBUILD-EC2.md`, na versão
dele). Os passos para lançar as instâncias de raiz estão em
[`GUIA-IMPLANTACAO.md`](GUIA-IMPLANTACAO.md). Esta guia serve para trocar o que
**já corre** nos backends por esta versão.

> **Atenção: as bases têm de ser recriadas.** A versão que está hoje na AWS usa
> outro esquema, com tabelas `cuenta`, `log_replicacion` e um protocolo de
> arrendamento a dois. Esta versão usa `conta`, `log_replicado` e
> `estado_do_no`, e o log de cada nó tem de começar vazio e igual nos três. Não
> há migração: os utilizadores e as contas de teste perdem-se. Se algum dado
> importar, exporta-o antes (passo 2).

Os passos 1 a 4 fazem-se nos três pares `postgres-X` / `backend-X`. O passo 5
faz-se uma vez.

## 1. Antes de entrar nos EC2

- O código desta versão tem de estar no GitHub, em `PauloRPinedo/banco-distribuido`.
  A instância só vê o que já foi enviado.
- Tem à mão os IPs **privados** dos três backends e dos três Postgres. Ver
  [`INVENTARIO-INSTANCIAS.md`](INVENTARIO-INSTANCIAS.md).
- Os três backends têm de se alcançar por IP privado, na porta 8001. Se estão
  em VPCs diferentes (endereços `172.31.x` num e `10.1.x` noutro), sem
  *peering* não se alcançam. Põe os três na mesma VPC.

## 2. Guardar as variáveis e, se for preciso, os dados

Em cada `backend-X` (**Connect** → **EC2 Instance Connect**):

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
docker inspect backend-a --format '{{range .Config.Env}}{{println .}}{{end}}'
```

Anota `SECRET_KEY`, `PGHOST` e `PGPASSWORD`. Vale mais gerar uma `SECRET_KEY`
nova (`openssl rand -hex 32`), igual nos três: as antigas estiveram no histórico
do git. Gera também uma `CHAVE_ADMIN`.

Se quiseres guardar os dados da versão anterior, em cada `postgres-X`:

```bash
docker exec postgres-a pg_dump -U banco banco > ~/antes-da-troca.sql
```

## 3. Recriar o Postgres com o esquema desta versão

Em cada `postgres-X`, com o `esquema.sql` desta versão (cola o conteúdo de
`projeto-final/backend/db/esquema.sql`):

```bash
cat > ~/esquema.sql <<'SQL'
(o conteúdo inteiro de projeto-final/backend/db/esquema.sql)
SQL

docker rm -f postgres-a
docker volume prune -f        # apaga o volume da base antiga
docker run -d --name postgres-a -p 5432:5432 \
  --restart unless-stopped --memory=512m \
  -e POSTGRES_DB=banco -e POSTGRES_USER=banco -e POSTGRES_PASSWORD='<senha-nova>' \
  -v ~/esquema.sql:/docker-entrypoint-initdb.d/esquema.sql:ro \
  postgres:16-alpine

docker exec postgres-a psql -U banco -d banco -c '\dt'
```

O `\dt` tem de listar `conta`, `log_replicado`, `estado_do_no`, `operacao`,
`taxa_cambio`, `sistema_externo` e `usuario`.

## 4. Reconstruir o backend

Em cada `backend-X`:

```bash
cd ~/banco-distribuido
git remote set-url origin https://github.com/PauloRPinedo/banco-distribuido.git
git fetch origin && git checkout main && git reset --hard origin/main
cd projeto-final/backend
docker build -t backend .
```

O `git reset --hard` é de propósito: o histórico foi reescrito para tirar os
segredos, e um `git pull` sobre o clone antigo falha. O `remote` volta ao
repositório do grupo, e não ao fork de um de nós.

O mesmo `cluster.json` nas três instâncias, com os IPs privados dos três
backends:

```bash
sudo mkdir -p /etc/banco
sudo tee /etc/banco/cluster.json >/dev/null <<'JSON'
{"nos": [
  {"id": "A", "endereco": "<IP_PRIVADO_backend-a>", "porta": 8001},
  {"id": "B", "endereco": "<IP_PRIVADO_backend-b>", "porta": 8001},
  {"id": "C", "endereco": "<IP_PRIVADO_backend-c>", "porta": 8001}],
 "heartbeat_ms": 150, "timeout_eleicao_ms": [800, 1500],
 "timeout_replicacao_ms": 500, "semente": 42}
JSON

docker rm -f backend-a
docker run -d --name backend-a -p 8001:8001 --restart unless-stopped \
  -v /etc/banco/cluster.json:/config/cluster.json:ro \
  -e CLUSTER_CONFIG=/config/cluster.json \
  -e NO_ID=A -e PORTA=8001 \
  -e PGHOST=<IP_PRIVADO_postgres-a> -e PGPORT=5432 -e PGDATABASE=banco \
  -e PGUSER=banco -e PGPASSWORD='<senha-nova>' \
  -e SECRET_KEY='<a-mesma-nos-tres>' -e CHAVE_ADMIN='<a-mesma-nos-tres>' \
  backend
```

Em B e C muda `NO_ID`, o nome do contentor e o `PGHOST`. As variáveis da versão
anterior (`PARES`, `URL_PROPIA`, `ROL`, `NODO_ID`, `PUERTO`) já não existem.
Quem é primário decide-o a eleição, não uma variável.

Não ponhas `FALHAS_ATIVAS=1` na AWS. Essa variável liga `POST /admin/falha`, que
deixa qualquer pessoa derrubar um nó.

## 5. O balanceador e o painel

- **Lambda:** reconstrói a imagem a partir de `projeto-final/balanceador`
  (`GUIA-IMPLANTACAO.md`, Passo 4). Põe em `CLUSTER_CONFIG_JSON` o mesmo
  conteúdo do `cluster.json`.
- **Vercel:** *root directory* `projeto-final/frontend`. Se a Function URL
  mudou, atualiza `frontend/vercel.json`.

## 6. Verificar

Em cada backend:

```bash
curl -sS http://127.0.0.1:8001/interno/estado
```

Tem de haver exatamente um `"papel":"primário"`, com o mesmo `epoch` e o mesmo
`lider` nos três. Depois segue o
[Passo 6 da `GUIA-IMPLANTACAO.md`](GUIA-IMPLANTACAO.md#passo-6--verificar-de-ponta-a-ponta).
