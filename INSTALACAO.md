# Guia de instalação

Como pôr este repositório a correr, de raiz, numa máquina limpa.

---

## Primeiro: que pasta é que faz o quê

É a pergunta que mais custa a quem chega, e a resposta poupa meia hora:

| Pasta | O que é | Tem cluster? |
|---|---|---|
| **`prototipo-1/`** | Um banco **correto**, num nó só. FastAPI + PostgreSQL + painel React | **Não.** Um nó, ou dois contra a mesma base — que não é replicação |
| **`prototipo-2/`** | Um banco que **sobrevive à queda de um servidor**. Biblioteca padrão + painel em HTML | **Sim.** Três nós, replicação por log, eleição, failover |
| **`projeto-final/`** | A pilha expandida: balanceador, autenticação, Docker, CI/CD, nuvem | Não — o `cluster/` de lá ainda é um esqueleto |

**O `config/cluster.json` só existe em `prototipo-2/`.** Se andas à procura dele
no Protótipo 1, não está lá, e não é engano: o Protótipo 1 não tem nós para
configurar.

---

## O que é preciso ter instalado

| Para | Precisa de |
|---|---|
| Correr os testes do domínio | **Python 3.10+**, e mais nada |
| Correr o Protótipo 2 inteiro | **Python 3.10+**, e mais nada |
| Correr o Protótipo 1 inteiro | **Docker** (traz o Python, o PostgreSQL e o Node lá dentro) |
| Mexer no painel do Protótipo 1 | **Node 20+** e `npm` |

```bash
git clone https://github.com/PauloRPinedo/banco-distribuido.git
cd banco-distribuido
```

---

## Protótipo 1 — o banco de um nó

### Correr os testes sem instalar nada

```bash
cd prototipo-1
python3 -m unittest discover -s tests
```

Passam 55 e saltam-se 56, **com o motivo escrito**. Os que se saltam são os que
precisam da pilha do servidor e de uma base de dados; os 55 que correm são os do
domínio, que é onde o dinheiro se move.

### Levantar tudo com um comando

```bash
cd prototipo-1
docker compose up --build
```

- Painel: <http://localhost:8080>
- API: <http://localhost:8001>

O `docker compose` levanta o PostgreSQL, espera que ele esteja **pronto a
responder** (e não só arrancado), levanta o nó, e só depois serve o painel.

Para experimentar pela linha de comando:

```bash
curl -X POST localhost:8001/contas -H 'Content-Type: application/json' \
     -d '{"conta":"alice","saldo_inicial":"100.00","op_id":"exemplo-01"}'
curl -X POST localhost:8001/contas -H 'Content-Type: application/json' \
     -d '{"conta":"bob","op_id":"exemplo-02"}'
curl -X POST localhost:8001/transferencias -H 'Content-Type: application/json' \
     -d '{"de":"alice","para":"bob","valor":"25.50","op_id":"exemplo-03"}'
curl localhost:8001/auditoria
```

> **O dinheiro viaja como texto**: `"25.50"`, nunca `25.50`. Um número JSON é
> recusado com `400 valor_invalido`, de propósito — ver `docs/SPECS.md` 6.

### Correr os 111 testes, com base de dados

```bash
cd prototipo-1
pip install -r requisitos.txt
createdb banco_teste
BANCO_BD_TESTE=postgresql:///banco_teste python3 -m unittest discover -s tests
```

A base de teste é apagada no início de cada teste, e por isso o código
**recusa-se a trabalhar numa base cujo nome não contenha `teste`**.

### Mexer no painel

```bash
cd prototipo-1/frontend
npm install
npm run dev        # servidor de desenvolvimento, com recarga
npm run build      # compila para dist/
```

Os tipos de letra estão em `public/tipos/` e são servidos pelo próprio painel —
não há pedidos a CDN nenhum, e por isso funciona sem internet.

---

## Protótipo 2 — o cluster de três nós

**É aqui que está a replicação e o failover.** Não precisa de instalar nada: o
`--armazem ficheiro` guarda o log em JSONL e dispensa o PostgreSQL.

### Correr os testes

```bash
cd prototipo-2
python3 -m unittest discover -s tests
```

305 testes, 27 saltados (os que exigem PostgreSQL). Inclui os 8 de failover.

### Três nós num computador só

Primeiro, o ficheiro de configuração:

```bash
cd prototipo-2
cp config/cluster.exemplo.json config/cluster.json
```

E editá-lo para três nós em `127.0.0.1`, com portas diferentes:

```json
{
  "nos": [
    {"id": "A", "endereco": "127.0.0.1", "porta": 8101},
    {"id": "B", "endereco": "127.0.0.1", "porta": 8102},
    {"id": "C", "endereco": "127.0.0.1", "porta": 8103}
  ],
  "heartbeat_ms": 150,
  "timeout_eleicao_ms": [800, 1500],
  "timeout_replicacao_ms": 500,
  "semente": 42
}
```

Depois, os três processos:

```bash
python3 -m banco.servidor --id A --porta 8101 --config config/cluster.json \
        --armazem ficheiro --dados dados/A --encaminhar-escritas &
python3 -m banco.servidor --id B --porta 8102 --config config/cluster.json \
        --armazem ficheiro --dados dados/B --encaminhar-escritas &
python3 -m banco.servidor --id C --porta 8103 --config config/cluster.json \
        --armazem ficheiro --dados dados/C --encaminhar-escritas &
```

> **Três coisas que custam tempo se forem esquecidas:**
>
> - **`--porta` por nó.** Não se deduz do `cluster.json`. Sem ela os três tentam
>   a 8001, dois morrem a dizer que o endereço está ocupado, e parece um erro de
>   protocolo quando é um erro de arranque.
> - **`--dados` por nó.** Sem isso os três escrevem no mesmo log e corrompem-no.
> - **`--encaminhar-escritas`** deixa qualquer nó aceitar uma escrita e
>   reencaminhá-la ao primário. Sem ela, escrever numa réplica dá `409`, e o
>   painel tem de estar apontado ao primário — que muda com o failover.

### Falar com o cluster

```bash
python3 -m banco.cli --cluster config/cluster.json estado
python3 -m banco.cli --cluster config/cluster.json criar-conta alice --saldo 100.00
python3 -m banco.cli --cluster config/cluster.json criar-conta bob --saldo 0
python3 -m banco.cli --cluster config/cluster.json transferir alice bob 25.00
python3 -m banco.cli --cluster config/cluster.json auditoria
```

> **`--cluster` vem antes do subcomando**, não depois. `banco.cli estado
> --cluster ...` dá erro de argumentos.

O `estado` mostra quem manda:

```
  NÓ  PAPEL     EPOCH  ÍNDICE  COMMIT  CONTAS
  A   primário      3       4       4       2
  B   réplica       3       4       4       2
  C   réplica       3       4       4       2
```

### O painel

O painel do Protótipo 2 é HTML estático e serve-se à parte:

```bash
cd prototipo-2/frontend
python3 -m http.server 9000 --bind 127.0.0.1
```

Abrir <http://localhost:9000> e, no campo **Endereço do banco**, pôr
`http://localhost:8101` — ou qualquer um dos três, que dá no mesmo por causa do
`--encaminhar-escritas`.

Quatro separadores: **Início** (saldos e auditoria), **Operações** (criar,
depositar, sacar, transferir), **Extrato**, e **Cluster** — o último mostra quem
é o primário, o `epoch` de cada nó e quem está em baixo.

### Ver o failover

```bash
# ver quem é o primário
python3 -m banco.cli --cluster config/cluster.json estado
python3 -m banco.cli --cluster config/cluster.json auditoria   # anotar o total

kill -9 <pid do primário>

python3 -m banco.cli --cluster config/cluster.json estado      # outro assumiu,
                                                               # com epoch maior
python3 -m banco.cli --cluster config/cluster.json transferir bob alice 10.00
python3 -m banco.cli --cluster config/cluster.json auditoria   # o total é o mesmo
```

E, ao voltar a levantar o nó morto com o mesmo comando de arranque, ele recupera
o log do disco e apanha o resto junto do primário.

### Em três portáteis na rede local

Um nó por máquina. O passo a passo, a *firewall*, a verificação prévia e a tabela
de sintoma → causa estão em [`prototipo-2/REDE.md`](prototipo-2/REDE.md).

> **Três nós, não dois.** A maioria é metade mais um: com dois nós a maioria
> continua a ser dois, e a queda de qualquer um deixa o outro em somente-leitura,
> sem failover para demonstrar.

---

## Projeto final

A pilha expandida, com balanceador, autenticação e implantação na nuvem:

```bash
cd projeto-final
cp config/cluster.exemplo.json config/cluster.json
SECRET_KEY=$(openssl rand -hex 32) docker compose up --build
```

O guião de implantação em AWS está em
[`projeto-final/GUIA-DESPLIEGUE.md`](projeto-final/GUIA-DESPLIEGUE.md), e a
decisão sobre a replicação da base em
[`projeto-final/GUIA-REPLICA-POSTGRESQL.md`](projeto-final/GUIA-REPLICA-POSTGRESQL.md).

---

## Quando não arranca

| O que se vê | Causa quase certa | O que fazer |
|---|---|---|
| `address already in use` ao arrancar um nó | Faltou `--porta`, ou já há algo naquela porta | Dar uma porta a cada nó |
| Dois nós com o mesmo log, ou saldos estranhos | Faltou `--dados` por nó | Uma pasta de dados por nó |
| `unrecognized arguments: --cluster` | O `--cluster` foi depois do subcomando | Pôr `--cluster` antes |
| `sem_quorum` em todas as escritas | Menos de dois nós de pé | `banco.cli estado` |
| `409 nao_sou_primario` | Escrita enviada a uma réplica sem `--encaminhar-escritas` | Acrescentar a bandeira, ou escrever no primário |
| Eleições sem fim, `epoch` a subir sozinho | Uma porta fechada **num só sentido** | `prototipo-2/scripts/verificar_rede.sh` |
| O painel do Protótipo 1 dá 502 nos primeiros segundos | O nginx respondeu antes de o nó estar de pé | Esperar; o `healthcheck` já cobre o caso |
| `relation "conta" does not exist` | O esquema nunca foi carregado | `psql "$BANCO_BD" -f db/esquema.sql` |
| Os testes de integração saltam-se todos | Não há `BANCO_BD_TESTE` nem a pilha instalada | É o comportamento esperado; ver acima |

---

## Onde está escrito o resto

| Documento | Para quê |
|---|---|
| [`docs/SPECS.md`](docs/SPECS.md) | Como o sistema funciona: protocolos, formatos, API, e os desvios com a sua justificação |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | O que cada etapa faz, e quem fez o quê |
| [`docs/CODESTYLE.md`](docs/CODESTYLE.md) | Estilo do código, do CLI e do painel |
| [`docs/CONVENCOES.md`](docs/CONVENCOES.md) | Convenções de trabalho no repositório |
| [`prototipo-2/REDE.md`](prototipo-2/REDE.md) | Pôr o cluster a correr em três portáteis |
