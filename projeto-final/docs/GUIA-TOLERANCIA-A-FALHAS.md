# Testar a tolerância a falhas, pela consola

Esta guia mostra como derrubar, isolar e atrasar nós do banco a partir da
consola, e como confirmar que nenhum dinheiro se perde nem se duplica. Tem duas
partes, com os mesmos testes:

- **[Parte A](#parte-a--num-só-portátil):** os três nós num só portátil, com o
  `docker compose`.
- **[Parte B](#parte-b--em-vários-portáteis-na-mesma-rede):** os nós espalhados
  por dois ou três portáteis na mesma rede. Cada falha pode ser provocada e
  observada a partir de qualquer um deles.
- **[Parte C](#parte-c--na-aws-um-nó-por-pessoa):** o cluster implantado na
  AWS, com cada pessoa responsável por um nó.

Todas as saídas das Partes A e B são de execuções reais, de 23 de novembro de
2026. A Parte B foi ensaiada num só portátil, com os três nós a falarem entre si
pelo IP da rede local. A Parte C ainda não tem saídas guardadas: escrevam-nas
aqui quando a correrem.

## Índice

- [O que é preciso](#o-que-é-preciso)
- [As ajudas da consola](#as-ajudas-da-consola)
- [Parte A — num só portátil](#parte-a--num-só-portátil)
- [Parte B — em vários portáteis, na mesma rede](#parte-b--em-vários-portáteis-na-mesma-rede)
- [Parte C — na AWS, um nó por pessoa](#parte-c--na-aws-um-nó-por-pessoa)
- [Problemas comuns](#problemas-comuns)

---

## O que é preciso

Em cada portátil:

| O quê | Para quê |
|---|---|
| Docker (com Compose v2) | Correr os nós, as bases e o balanceador |
| Este repositório, no mesmo commit em todos | Os nós têm de falar o mesmo protocolo |
| `bash` ou `zsh`, `curl` e `python3` | As ajudas da consola |

No Windows, usa o WSL 2 (Ubuntu) com o Docker Desktop: as ajudas são de `bash`.

Todos os comandos correm na pasta `projeto-final/`.

## As ajudas da consola

Cola este bloco em cada consola onde fores testar. Também podes guardá-lo num
ficheiro e fazer `source ajudas.sh`. Funciona em `bash` e em `zsh`.

Há duas variáveis:

- `BANCO` é o balanceador, por onde passam as operações.
- `NOS` são os três nós, consultados diretamente.

Por omissão, as duas apontam para este portátil (Parte A). Na Parte B, define-as
antes de colar o bloco (ver [B.7](#b7-as-ajudas-apontadas-para-a-rede)).

```bash
# --- banco: ajudas para os testes de tolerância a falhas (bash ou zsh) ---
BANCO=${BANCO:-http://localhost:8000}
[ -n "${NOS+x}" ] || NOS=(localhost:8001 localhost:8002 localhost:8003)

# Uma linha por nó: papel, epoch, líder e os três índices do log.
estado() {
  python3 - "${NOS[@]}" <<'PY'
import json, sys, urllib.request
for no in sys.argv[1:]:
    try:
        e = json.load(urllib.request.urlopen(f"http://{no}/interno/estado", timeout=1))
    except Exception:
        print(f"{no:<22} EM BAIXO")
        continue
    print(f"{no:<22} nó {e['no']}  {e['papel']:<9} epoch {e['epoch']:<3} líder {e['lider'] or '-':<2}"
          f" log {e['ultimo_indice']:<4} commit {e['indice_commit']:<4} aplicado {e['ultimo_aplicado']}")
PY
}

# Repete `estado` a cada meio segundo, até Ctrl+C.
vigiar() { while true; do clear; date '+%H:%M:%S'; estado; sleep 0.5; done; }

# Tira um campo de uma resposta JSON; se não o tiver (um erro), mostra-a inteira.
_json() { python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get(sys.argv[1], d))' "$1"; }

# Cria um utilizador e uma conta a zero; guarda TOKEN e CONTA nesta consola.
preparar() {
  local email="teste-$RANDOM$RANDOM@exemplo.pt"
  curl -s -X POST "$BANCO/auth/registo" -H 'Content-Type: application/json' \
    -d "{\"nome\":\"Teste\",\"email\":\"$email\",\"senha\":\"segredo-123\"}" >/dev/null
  TOKEN=$(curl -s -X POST "$BANCO/auth/login" -H 'Content-Type: application/json' \
    -d "{\"email\":\"$email\",\"senha\":\"segredo-123\"}" | _json token)
  CONTA=$(curl -s -X POST "$BANCO/contas" -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d "{\"saldo_inicial\":\"0.00\",\"op_id\":\"abrir-$RANDOM$RANDOM\"}" | _json conta)
  echo "utilizador $email, conta $CONTA"
}

# depositar 10.00 [op_id] — um pedido; mostra o corpo e o código HTTP.
depositar() {
  curl -s -w ' [%{http_code}]\n' -X POST "$BANCO/contas/$CONTA/deposito" \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d "{\"valor\":\"$1\",\"op_id\":\"${2:-dep-$RANDOM$RANDOM}\"}"
}

# rajada N — N depósitos de 1.00. Cada um repete-se com o MESMO op_id até
# dar 200, como faria um cliente bem-educado durante um failover.
rajada() {
  local i op codigo
  for i in $(seq 1 "$1"); do
    op="raj-$RANDOM$RANDOM-$i"
    while :; do
      codigo=$(curl -s -o /dev/null -w '%{http_code}' -m 3 -X POST "$BANCO/contas/$CONTA/deposito" \
        -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
        -d "{\"valor\":\"1.00\",\"op_id\":\"$op\"}")
      [ "$codigo" = 200 ] && break
      printf '[%s]' "$codigo"; sleep 0.2
    done
    printf '%s ' "$i"
  done
  echo
}

saldo() { curl -s "$BANCO/contas/$CONTA" -H "Authorization: Bearer $TOKEN" | _json saldo; }
auditoria() {
  [ -n "$TOKEN" ] || { echo "corre primeiro preparar: a auditoria exige sessão"; return 1; }
  curl -s "$BANCO/auditoria" -H "Authorization: Bearer $TOKEN"; echo
}

# falha <nó> '<json>' — injeção de falhas (só com FALHAS_ATIVAS=1).
#   falha localhost:8002 '{"tipo":"atraso","ms":300}'
#   falha localhost:8001 '{"tipo":"isolar","nos":["B","C"]}'
#   falha localhost:8001 '{"tipo":"limpar"}'
#   falha localhost:8001 '{"tipo":"derrubar"}'
falha() {
  curl -s -X POST "http://$1/admin/falha" -H 'Content-Type: application/json' -d "$2"; echo
}

# Derruba o primário (sem fechar nada, como um corte de luz) e mede quanto
# tempo passa até outro nó ser primário com um epoch maior.
failover() {
  python3 - "${NOS[@]}" <<'PY'
import json, sys, time, urllib.request
nos = sys.argv[1:]
def estado(no):
    try:
        return json.load(urllib.request.urlopen(f"http://{no}/interno/estado", timeout=0.3))
    except Exception:
        return None
primarios = [(no, e) for no in nos if (e := estado(no)) and e["papel"] == "primário"]
if not primarios:
    sys.exit("não há primário agora; espera uns segundos e repete")
alvo, antes = max(primarios, key=lambda p: p[1]["epoch"])
print(f"a derrubar o nó {antes['no']} ({alvo}), primário no epoch {antes['epoch']}")
pedido = urllib.request.Request(f"http://{alvo}/admin/falha", method="POST",
                                data=b'{"tipo":"derrubar"}',
                                headers={"Content-Type": "application/json"})
inicio = time.monotonic()
try:
    urllib.request.urlopen(pedido, timeout=1)
except Exception:
    pass                                   # morreu sem responder: é o esperado
while time.monotonic() - inicio < 15:
    for no in nos:
        if no == alvo:
            continue
        e = estado(no)
        if e and e["papel"] == "primário" and e["epoch"] > antes["epoch"]:
            print(f"novo primário: nó {e['no']} ({no}), epoch {e['epoch']}, "
                  f"{time.monotonic() - inicio:.2f} s depois")
            sys.exit()
    time.sleep(0.05)
sys.exit("ninguém assumiu em 15 s: há maioria de pé?")
PY
}
```

O que cada ajuda faz:

| Ajuda | O que faz |
|---|---|
| `estado` | Uma linha por nó: papel, `epoch`, líder e os índices do log (`log`, `commit`, `aplicado`) |
| `vigiar` | `estado` a cada meio segundo, até `Ctrl+C`. Deixa-o numa consola à parte |
| `preparar` | Cria um utilizador e uma conta a zero, e guarda `TOKEN` e `CONTA` nesta consola |
| `depositar 10.00 [op_id]` | Um depósito; mostra a resposta e o código HTTP |
| `rajada N` | N depósitos de 1,00. Cada um repete-se com o **mesmo** `op_id` até dar 200 |
| `saldo` | O saldo da conta de `preparar` |
| `auditoria` | Soma dos saldos contra soma do histórico, por moeda. Usa a sessão de `preparar` |
| `falha NÓ JSON` | Injeção de falhas num nó: atrasar, isolar, limpar, derrubar |
| `failover` | Derruba o primário e mede quanto tempo passa até haver outro |

> O `op_id` identifica uma intenção **no banco inteiro**, não numa conta. Ao
> repetir um `op_id` já usado, recebes o resultado guardado da primeira vez,
> mesmo que agora mandes outra conta ou outro valor. Para operações novas, não
> passes `op_id`: as ajudas geram um ao acaso.

---

## Parte A — num só portátil

### A.1 Levantar

```bash
export SECRET_KEY=$(openssl rand -hex 32)
docker compose up --build -d --wait
```

Exporta a `SECRET_KEY` na consola onde vais correr `docker compose kill` e
`docker compose start`: o Compose recusa-se a correr sem ela.

Ficam de pé:

| Porta | O quê |
|---|---|
| 8000 | O balanceador |
| 8001, 8002, 8003 | Os nós A, B e C |
| 8080 | O painel. O ecrã **Estado do cluster** mostra o mesmo que `estado` |

Abre duas consolas. Cola as ajudas nas duas. Na primeira, corre `vigiar` e
deixa-a à vista. A segunda é onde provocas as falhas.

```text
$ estado
localhost:8001         nó A  primário  epoch 2   líder A  log 34   commit 34   aplicado 34
localhost:8002         nó B  réplica   epoch 2   líder A  log 34   commit 34   aplicado 34
localhost:8003         nó C  réplica   epoch 2   líder A  log 34   commit 34   aplicado 34
```

Lê-se assim:

- Só um nó é primário, e os três concordam no `epoch` e no líder.
- `log` é a última entrada que o nó tem; `commit` é até onde a maioria já
  confirmou; `aplicado` é até onde o nó já mudou a sua base.
- Com os três de pé, os três números são iguais em todos.

### A.2 Queda do primário a meio de escritas (RF-09, RF-13, RNF-02, RNF-03)

**Prova:** outro nó assume em menos de 2 s. Nenhum depósito se perde nem se
duplica, mesmo os que estavam a meio quando o primário caiu.

```bash
preparar
rajada 40 &      # 40 depósitos de 1,00, em segundo plano
sleep 1
failover         # derruba o primário a meio da rajada
wait
saldo
```

```text
a derrubar o nó A (localhost:8001), primário no epoch 2
novo primário: nó C (localhost:8003), epoch 3, 1.11 s depois
1 2 3 4 5 6 [503][503][503]7 8 9 10 11 12 … 38 39 40
R$ 40,00
```

- Os `[503]` são o depósito 7 a chegar durante a eleição. O cliente repete-o
  com o mesmo `op_id` e o 7 entra **uma vez**.
- O saldo final é exatamente 40,00.
- O `failover` usa `POST /admin/falha {"tipo":"derrubar"}`: o processo morre
  sem fechar nada, como num corte de luz.

Para fazer a mesma queda por fora, sem a injeção de falhas:

```bash
docker compose kill no-a     # o nó que for primário: vê-o no `estado`
```

### A.3 O nó volta e alcança os outros (RF-12)

```bash
docker compose start no-a
sleep 4; estado
```

```text
localhost:8001         nó A  réplica   epoch 3   líder C  log 84   commit 84   aplicado 84
localhost:8002         nó B  réplica   epoch 3   líder C  log 84   commit 84   aplicado 84
localhost:8003         nó C  primário  epoch 3   líder C  log 84   commit 84   aplicado 84
```

O nó volta como **réplica**, mesmo que fosse primário antes de cair. Vê o
`epoch` maior e recebe o que lhe falta até ter o log dos outros.

### A.4 Sem maioria, ninguém escreve (RNF-06)

**Prova:** com um só nó de pé, nada se confirma, mas as leituras continuam,
marcadas como vindas de uma réplica. Quando volta um segundo nó, a mesma
escrita, com o mesmo `op_id`, entra uma vez.

```bash
preparar; depositar 10.00
docker compose kill no-b no-c         # fica só um de pé
sleep 3; estado
depositar 7.00 sem-maioria-1
curl -s -D - $BANCO/contas/$CONTA -H "Authorization: Bearer $TOKEN"; echo   # uma leitura
```

```text
localhost:8001         nó A  candidato epoch 17  líder B  log 182  commit 182  aplicado 182
localhost:8002         EM BAIXO
localhost:8003         EM BAIXO
{"erro":"sem_primario","mensagem":"nenhum nó se diz primário — há uma eleição a decorrer ou não há maioria; repetir com o mesmo op_id"} [503]
HTTP/1.1 200 OK
x-leitura-de-replica: A
…
{"conta":"conta-71574662-6",…,"saldo_centavos":1000,"saldo":"R$ 10,00",…}
```

Sozinho, o A candidata-se uma e outra vez e nunca ganha: precisa de 2 votos em
3. O balanceador não tem primário: recusa as escritas e manda as leituras ao
nó vivo com mais log aplicado, com o cabeçalho `X-Leitura-De-Replica`. O
painel mostra então um aviso: os dados podem vir atrasados, porque esse nó não
sabe se a maioria confirmou mais alguma coisa.

```bash
docker compose start no-b
sleep 4
depositar 7.00 sem-maioria-1      # o mesmo op_id
depositar 7.00 sem-maioria-1      # outra vez
saldo                             # R$ 17,00: os 7,00 entraram uma vez
docker compose start no-c
```

### A.5 Partição de rede: o primário isolado (RF-11)

**Prova:** um primário separado da maioria deixa de confirmar escritas. Os
outros dois elegem um primário novo, e o banco continua a escrever. Quando a
rede volta, o antigo passa a réplica e as três bases ficam iguais.

`isolar` corta, num nó, as mensagens de e para os nós indicados, nos dois
sentidos. A rede verdadeira não muda: o balanceador e tu continuam a falar com
todos.

```bash
preparar
estado | grep primário                                   # suponhamos: C, na 8003
falha localhost:8003 '{"tipo":"isolar","nos":["A","B"]}'
sleep 3; estado
depositar 3.00                                            # pelo balanceador
curl -s -w ' [%{http_code}]\n' -X POST localhost:8003/contas/$CONTA/deposito \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"valor":"1.00","op_id":"direto-ao-isolado-1"}'      # direto ao isolado
falha localhost:8003 '{"tipo":"limpar"}'
sleep 2; estado
```

```text
localhost:8001         nó A  primário  epoch 10  líder A  log 96   commit 96   aplicado 96
localhost:8002         nó B  réplica   epoch 10  líder A  log 96   commit 96   aplicado 96
localhost:8003         nó C  primário  epoch 9   líder C  log 95   commit 95   aplicado 95
{"conta":"conta-36549102-0","saldo_centavos":400,"moeda":"BRL","saldo":"R$ 4,00"} [200]
{"erro":"somente_leitura","mensagem":"o nó C não fala com a maioria há mais de um timeout de eleição; recusa escritas e continua a responder a leituras"} [503]
… depois de limpar:
localhost:8001         nó A  primário  epoch 10  líder A  log 98   commit 98   aplicado 98
localhost:8002         nó B  réplica   epoch 10  líder A  log 98   commit 98   aplicado 98
localhost:8003         nó C  réplica   epoch 10  líder A  log 98   commit 98   aplicado 98
```

- Durante a partição há **dois nós que se dizem primários**: C, no `epoch` 9, e
  A, no 10. Só o A confirma escritas: tem a maioria. O C recusa-as
  (`somente_leitura`).
- O balanceador escolhe o de `epoch` maior. Se o primário que tinha em cache
  responder `somente_leitura` ou `sem_quorum`, volta a procurar e repete no
  primário novo.

### A.6 Rede lenta (RNF-02)

**Prova:** um nó lento não atrasa o banco, porque basta a maioria. Se as duas
réplicas forem mais lentas que o `timeout_replicacao_ms` (500 ms), nada se
confirma, e a mesma escrita entra quando a rede melhora.

```bash
preparar
# o primário é o A? então as réplicas são B (8002) e C (8003)
falha localhost:8002 '{"tipo":"atraso","ms":400}'
depositar 1.00                 # demora ~0,5 s, mas entra

falha localhost:8003 '{"tipo":"atraso","ms":700}'
falha localhost:8002 '{"tipo":"atraso","ms":700}'
depositar 1.00 atraso-duplo-1  # 503 sem_quorum
falha localhost:8002 '{"tipo":"limpar"}'; falha localhost:8003 '{"tipo":"limpar"}'
depositar 1.00 atraso-duplo-1  # 200, e só uma vez
```

```text
{"erro":"sem_quorum","mensagem":"a maioria não confirmou a operação a tempo (500 ms); a entrada 101 ficou gravada por confirmar — repetir com o mesmo op_id"} [503]
{"conta":"conta-22017023-1","moeda":"BRL","saldo_centavos":100,"saldo":"R$ 1,00"} [200]
```

### A.7 Reiniciar tudo

**Prova:** o log e o voto de cada nó estão na sua base. Nada confirmado
depende da memória de um processo.

```bash
auditoria > /tmp/antes.json
docker compose restart no-a no-b no-c
sleep 6; estado
auditoria | diff - /tmp/antes.json && echo "nada mudou"
```

### A.8 As três bases ficaram iguais

Depois de qualquer teste, e com os três de pé, compara as bases. Cada uma dá o
número de contas, o total em centavos e uma impressão digital de todos os
saldos:

```bash
for b in a b c; do
  printf "postgres-$b  "
  docker compose exec -T postgres-$b psql -U banco -d banco -Atc \
    "SELECT count(*), sum(saldo_centavos), md5(string_agg(id || ':' || saldo_centavos, ',' ORDER BY id)) FROM conta"
done
```

```text
postgres-a  28|1659550|8f9c93021460ed39efe0f4b681310859
postgres-b  28|1659550|8f9c93021460ed39efe0f4b681310859
postgres-c  28|1659550|8f9c93021460ed39efe0f4b681310859
```

As três linhas têm de ser iguais. Se uma não for, espera dois segundos: um nó
que acabou de voltar pode ainda estar a aplicar.

### A.9 Tudo de uma vez

`provas/scripts/operacoes_api.py` faz 65 passos pela API, incluindo uma queda do
primário a meio de transferências concorrentes, e escreve o relatório em
`provas/api/sessao.md`:

```bash
python3 provas/scripts/operacoes_api.py
```

### A.10 Desligar

```bash
docker compose down -v      # -v apaga as bases; sem -v ficam para a próxima
```

---

## Parte B — em vários portáteis, na mesma rede

Cada portátil corre o seu nó e a sua base Postgres, como na AWS, mas na rede
local. Os nós falam entre si pelo IP de cada portátil. Os testes da Parte A
servem todos; muda só quem os provoca e a partir de onde.

### B.1 Escolher a distribuição

| Portáteis | Onde fica cada nó | Notas |
|---|---|---|
| **3** (recomendado) | A no 1.º, B no 2.º, C no 3.º | Desligar o Wi-Fi de um portátil é uma partição a sério |
| **2** | A e B no 1.º (portas 8001 e 8002), C no 2.º | Se o 1.º portátil cair, o C fica sozinho e sem maioria: é o teste A.4 |

O balanceador e o painel podem ficar em qualquer portátil, ou em vários: o
balanceador não guarda estado. Põe-nos num portátil que **não** vás desligar da
rede.

### B.2 A rede

1. Liga todos à **mesma rede**. As redes de convidados e muitas redes de
   universidade isolam os aparelhos uns dos outros. Se for o caso, usa o
   *hotspot* de um telemóvel.
2. Descobre o IP de cada portátil:

   | Sistema | Comando |
   |---|---|
   | Linux | `hostname -I` |
   | macOS | `ipconfig getifaddr en0` |
   | Windows | `ipconfig`, em «Endereço IPv4» |

3. Confirma que se veem: `ping IP_DO_OUTRO`, de cada um para os outros.
4. Abre na firewall as portas que cada portátil publica: a do nó (8001, ou 8001
   e 8002) e, onde estiverem, 8000 (balanceador) e 8080 (painel). No Windows, o
   Docker Desktop pede autorização na primeira vez. No Linux, as portas
   publicadas pelo Docker já passam o `ufw`.

### B.3 O que se combina uma vez, num portátil, e se passa aos outros

```bash
openssl rand -hex 32        # a SECRET_KEY: a mesma em todos
git rev-parse --short HEAD  # o commit: o mesmo em todos
```

A `SECRET_KEY` assina os tokens e deriva a chave do cluster, que as rotas entre
nós exigem. Com chaves diferentes, os nós recusam-se uns aos outros
(`403 nao_e_par_do_cluster`) e nunca elegem ninguém. É uma chave de laboratório:
pode ir por mensagem; não a uses noutro sítio.

Em **cada** consola, de cada portátil:

```bash
export SECRET_KEY=<a-chave-combinada>
export CHAVE_ADMIN=chave-admin-lan
```

### B.4 O mesmo `config/cluster.lan.json` em todos

Com três portáteis (troca os IPs pelos vossos):

```json
{"nos": [
  {"id": "A", "endereco": "192.168.1.10", "porta": 8001},
  {"id": "B", "endereco": "192.168.1.11", "porta": 8001},
  {"id": "C", "endereco": "192.168.1.12", "porta": 8001}],
 "heartbeat_ms": 150, "timeout_eleicao_ms": [800, 1500],
 "timeout_replicacao_ms": 500, "semente": 42}
```

Com dois portáteis, o A e o B têm o mesmo IP e portas diferentes:

```json
  {"id": "A", "endereco": "192.168.1.10", "porta": 8001},
  {"id": "B", "endereco": "192.168.1.10", "porta": 8002},
  {"id": "C", "endereco": "192.168.1.11", "porta": 8001}],
```

`endereco` e `porta` são por onde **os outros** chegam a esse nó: o IP do
portátil e a porta publicada. Dentro do contentor, o nó escuta sempre na 8001.

### B.5 Levantar o nó de cada portátil

Se o `docker compose` da Parte A estiver de pé neste portátil, desliga-o
primeiro (`docker compose down`): usa as mesmas portas.

Em cada portátil, muda só as três primeiras linhas:

```bash
NO=A          # B no 2.º portátil, C no 3.º
no=a          # o mesmo, em minúscula
PORTA=8001    # a porta deste nó no cluster.lan.json

docker network create banco-lan 2>/dev/null
docker build -t banco-no ./backend

docker run -d --name postgres-$no --network banco-lan \
  -e POSTGRES_DB=banco -e POSTGRES_USER=banco -e POSTGRES_PASSWORD=banco \
  -v "$PWD/backend/db/esquema.sql:/docker-entrypoint-initdb.d/esquema.sql:ro" \
  -v dados-lan-$no:/var/lib/postgresql/data \
  postgres:16-alpine

# espera pela base pronta (com -h: durante a criação do esquema ainda não aceita TCP)
until docker exec postgres-$no pg_isready -h 127.0.0.1 -U banco -d banco >/dev/null 2>&1; do sleep 1; done

docker run -d --name no-$no --network banco-lan -p $PORTA:8001 \
  -v "$PWD/config/cluster.lan.json:/config/cluster.json:ro" \
  -e CLUSTER_CONFIG=/config/cluster.json -e NO_ID=$NO -e PORTA=8001 \
  -e PGHOST=postgres-$no -e PGPORT=5432 -e PGDATABASE=banco \
  -e PGUSER=banco -e PGPASSWORD=banco \
  -e SECRET_KEY="$SECRET_KEY" -e CHAVE_ADMIN="$CHAVE_ADMIN" -e FALHAS_ATIVAS=1 \
  banco-no
```

- Com dois portáteis, o 1.º corre o bloco duas vezes: `NO=A no=a PORTA=8001` e
  depois `NO=B no=b PORTA=8002`.
- Não há `--restart`, de propósito: um nó derrubado fica em baixo até o
  levantares, como no `docker compose`.
- `FALHAS_ATIVAS=1` liga `POST /admin/falha`, que deixa quem chegar à porta
  derrubar o nó. Serve para o laboratório; não o ligues fora dele.

Assim que os três estão de pé, elegem um primário em um ou dois segundos.
Verifica em qualquer portátil:

```bash
curl -s http://192.168.1.10:8001/interno/estado; echo
```

### B.6 O balanceador e o painel

Num portátil, ou em vários:

```bash
docker build -t banco-balanceador ./balanceador
docker run -d --name balanceador --network banco-lan -p 8000:8000 \
  -v "$PWD/config/cluster.lan.json:/config/cluster.json:ro" \
  banco-balanceador

docker build -t banco-painel ./frontend
docker run -d --name painel --network banco-lan -p 8080:80 banco-painel
```

O contentor do balanceador tem de se chamar `balanceador`: o painel encaminha
`/api` para esse nome. O painel fica em `http://IP_DESTE_PORTÁTIL:8080`, e
qualquer portátil (ou telemóvel) da rede o pode abrir.

### B.7 As ajudas, apontadas para a rede

Em qualquer consola de qualquer portátil, **antes** de colar as ajudas:

```bash
NOS=(192.168.1.10:8001 192.168.1.11:8001 192.168.1.12:8001)   # os do cluster.lan.json
BANCO=http://192.168.1.10:8000                                 # onde está o balanceador
```

Daí para a frente, `estado`, `vigiar`, `preparar`, `rajada`, `falha` e
`failover` funcionam a partir de qualquer portátil, sobre o cluster inteiro.
Ensaio real, com os três nós no mesmo IP de rede e portas 9001–9003:

```text
172.24.19.63:9001      nó A  primário  epoch 4   líder A  log 1    commit 1    aplicado 1
172.24.19.63:9002      nó B  réplica   epoch 4   líder A  log 1    commit 1    aplicado 1
172.24.19.63:9003      nó C  réplica   epoch 4   líder A  log 1    commit 1    aplicado 1
a derrubar o nó A (172.24.19.63:9001), primário no epoch 4
novo primário: nó C (172.24.19.63:9003), epoch 5, 0.92 s depois
```

### B.8 Os testes, com várias pessoas

Os testes são os da Parte A. O que muda:

| Na Parte A | Na Parte B |
|---|---|
| `docker compose kill no-a` | No portátil do nó: `docker kill no-a`. De qualquer portátil: `falha IP:8001 '{"tipo":"derrubar"}'` ou `failover` |
| `docker compose start no-a` | No portátil do nó: `docker start no-a` |
| `falha localhost:8003 …` | `falha IP_DO_C:8001 …`, de qualquer portátil |
| `docker compose exec -T postgres-a psql …` | No portátil de cada nó: `docker exec -i postgres-a psql …` (a mesma consulta do A.8) |

Uma forma de dividir o trabalho, com três pessoas:

| Portátil | Quem | O quê |
|---|---|---|
| 1 | Observa | `vigiar`, e o painel no ecrã **Estado do cluster** |
| 2 | Escreve | `preparar`, `rajada 100` |
| 3 | Provoca | `failover`, `falha …`, ou desliga o próprio Wi-Fi |

#### Partição a sério: desligar o Wi-Fi de um portátil

Este é o teste que um só portátil não consegue fazer.

1. Com a `rajada` a correr no portátil 2, **desliga o Wi-Fi** do portátil do
   primário.
2. Os outros dois deixam de o ouvir. Em menos de 2 s elegem um primário novo,
   com o `epoch` + 1, e a `rajada` continua, com alguns `[503]` pelo meio.
3. No portátil desligado, o nó ainda se diz primário, mas recusa escritas
   (`somente_leitura`).
4. **Liga o Wi-Fi.** O nó vê o `epoch` maior, passa a réplica e recebe o que
   lhe falta.
5. No fim: o saldo é exatamente o número de depósitos da `rajada`, e a
   consulta do A.8, corrida em cada portátil, dá três linhas iguais.

Ao voltar à rede, o portátil costuma receber o mesmo IP. Se receber outro, o
`cluster.lan.json` já não serve: corrige-o em todos e reinicia os nós
(`docker restart no-a`, em cada portátil).

### B.9 Desligar

Em cada portátil:

```bash
docker rm -f no-$no postgres-$no balanceador painel 2>/dev/null
docker volume rm dados-lan-$no          # apaga a base deste nó
docker network rm banco-lan
```

Para recomeçar do zero, apaga as bases nos **três** portáteis. Não juntes uma
base de uma sessão anterior a bases novas: o nó que a trouxer pode ganhar a
eleição com esse log antigo e impô-lo aos outros.

---

## Parte C — na AWS, um nó por pessoa

O cluster na AWS está em duas contas, unidas por *VPC peering*
([`MUDANCAS-E-PENDENTES.md`](MUDANCAS-E-PENDENTES.md), secção 10). Cada pessoa
fica com um nó: abre a consola do seu `backend-X` e a do seu `postgres-X` com
**Connect → EC2 Instance Connect**.

Todos os blocos desta parte são para **copiar e colar sem mudar nada**: os
comandos descobrem sozinhos em que instância estão (`backend-a`, `backend-b`
ou `backend-c`). Onde um passo é na consola web da AWS, e não num terminal,
está escrito em texto.

Duas diferenças em relação às Partes A e B:

- Na AWS os nós arrancam **sem** `FALHAS_ATIVAS`, de propósito. `falha` e
  `failover` respondem `403 falhas_desativadas`. As quedas provocam-se com as
  ajudas desta parte (`derrubar_este`, `parar_este`) ou com **Stop instance**.
- Por isso, o atraso de rede (A.6) e a partição (A.5) não se fazem na AWS:
  ficam provados nas Partes A e B.

### C.1 Quem fica com que nó

| Nó | Conta AWS | `backend-X` (IP privado) | `postgres-X` (IP privado) | Pessoa |
|---|---|---|---|---|
| A | antiga | `172.31.12.211` | `172.31.12.43` | 1 |
| B | nova | `10.1.0.27` | `10.1.5.208` | 2 |
| C | nova | `10.1.31.94` | `10.1.26.86` | 3 |

> **Nota:** os IPs desta tabela estão escritos nos comandos abaixo. Se alguma
> instância foi relançada (não basta parar e arrancar), o IP privado mudou: aí
> é preciso trocá-lo nos comandos, no `/etc/banco/cluster.json` dos três
> backends e no `CLUSTER_CONFIG_JSON` do Lambda.

### C.2 Preparar a consola de cada `backend-X`

**Uma vez por instância**, cada pessoa cola isto na consola do seu `backend-X`.
Guarda em `~/ajudas.sh` os endereços do cluster, as
[ajudas da consola](#as-ajudas-da-consola) e as ajudas da AWS (mais abaixo),
lidas desta guia no GitHub:

```bash
{
  echo 'NOS=(172.31.12.211:8001 10.1.0.27:8001 10.1.31.94:8001)'
  echo 'BANCO=https://usrzoacnuosa6bhetxt5qa4mwe0ldjrk.lambda-url.us-east-2.on.aws'
  curl -fsSL https://raw.githubusercontent.com/PauloRPinedo/banco-distribuido/main/projeto-final/docs/GUIA-TOLERANCIA-A-FALHAS.md \
    | tr -d '\r' | awk '/^# --- banco: ajudas/{p=1} p&&/^```/{p=0} p'
} > ~/ajudas.sh
source ~/ajudas.sh
type derrubar_este >/dev/null 2>&1 && echo "ajudas prontas" || echo "FALTAM as ajudas da AWS: ver a nota"
```

> **Nota:** se disser `FALTAM as ajudas da AWS`, esta Parte C ainda não está
> no `main` do repositório do grupo. Cola então o mesmo bloco, mas a ler do
> fork onde ela já está:
>
> ```bash
> {
>   echo 'NOS=(172.31.12.211:8001 10.1.0.27:8001 10.1.31.94:8001)'
>   echo 'BANCO=https://usrzoacnuosa6bhetxt5qa4mwe0ldjrk.lambda-url.us-east-2.on.aws'
>   curl -fsSL https://raw.githubusercontent.com/JEFRY200307/banco-distribuido/main/projeto-final/docs/GUIA-TOLERANCIA-A-FALHAS.md \
>     | tr -d '\r' | awk '/^# --- banco: ajudas/{p=1} p&&/^```/{p=0} p'
> } > ~/ajudas.sh
> source ~/ajudas.sh
> type derrubar_este >/dev/null 2>&1 && echo "ajudas prontas" || echo "FALTAM as ajudas da AWS"
> ```

**Em cada consola nova** (cada vez que abrires o *Connect*), basta:

```bash
source ~/ajudas.sh
```

As ajudas da AWS, que o bloco acima já descarregou (estão aqui para se ver o
que fazem; não é preciso colá-las):

```bash
# --- banco: ajudas da AWS (Parte C) ---
# O nome do contentor backend-X desta instância, a correr ou parado.
este_backend() { docker ps -a --format '{{.Names}}' | grep '^backend-' | head -n1; }

# Para o backend-X desta instância sem aviso, como um corte de luz.
# Não volta sozinho: o --restart unless-stopped respeita uma paragem manual.
parar_este() { docker stop -t 0 "$(este_backend)"; }

# Volta a levantar o backend-X desta instância.
levantar_este() { docker start "$(este_backend)"; }

# Para o backend-X desta instância e mede quanto tempo passa até haver primário.
derrubar_este() {
  local nome
  nome=$(docker ps --format '{{.Names}}' | grep '^backend-' | head -n1)
  [ -n "$nome" ] || { echo "o backend-X desta instância não está a correr"; return 1; }
  python3 - "$nome" "${NOS[@]}" <<'PY'
import json, subprocess, sys, time, urllib.request
nome, nos = sys.argv[1], sys.argv[2:]
def estado(no):
    try:
        return json.load(urllib.request.urlopen(f"http://{no}/interno/estado", timeout=0.3))
    except Exception:
        return None
local = estado("127.0.0.1:8001") or {}
era_primario = local.get("papel") == "primário"
antes = max((e["epoch"] for no in nos if (e := estado(no))), default=0)
print(f"a parar {nome} (nó {local.get('no', '?')}, {local.get('papel', '?')}), epoch {antes}")
inicio = time.monotonic()
subprocess.run(["docker", "stop", "-t", "0", nome], check=True, capture_output=True)
while time.monotonic() - inicio < 15:
    for no in nos:
        e = estado(no)
        if not e or e["papel"] != "primário" or e["no"] == local.get("no"):
            continue
        if era_primario and e["epoch"] <= antes:
            continue
        print(f"primário: nó {e['no']} ({no}), epoch {e['epoch']}, "
              f"{time.monotonic() - inicio:.2f} s depois")
        sys.exit()
    time.sleep(0.05)
sys.exit("ninguém é primário 15 s depois: há maioria de pé?")
PY
}
```

### C.3 Antes de cada teste

Em cada `backend-X`:

```bash
source ~/ajudas.sh
docker ps --format 'table {{.Names}}\t{{.Status}}'
estado
```

O `backend-X` tem de estar `Up`, e o `estado` tem de mostrar um só
`primário`, com o mesmo `epoch` e o mesmo `líder` nos três.

> **Nota:** o primário muda a cada teste. Vejam no `estado` quem é antes de
> começar: é essa pessoa que provoca a queda nos testes C.5 e C.9.

### C.4 Como dividir o trabalho

| Papel | O que faz | Onde |
|---|---|---|
| Quem tem o primário | Provoca a queda (`derrubar_este`) | O seu `backend-X` |
| Quem escreve | `preparar`, `rajada`, `saldo` | Outro `backend-X` |
| Quem observa | `vigiar`, e no painel (Vercel) o ecrã **Estado do cluster** | O terceiro `backend-X` |

Quem escreve e quem observa podem ser a mesma pessoa, com duas consolas.

### C.5 Queda do primário a meio de escritas (RF-09, RF-13, RNF-02, RNF-03)

**Prova:** outro nó assume em menos de 2 s, e nenhum depósito se perde nem se
duplica.

1. Quem escreve:

   ```bash
   preparar
   rajada 100
   ```

2. **Enquanto a rajada corre** (vão aparecendo os números), quem tem o
   primário:

   ```bash
   derrubar_este
   ```

3. Quando a rajada acabar, quem escreve:

   ```bash
   saldo
   estado
   ```

   O saldo tem de ser exatamente **R$ 100,00**. O nó parado aparece
   `EM BAIXO`, e há outro primário com o `epoch` maior. Os `[503]` que
   aparecem na rajada são o cliente a repetir com o mesmo `op_id`: cada
   depósito entra uma vez.

### C.6 O nó volta e alcança os outros (RF-12)

Quem parou o seu nó no C.5:

```bash
levantar_este
sleep 4
estado
```

O nó volta como **réplica**, mesmo que fosse primário, e os três índices
(`log`, `commit`, `aplicado`) ficam iguais nos três.

### C.7 Queda de uma réplica

**Prova:** com uma réplica em baixo, o primário confirma com a outra, e as
escritas não dão erro.

1. Quem tem uma **réplica** (não o primário):

   ```bash
   derrubar_este
   ```

2. Quem escreve (sem `[503]` pelo meio):

   ```bash
   preparar
   rajada 10
   saldo
   ```

3. Quem parou:

   ```bash
   levantar_este
   ```

### C.8 Sem maioria, ninguém escreve (RNF-06)

**Prova:** com um só nó de pé, as escritas dão `503`, as leituras continuam
(marcadas como vindas de uma réplica), e a mesma escrita entra uma vez quando
volta a maioria.

1. Quem escreve:

   ```bash
   preparar
   depositar 10.00
   ```

2. As **outras duas** pessoas, cada uma no seu `backend-X`:

   ```bash
   parar_este
   ```

3. Quem escreve:

   ```bash
   sleep 3
   estado
   depositar 7.00 sem-maioria-1
   curl -s -D - "$BANCO/contas/$CONTA" -H "Authorization: Bearer $TOKEN"; echo
   ```

   O depósito dá `503 sem_primario`. A leitura dá `200`, com o cabeçalho
   `x-leitura-de-replica`.

4. **Uma** das duas que pararam:

   ```bash
   levantar_este
   ```

5. Quem escreve:

   ```bash
   sleep 4
   depositar 7.00 sem-maioria-1
   depositar 7.00 sem-maioria-1
   saldo
   ```

   O mesmo `op_id` duas vezes: o saldo é **R$ 17,00**, os 7,00 entraram uma
   vez.

6. A **outra** que parou:

   ```bash
   levantar_este
   ```

### C.9 Queda da máquina inteira

**Prova:** o mesmo que C.5, mas a falha é a instância, e não só o processo.

1. Quem escreve:

   ```bash
   preparar
   rajada 100
   ```

2. **Enquanto a rajada corre**, quem tem o primário, na consola web do EC2:
   seleciona o seu `backend-X` → **Instance state** → **Stop instance** (nunca
   *Terminate*). A consola do *Connect* dessa instância fecha-se: é normal.

3. Quem observa:

   ```bash
   vigiar
   ```

   Em poucos segundos, outro nó é primário (`Ctrl+C` para sair).

4. Quando a rajada acabar, quem escreve:

   ```bash
   saldo
   ```

   Tem de ser **R$ 100,00**.

5. Quem parou, na consola web do EC2: **Instance state** → **Start instance**.
   O contentor volta sozinho com a máquina e o nó entra como réplica. Passado
   um minuto, quem observa:

   ```bash
   estado
   ```

   O IP privado não muda ao parar e arrancar; o público sim, mas nada o usa.

### C.10 As três bases ficaram iguais

Depois de cada teste, com os três de pé, cada pessoa cola isto na consola do
seu **`postgres-X`** (não no `backend-X`). O mesmo comando serve nos três:

```bash
docker exec "$(docker ps --format '{{.Names}}' | grep '^postgres-')" psql -U banco -d banco -Atc \
  "SELECT count(*), sum(saldo_centavos), md5(string_agg(id || ':' || saldo_centavos, ',' ORDER BY id)) FROM conta"
```

As três linhas têm de ser iguais. Se uma não for, esperem dois segundos e
repitam: um nó que acabou de voltar pode ainda estar a aplicar.

E, em qualquer `backend-X` (depois de um `preparar` nessa consola, porque a
auditoria pede sessão):

```bash
auditoria
```

### C.11 Se um nó não volta

Na consola desse `backend-X`:

```bash
source ~/ajudas.sh
docker ps -a --format 'table {{.Names}}\t{{.Status}}'
docker logs --tail 40 "$(este_backend)"
```

| No log | Causa | O que fazer |
|---|---|---|
| `password authentication failed` | O `PGPASSWORD` de `/etc/banco/backend.env` não é a senha do `postgres-X` | Corrigir a linha `PGPASSWORD=` com `sudo nano /etc/banco/backend.env` e recriar o contentor (bloco abaixo) |
| `connection refused` para o Postgres | O `postgres-X` está parado | Na consola do `postgres-X`: `docker start "$(docker ps -a --format '{{.Names}}' \| grep '^postgres-')"` |
| `falta o campo …` / `não é JSON válido` | `/etc/banco/cluster.json` estragado | Voltar a escrevê-lo, igual nos três ([`GUIA-RECONSTRUIR-EC2.md`](GUIA-RECONSTRUIR-EC2.md), passo 4) |

Recriar o contentor (cada pessoa cola só o bloco do seu nó):

```bash
# nó A — em backend-a
docker rm -f backend-a
docker run -d --name backend-a -p 8001:8001 --restart unless-stopped \
  -v /etc/banco/cluster.json:/config/cluster.json:ro \
  --env-file /etc/banco/backend.env \
  -e NO_ID=A -e PGHOST=172.31.12.43 \
  backend
```

```bash
# nó B — em backend-b
docker rm -f backend-b
docker run -d --name backend-b -p 8001:8001 --restart unless-stopped \
  -v /etc/banco/cluster.json:/config/cluster.json:ro \
  --env-file /etc/banco/backend.env \
  -e NO_ID=B -e PGHOST=10.1.5.208 \
  backend
```

```bash
# nó C — em backend-c
docker rm -f backend-c
docker run -d --name backend-c -p 8001:8001 --restart unless-stopped \
  -v /etc/banco/cluster.json:/config/cluster.json:ro \
  --env-file /etc/banco/backend.env \
  -e NO_ID=C -e PGHOST=10.1.26.86 \
  backend
```

### C.12 Ao terminar

1. Em cada `backend-X`, confirmem que ficou de pé:

   ```bash
   source ~/ajudas.sh
   docker ps --format 'table {{.Names}}\t{{.Status}}'
   estado
   ```

2. Para não gastar, na consola web do EC2: seleciona as 6 instâncias →
   **Instance state** → **Stop instance** (não *Terminate*). Na sessão
   seguinte, **Start instance** nas 6: os contentores voltam sozinhos.

---

## Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `estado` diz `EM BAIXO` para um nó que está a correr | A firewall do portátil desse nó, ou uma rede que isola aparelhos | `ping`; abrir a porta; *hotspot* de telemóvel |
| Todos ficam `candidato`, com o `epoch` sempre a subir | `SECRET_KEY` diferente entre portáteis (as rotas entre nós respondem `403 nao_e_par_do_cluster`), ou `cluster.lan.json` com um IP errado | Comparar a chave e o ficheiro em todos; recriar o contentor do nó |
| `falha …` responde `403 falhas_desativadas` | O nó arrancou sem `FALHAS_ATIVAS=1` | Recriar o contentor com a variável. Na AWS é o esperado: usar `derrubar_este` (Parte C) |
| `503 sem_primario` em tudo | Há uma eleição a decorrer, ou não há maioria de pé | `estado`; levantar nós até haver 2 de 3 |
| O painel dá 502 | O balanceador não se chama `balanceador`, ou não está na rede `banco-lan` | Ver B.6 |
| Um nó sai logo depois de arrancar (`docker ps -a` mostra `Exited`) | Arrancou antes de o Postgres estar pronto | `docker logs no-a`; `docker start no-a`; da próxima vez, esperar com o `until … pg_isready` |
| `docker compose` recusa-se: «defina SECRET_KEY» | Consola nova, sem a variável | `export SECRET_KEY=…` (a mesma de antes, se as bases já existem) |
| Uma operação repetida devolve o resultado de outra conta | O `op_id` já tinha sido usado no banco | Usa `op_id` novos; ver a nota em [As ajudas da consola](#as-ajudas-da-consola) |
