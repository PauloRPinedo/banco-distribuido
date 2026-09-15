# Os dois portáteis

Como pôr o Protótipo 1 a correr em duas máquinas ao mesmo tempo, com as mesmas
contas nas duas.

**O que se vai montar:** cada portátil corre o seu nó e o seu painel. Os dois
escrevem na **mesma** base, que está na nuvem. Criar uma conta num portátil
fá-la aparecer no outro, porque não há duas cópias do dinheiro — há uma só.

```
  portátil A                      portátil B
  ┌──────────────────┐            ┌──────────────────┐
  │ painel   :8080   │            │ painel   :8080   │
  │ nó A     :8001   │            │ nó B     :8001   │
  └────────┬─────────┘            └─────────┬────────┘
           │                                │
           └────────────┐      ┌────────────┘
                        ▼      ▼
                 ┌────────────────────┐
                 │  PostgreSQL gerido │   uma base, uma verdade
                 └────────────────────┘
```

> **Isto não é replicação, e é importante não trocar as duas coisas na defesa.**
> Não há eleição de primário (RF-09) nem confirmação por maioria (RF-10): há dois
> servidores sem estado a escrever na mesma base, e quem garante a correção é o
> PostgreSQL, com os *locks* de linha. A base partilhada é um ponto único de
> falha — se ela cair, caem os dois nós. A tolerância a falhas é a etapa 2, e
> está em [`prototipo-2/`](../prototipo-2/), com três nós, e é lá que se
> demonstra matar um servidor e o serviço continuar.

---

## O que é preciso

Em cada portátil: Docker e `git`. Mais nada — nem Python, nem PostgreSQL.

Uma vez, para o grupo: uma base PostgreSQL gerida. Qualquer uma serve; os planos
gratuitos do [Neon](https://neon.tech) ou do [Supabase](https://supabase.com)
chegam de sobra para uma demonstração.

---

## Passo 1 — A base, uma vez

Criar a base no fornecedor escolhido e copiar a **linha de ligação**. Tem esta
forma, e o `?sslmode=require` no fim **não é opcional**:

```
postgresql://utilizador:senha@ep-xxxx.eu-central-1.aws.neon.tech/banco?sslmode=require
```

Carregar o esquema, **de um portátil qualquer, uma vez só**:

```bash
cd prototipo-1
BANCO_BD='postgresql://...?sslmode=require' ./scripts/preparar_base.sh
```

Correr isto uma segunda vez falha no `CREATE TABLE` e não altera nada. É de
propósito: apagar as contas a meio de um ensaio tinha de ser difícil.

> A linha de ligação tem uma senha lá dentro. **Não vai para o GitHub nem para o
> chat do grupo** — passa-se por onde se passam as senhas. O `.env` que a guarda
> está no `.gitignore`.

## Passo 2 — Cada portátil

Nos dois, a partir da pasta `prototipo-1/`:

```bash
cp .env.exemplo .env
```

Editar o `.env`:

| Portátil A | Portátil B |
|---|---|
| `NO_ID=A` | `NO_ID=B` |
| `BANCO_BD=<a mesma linha>` | `BANCO_BD=<a mesma linha>` |

A `BANCO_BD` é **a mesma nos dois** — é isso que os faz partilhar as contas. O
`NO_ID` é **diferente nos dois**: se os dois disserem `A`, o banco funciona na
mesma, mas os dois ecrãs ficam iguais e ninguém sabe qual é qual.

## Passo 3 — Levantar

Nos dois portáteis:

```bash
docker compose -f compose.nuvem.yaml up --build
```

E confirmar, em cada um:

```bash
curl localhost:8001/saude
# portátil A -> {"no":"A","estado":"de pé"}
# portátil B -> {"no":"B","estado":"de pé"}
```

O painel fica em <http://localhost:8080>, e o cabeçalho diz **nó A** ou **nó B**.

---

## A demonstração

Com os dois painéis abertos, um em cada portátil:

1. **No A:** separador *Contas* → criar `alice` com `100.00`.
2. **No B:** separador *Contas* → consultar `alice`. **Aparece, com R$ 100,00.**
   Nunca foi criada no B; está na base que os dois partilham.
3. **No B:** criar `bob` com `0` e transferir `25.00` de `alice` para `bob`.
4. **No A:** consultar `alice` → R$ 75,00. O extrato mostra a transferência que
   foi feita na outra máquina, com `bob` como contraparte.
5. **Nos dois:** separador *Auditoria* → o mesmo total, e divergência R$ 0,00.

O passo 5 é o que interessa: os dois nós concordam porque não há nada para
concordar — só há um sítio onde o dinheiro está.

**Para mostrar que a concorrência aguenta**, de um terceiro terminal, com
`<IP-A>` e `<IP-B>` os endereços dos dois portáteis:

```bash
# alice tem R$ 75,00; vinte saques de R$ 5,00 chegam aos dois nós ao mesmo tempo
for n in $(seq 1 10); do
  curl -s -X POST http://<IP-A>:8001/contas/alice/saque \
       -H 'Content-Type: application/json' \
       -d "{\"valor\":\"5.00\",\"op_id\":\"ensaio-a-$n\"}" -o /dev/null &
  curl -s -X POST http://<IP-B>:8001/contas/alice/saque \
       -H 'Content-Type: application/json' \
       -d "{\"valor\":\"5.00\",\"op_id\":\"ensaio-b-$n\"}" -o /dev/null &
done; wait

curl -s http://<IP-A>:8001/auditoria
```

Passam quinze e são recusados cinco, o saldo fica em zero, e a divergência
continua em R$ 0,00. É o mesmo que
`tests/integracao/teste_dois_nos.py` verifica automaticamente.

---

## Quando não arranca

| O que se vê | O que é | O que fazer |
|---|---|---|
| `required variable BANCO_BD is missing` | Não há `.env` | `cp .env.exemplo .env` e preencher |
| `required variable NO_ID is missing` | O `.env` não tem `NO_ID` | Pôr `NO_ID=A` ou `NO_ID=B` |
| `SSL connection has been closed unexpectedly` ou `server does not support SSL` | Falta `?sslmode=require` no fim da linha de ligação | Acrescentá-lo |
| `relation "conta" does not exist` | O esquema nunca foi carregado | Passo 1, `./scripts/preparar_base.sh` |
| `password authentication failed` | Senha errada, ou a linha foi copiada cortada | Copiar outra vez da consola do fornecedor |
| `Connection timed out` a ligar à base | O fornecedor tem uma lista de IPs permitidos | Autorizar os IPs dos dois portáteis na consola dele |
| Os dois ecrãs dizem **nó A** | Os dois `.env` têm `NO_ID=A` | Mudar um para `B` e `docker compose -f compose.nuvem.yaml up -d --force-recreate` |
| O painel responde 502 nos primeiros segundos | O nginx respondeu antes de o nó estar de pé | Esperar. O `healthcheck` já cobre o caso; se persistir, ver `docker compose -f compose.nuvem.yaml logs banco` |
| Cada clique demora quase um segundo | Latência até à base, e uma ligação TLS nova por pedido | É conhecido, está no README em "modos de falha". Uma base numa região mais perto reduz-o |
| Um portátil vê contas e o outro não | Os dois `.env` têm `BANCO_BD` diferentes | Comparar as duas linhas; têm de ser iguais, caractere a caractere |

---

## Deixar tudo como estava

Nos dois portáteis:

```bash
docker compose -f compose.nuvem.yaml down
```

A base fica com as contas do ensaio. Para a limpar sem a apagar:

```bash
psql "$BANCO_BD" -c 'TRUNCATE operacao, conta; ALTER SEQUENCE operacao_numero RESTART WITH 1;'
```

E, no fim do trabalho, apagar a base na consola do fornecedor — não fica nada a
correr à espera.

---

## Um portátil só

Para trabalhar sozinho não é preciso nada disto. O `compose.yaml` do lado traz o
seu próprio PostgreSQL e não fala com a rede:

```bash
docker compose up --build
```
