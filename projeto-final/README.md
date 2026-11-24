# Projeto final — o banco distribuído, pronto para a AWS

Terceira etapa do [Banco Distribuído](../README.md).

**Numa frase:** o banco do [Protótipo 2](../prototipo-2/README.md) — três nós,
cada um com a sua base PostgreSQL, um log replicado confirmado pela maioria,
eleição com `epoch` e failover automático — preparado para correr em
servidores reais da AWS: EC2 para os nós e o Postgres, Lambda para o
balanceador, Vercel para o painel.

**De onde vem este código.** Esta pasta tinha um *scaffolding* com o nó em
*stub* (todo o nó se dizia primário e nada se replicava). Foi substituído pelo
código do `prototipo-2/`, que já resolvia isso e o resto, com o que a
implantação na AWS pede a mais:

- as rotas entre nós (`/interno/replicar`, `/interno/votar`, `/interno/log`)
  exigem a chave do cluster, derivada da `SECRET_KEY` — na AWS a porta 8001
  estava aberta à Internet e um pedido forjado seria aceite (já está fechada,
  mas a chave continua a ser a proteção entre nós);
- `POST /admin/falha` só existe com `FALHAS_ATIVAS=1` (ligado no compose
  local, desligado na AWS);
- registar uma taxa de câmbio (`POST /admin/taxas`) exige a chave de operador
  `X-Chave-Admin`, e não só uma sessão;
- a guia de implantação dá a cada nó o `cluster.json` com os IPs privados dos
  outros (sem ele, cada nó arrancava sozinho);
- o CI/CD está em [`.github/workflows/projeto-final.yml`](../.github/workflows/projeto-final.yml),
  na raiz, onde o GitHub o lê.

**Com a versão do Jefferson.** O Jefferson tinha feito, à parte, outra versão
desta pasta (PR #3, em espanhol). Dela vieram, traduzidos e arrumados:

- o painel com aspeto de aplicação bancária: início com saldo e atalhos, um
  ecrã por operação, registo com termos, logótipo, instalável no telefone;
- o **número de conta** com agência e dígito verificador (`0001 / 12345678-9`),
  e transferir para outra pessoa pelo número, confirmando o titular antes;
- as guias de teste e de reconstrução dos EC2.

O protocolo dele (arrendamento a dois nós) e a recuperação de senha sem
verificação **não** vieram: o primeiro deixa haver dois primários num corte de
rede, a segunda deixa qualquer pessoa trocar a senha de outra.

O detalhe destas mudanças, a revisão problema a problema e a lista do que
falta estão em [`docs/MUDANCAS-E-PENDENTES.md`](docs/MUDANCAS-E-PENDENTES.md).

**Provado com este código** ([`provas/api/sessao.md`](provas/api/sessao.md),
23 de novembro de 2026): os 65 passos pela API certos, o primário morto com
`docker compose kill` a meio de transferências concorrentes, **C assumiu em
1,30 s**, nada confirmado se perdeu e as três bases ficaram com a mesma
impressão digital. As capturas do painel e a medição anterior (1,23 s) são do
Protótipo 2, em [`../prototipo-2/provas/`](../prototipo-2/provas/README.md).

**306 testes do backend passam** contra um PostgreSQL a sério — entre eles, sete
com três processos, três bases e `kill -9` do primário.

---

## Instalação

### O que é preciso

| Para | Precisa de |
|---|---|
| Correr o banco inteiro | Docker com Compose v2 |
| Correr os testes | Python 3.12 ou mais recente (os do domínio e do protocolo não pedem mais nada) |
| Os testes com base de dados | o anterior + Docker (ou um PostgreSQL 16 qualquer) |
| Mexer no painel fora do Docker | Node 20 e npm |

### Levantar os três nós

```bash
cd projeto-final
export SECRET_KEY=$(openssl rand -hex 32)
docker compose up --build -d --wait
```

O `--wait` devolve o controlo quando os oito contentores estão *healthy*: três
PostgreSQL, três nós, o balanceador e o painel. Uns segundos depois, um dos nós
já ganhou a eleição.

A `SECRET_KEY` assina os tokens de sessão e tem de ser igual nos três nós, para
que um token emitido por um continue válido depois de um failover. Sem ela, o
compose recusa-se a arrancar, de propósito. Fica exportada na sessão do
terminal porque `docker compose start` de um nó morto também precisa dela.

| Porta | O quê |
|---|---|
| `8080` | o painel |
| `8000` | o balanceador — é com ele que o cliente fala |
| `8001`, `8002`, `8003` | os nós A, B e C, diretamente |

Parar e apagar tudo, bases incluídas:

```bash
docker compose down -v
```

Sem `-v` as bases ficam nos volumes, e o banco volta como estava.

### Variáveis de ambiente de um nó

O `compose.yaml` já as define; só interessam a quem corre um nó à mão.

| Variável | Para quê | Por omissão |
|---|---|---|
| `SECRET_KEY` | Assinar os tokens e derivar a chave do cluster; igual em todos os nós | — (obrigatória) |
| `CHAVE_ADMIN` | A chave de operador de `POST /admin/taxas` (cabeçalho `X-Chave-Admin`) | nenhuma: a rota recusa sempre (o compose põe `chave-admin-local`) |
| `FALHAS_ATIVAS` | `1` liga `POST /admin/falha` | desligado (o compose liga-o) |
| `NO_ID` | A identidade do nó (`A`, `B`, `C`); é a do `--id` | `A` |
| `PORTA` | Onde o nó escuta; é a do `--porta` | `8001` |
| `CLUSTER_CONFIG` | Caminho do ficheiro com os nós e os tempos do protocolo | nenhum: o nó funciona sozinho, com maioria de um |
| `BANCO_BD` ou `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` | A base **deste** nó — cada nó tem a sua | `localhost:5432/banco`, utilizador `banco` |
| `BANCO_GATEWAY` | O outro banco das transferências externas | `simulado` |

O balanceador lê o mesmo `CLUSTER_CONFIG` (ou o JSON inteiro em
`CLUSTER_CONFIG_JSON`) para saber onde estão os nós.

### Um nó sem Docker

Para depurar um nó contra um PostgreSQL que já está a correr:

```bash
cd projeto-final
python3 -m venv .venv
.venv/bin/pip install -r backend/requisitos.txt
createdb banco && psql banco -f backend/db/esquema.sql
cd backend
SECRET_KEY=desenvolvimento BANCO_BD=postgresql:///banco \
  ../.venv/bin/python -m banco.servidor --id A --porta 8001
```

Sem `CLUSTER_CONFIG` é um banco de um nó só: elege-se a si próprio e confirma
cada escrita sozinho. Para três nós fora do Docker, cada um precisa da sua base
e de um `CLUSTER_CONFIG` com os endereços dos três — é o que
`tests/integracao/teste_cluster.py` faz.

### O painel em modo de desenvolvimento

```bash
cd projeto-final/frontend
npm ci
npm run dev        # Vite em :5173, com /api reencaminhado para o balanceador em :8000
```

Com o balanceador noutro sítio: `VITE_BALANCEADOR_URL=http://outro:8000 npm run dev`.

---

## Uso

### O painel

Em `http://localhost:8080`, uma página responsiva que ocupa sempre a janela:
no telemóvel, um cabeçalho com menu e uma coluna; no tablet, o conteúdo em
grelha; num portátil ou computador (1024px ou mais), uma barra lateral com
todos os destinos. Criar utilizador, entrar, e depois:

| Ecrã | O que se faz |
|---|---|
| **Início** | O saldo da conta principal (o olho esconde-o), atalhos, as contas como cartões |
| **Abrir conta** | Moeda, corrente / poupança / prazo fixo; o banco dá o número `0001 / 12345678-9` |
| **Depositar**, **Sacar** | Numa conta tua; mostra o saldo que ficou |
| **Transferir** | Entre as tuas contas (com câmbio se as moedas diferem), para outra pessoa pelo número (vê-se o titular antes), para outro banco |
| **Extrato** | Os movimentos, o mais recente primeiro, com o índice no log |
| **Consultar saldo** | O detalhe de uma conta: produto, juros, vencimento |
| **Auditoria** | O total por moeda, saldos contra histórico; creditar juros |
| **Estado do cluster** | Os três nós, atualizados a cada segundo: papel, `epoch`, índices, quem está em baixo |

A linha gráfica está em [`docs/LINHA-GRAFICA.md`](docs/LINHA-GRAFICA.md).

### Pela API, do princípio ao fim

O cliente fala sempre com o balanceador. O dinheiro viaja **como texto**
(`"25.00"`, nunca `25.00`) e cada escrita leva um `op_id` escolhido pelo cliente.

```bash
B=localhost:8000
J='Content-Type: application/json'

curl -s -X POST $B/auth/registo -H "$J" \
     -d '{"nome":"Ana","email":"ana@exemplo.pt","senha":"segredo-ana"}'
TOKEN=$(curl -s -X POST $B/auth/login -H "$J" \
     -d '{"email":"ana@exemplo.pt","senha":"segredo-ana"}' \
     | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')
A="Authorization: Bearer $TOKEN"

curl -s -X POST $B/contas -H "$J" -H "$A" \
     -d '{"conta":"ana-corrente","saldo_inicial":"100.00","op_id":"exemplo-01"}'
curl -s -X POST $B/contas -H "$J" -H "$A" \
     -d '{"conta":"ana-reserva","op_id":"exemplo-02"}'
curl -s -X POST $B/contas/ana-corrente/deposito -H "$J" \
     -d '{"valor":"25.50","op_id":"exemplo-03"}'
curl -s -X POST $B/transferencias -H "$J" -H "$A" \
     -d '{"de":"ana-corrente","para":"ana-reserva","valor":"30.00","op_id":"exemplo-04"}'
curl -s $B/contas/ana-corrente/extrato -H "$A"
curl -s $B/auditoria -H "$A"
```

Repetir qualquer destas escritas com o mesmo `op_id` — mesmo depois de o
primário mudar — devolve a resposta guardada e não move o dinheiro outra vez.

### Ver o failover

A guia completa, com uma rajada de depósitos durante a queda, partições,
atrasos e a comparação das três bases, num portátil ou em vários ligados pela
rede, está em [`docs/GUIA-TOLERANCIA-A-FALHAS.md`](docs/GUIA-TOLERANCIA-A-FALHAS.md).

```bash
curl -s localhost:8000/interno/estado          # quem é o primário ("no": "C", por exemplo)
docker compose kill no-c                       # mata-o (troca c pelo que for)
curl -s localhost:8000/interno/estado          # outro nó, com epoch maior
curl -s localhost:8000/auditoria -H "$A"       # o mesmo total de antes
docker compose start no-c                      # volta como réplica e põe-se em dia
```

No ecrã **Estado do cluster** do painel (menu → Ver mais) vê-se acontecer: o nó morto passa a "em baixo" e outro
fica primário em cerca de um segundo e meio.

Com **dois** nós em baixo não há maioria, e nenhuma escrita é confirmada. O
que acontece às leituras depende de quem sobra:

- se é o primário, continua primário mas recusa escritas com
  `503 somente_leitura`; as leituras continuam pelo balanceador;
- se é uma réplica, não consegue ser eleita; o balanceador não encontra
  primário e responde `503 sem_primario`, e as leituras só se fazem pedindo
  **diretamente** a esse nó (`:8001`, `:8002` ou `:8003`).

### Injetar falhas sem matar contentores

`POST /admin/falha`, feito a um nó diretamente, para provar partições. Só
existe com `FALHAS_ATIVAS=1`, que o `compose.yaml` liga; na AWS fica
desligado e responde `403 falhas_desativadas`:

```bash
curl -s -X POST localhost:8001/admin/falha -H 'Content-Type: application/json' \
     -d '{"tipo":"isolar","nos":["B","C"]}'     # A deixa de falar com B e C
curl -s -X POST localhost:8001/admin/falha -H 'Content-Type: application/json' \
     -d '{"tipo":"limpar"}'
```

Os tipos são `atraso` (com `ms`), `isolar` (com `nos`: as mensagens de e para
esses nós perdem-se nos dois sentidos), `derrubar` (o processo morre de
imediato, sem fechar nada) e `limpar`.

---

## Estrutura e funcionamento, em diagramas

Os diagramas estão em [Mermaid](https://mermaid.js.org/): o GitHub desenha-os, e
como são texto mudam no mesmo commit que o código que descrevem.

### 1. As peças e por onde passa um pedido

```mermaid
flowchart LR
    U(["Navegador"]) -->|":8080"| P["Painel<br/>React + nginx"]
    CLI(["curl / outro cliente"]) -->|":8000"| BAL
    P -->|"/api/* → :8000"| BAL["Balanceador<br/>encontra o primário"]

    BAL ==>|"todos os pedidos"| A
    BAL -.->|"GET /interno/estado"| B
    BAL -.->|"GET /interno/estado"| C

    subgraph cluster["Cluster: 3 nós, maioria = 2"]
        direction TB
        A["Nó A · primário<br/>FastAPI :8001"]
        B["Nó B · réplica<br/>FastAPI :8002"]
        C["Nó C · réplica<br/>FastAPI :8003"]
        A <-->|"/interno/replicar<br/>/interno/votar"| B
        A <-->|"/interno/replicar<br/>/interno/votar"| C
        B <-.->|"/interno/votar"| C
    end

    A --- PA[("PostgreSQL A")]
    B --- PB[("PostgreSQL B")]
    C --- PC[("PostgreSQL C")]
```

O cliente nunca escolhe um nó: fala com o balanceador, que pergunta aos três
quem é o primário e lhe manda tudo. Cada nó só fala com a **sua** base; as bases
não se conhecem. O que as mantém iguais é o protocolo entre os nós. O papel de
primário é de quem ganhar a eleição — aqui A, mas pode ser qualquer um.

### 2. As camadas de um nó

```mermaid
flowchart TB
    API["api/<br/>rotas FastAPI, tradução de erros, sessão"]
    SERV["servico/<br/>ServicoDeEscrita · ServicoDeConsultas · ServicoAutenticacao"]
    APL["servico/aplicador.py<br/>AplicadorPostgres"]
    CLU["cluster/<br/>No · Eleicao · LogDeReplicacao · Replicador<br/>ArmazemPostgres · InjetorDeFalhas"]
    REPO["repositorio/<br/>SQL das contas, operações, utilizadores, taxas"]
    DOM["dominio/<br/>Conta · Livro · Operacao e subclasses<br/>sem rede, sem disco, sem relógio"]
    BD[("PostgreSQL do nó")]
    OUT["outros nós"]

    API --> SERV
    SERV -->|"No.executar(op_id, operação)"| CLU
    CLU -->|"entrada confirmada"| APL
    SERV --> REPO
    APL --> REPO
    CLU -->|"log_replicado, estado_do_no"| BD
    REPO --> BD
    CLU <-->|"HTTP /interno/*"| OUT
    SERV -.->|"validar"| DOM
    APL -.->|"aplicar"| DOM
```

As setas apontam para dentro, e o domínio não aponta para lado nenhum. A escrita
entra pelo serviço, passa pelo `No` (que a replica) e só chega às tabelas pelo
`AplicadorPostgres` — que é o mesmo código no primário e nas réplicas.

### 3. O caminho de uma escrita

Uma transferência, do pedido à resposta. É `No.executar()` em
`cluster/no.py`.

```mermaid
sequenceDiagram
    autonumber
    actor Cli as Cliente
    participant Bal as Balanceador
    participant A as Nó A (primário)
    participant B as Nó B (réplica)
    participant C as Nó C (réplica)

    Cli->>Bal: POST /transferencias {de, para, valor, op_id}
    Bal->>A: reenvia ao primário em cache
    A->>A: sou primário e vejo a maioria?
    Note over A: reservar as chaves (as duas contas, o op_id); se outra escrita as tem, esperar por ela
    alt este op_id já foi aplicado
        A-->>Bal: a resposta guardada (o dinheiro não se move)
    else op_id novo
        A->>A: validar contra as tabelas (dono, saldo, moeda, prazo)
        A->>A: gravar a entrada no log_replicado (índice n, epoch e)
        Note over A: uma ronda leva n e as outras escritas que chegaram entretanto (até m)
        par replicação
            A->>B: POST /interno/replicar [entradas até m]
            B->>B: grava no seu log
            B-->>A: ok, tenho até m
        and
            A->>C: POST /interno/replicar [entradas até m]
            C-->>A: ok (ou não responde, ou responde depois)
        end
        Note over A: a primeira réplica que confirma faz a maioria: confirmadas
        A->>A: indice_commit = m
        A->>A: AplicadorPostgres.aplicar_lote(..m): contas + operações + ultimo_aplicado, numa transação
        A-->>Bal: 200 com a resposta, guardada para repetições
    end
    Bal-->>Cli: 200 (o nó diz X-Primario-Pronto: sim)
    A->>B: envio seguinte (commit = m)
    B->>B: aplica até m às suas tabelas, noutra thread
    A->>C: envio seguinte (commit = m)
    C->>C: aplica até m às suas tabelas, noutra thread
```

Se o primário já não o for, responde `409 nao_sou_primario` com o endereço do
provável primário; se a ligação falhar, o balanceador volta a perguntar quem é o
primário. Nos dois casos repete **uma vez**, com o mesmo `op_id` — e é por isso
que repetir é seguro. Se a maioria não responder dentro do prazo de replicação,
a resposta é `503 sem_quorum` e a entrada fica por confirmar até a maioria
voltar.

### 4. Os papéis de um nó

```mermaid
stateDiagram-v2
    [*] --> Replica: arranca sempre como réplica
    Replica --> Candidato: sem heartbeat durante 800–1500 ms (sorteado)<br/>epoch + 1, vota em si, pede votos
    Candidato --> Candidato: ninguém ganhou e o tempo voltou a esgotar<br/>epoch + 1, outra vez
    Candidato --> Primario: votos da maioria (2 de 3)<br/>grava uma entrada noop do seu epoch
    Candidato --> Replica: recebe heartbeat de um primário<br/>ou vê um epoch maior
    Primario --> Replica: vê um epoch maior (fencing)
    Replica --> Replica: heartbeat do primário: segue-o e aplica o confirmado

    Replica: Réplica
    Primario: Primário
```

Um nó só vota uma vez por `epoch`, e só num candidato com o log pelo menos tão
atualizado como o seu. Por isso o vencedor tem sempre tudo o que foi confirmado.

### 5. O failover

O primário C morre a meio do trabalho. Os tempos são os de
`config/cluster.exemplo.json`.

```mermaid
sequenceDiagram
    actor Cli as Cliente
    participant Bal as Balanceador
    participant A as Nó A
    participant B as Nó B
    participant C as Nó C (primário, epoch 2)

    C-xC: docker compose kill
    Cli->>Bal: POST /transferencias (op_id X)
    Bal-xC: a ligação falha
    Bal->>Bal: redescobre: ainda ninguém é primário
    Bal-->>Cli: 503 sem_primario: repete com o mesmo op_id
    Note over A,B: nenhum heartbeat de C
    A->>A: timeout (ex.: 900 ms): candidato, epoch 3
    A->>B: POST /interno/votar (epoch 3, o meu último índice)
    B-->>A: voto concedido (o log de A está tão em dia como o meu)
    Note over A: 2 votos de 3: primário do epoch 3
    A->>B: noop do epoch 3, replicada e confirmada
    Cli->>Bal: repete POST /transferencias (op_id X)
    Bal->>A: redescobre o primário: A
    alt X tinha chegado a ser confirmado por C
        A-->>Cli: a resposta guardada
    else X nunca foi confirmado
        A-->>Cli: aplica agora, uma vez só
    end
    C->>C: docker compose start: volta como réplica, epoch 2
    A->>C: heartbeat (epoch 3)
    C->>C: vê o epoch 3 e segue A
    C-->>A: o meu log diverge ou está atrás
    A->>C: as entradas em falta, a partir do que C tem confirmado
    Note over A,C: as três bases voltam a ser iguais
```

Na prova desta pasta ([`provas/api/sessao.md`](provas/api/sessao.md)) este
intervalo — da morte do primário à eleição do novo — durou 1,79 s; na do
Protótipo 2, 1,23 s.

### 6. O banco, em UML

O cliente do banco é o `Usuario`: não há uma entidade "pessoa" à parte. As
classes são as do domínio (`banco/dominio/`), mais as três que vivem à volta
dele: o utilizador, a taxa de câmbio e o outro banco.

```mermaid
classDiagram
    direction LR

    class Usuario {
        +UUID id
        +str nome
        +str email «único»
        +str hash_senha
        +float criado_em
    }

    class Conta {
        +str id «escolhido pelo cliente»
        +int saldo_centavos «≥ 0»
        +float criada_em
        +Moeda moeda
        +Produto produto
        +int taxa_juros_milionesimos «poupança e prazo fixo»
        +float ultimo_juros_em
        +float vence_em «só prazo fixo»
    }

    class Moeda {
        <<enumeration>>
        BRL
        USD
        PEN
    }

    class Produto {
        <<enumeration>>
        corrente
        poupanca
        prazo_fixo
    }

    class Movimento {
        +int indice
        +str tipo
        +int valor_centavos
        +str contraparte
        +int saldo_depois_centavos
        +float instante
    }

    class Livro {
        +existe(id) bool
        +obter(id) Conta
        +criar(...)
        +extrato(id) list~Movimento~
        +total_centavos() int
    }

    class Operacao {
        <<abstract>>
        +str tipo
        +contas_tocadas() tuple
        +validar(livro, instante)
        +aplicar(livro, indice, instante) dict
    }

    class CriarConta {
        +str conta
        +int saldo_inicial_centavos
        +str dono
        +Moeda moeda
        +Produto produto
        +int taxa_juros_milionesimos
        +int prazo_dias
    }
    class Deposito {
        +str conta
        +int valor_centavos
    }
    class Saque {
        +str conta
        +int valor_centavos
    }
    class Transferencia {
        +str de
        +str para
        +int valor_centavos
    }
    class Cambio {
        +str de
        +str para
        +int valor_centavos
        +int taxa_milionesimos
    }
    class Juros {
        +str conta
        +float ate
    }
    class TransferenciaExterna {
        +str de
        +str sistema_externo_id
        +int valor_centavos
    }
    class DesfechoExterno {
        +str conta
        +int valor_centavos
        +bool confirmada
        +str referencia_externa
        +str op_original
    }

    class TaxaCambio {
        +Moeda moeda_origem
        +Moeda moeda_destino
        +int taxa_milionesimos
        +float vigente_desde
    }

    class SistemaExterno {
        +str id
        +str nome
        +str codigo «único»
        +bool ativo
    }

    class EntradaDeLog {
        +int indice
        +int epoch
        +str op_id «único»
        +str tipo
        +dict dados
        +float instante
    }

    Usuario "1" --> "0..*" Conta : é dono de
    Conta --> Moeda
    Conta --> Produto
    Livro "1" o-- "0..*" Conta : contas
    Conta "1" *-- "0..*" Movimento : extrato

    Operacao <|-- CriarConta
    Operacao <|-- Deposito
    Operacao <|-- Saque
    Operacao <|-- Transferencia
    Operacao <|-- Cambio
    Operacao <|-- Juros
    Operacao <|-- TransferenciaExterna
    Operacao <|-- DesfechoExterno

    Operacao "0..*" --> "1..2" Conta : toca
    Cambio "0..*" --> "1" TaxaCambio : à taxa em vigor
    TransferenciaExterna "0..*" --> "1" SistemaExterno : para
    DesfechoExterno "0..1" --> "1" TransferenciaExterna : resolve
    EntradaDeLog "1" --> "1" Operacao : leva
```

Como ler as cardinalidades:

- Um utilizador tem **zero ou mais** contas; cada conta tem **exatamente um**
  dono, que vem do token e não do corpo do pedido.
- Uma operação toca **uma ou duas** contas: duas na transferência e no câmbio
  (origem e destino), uma em todas as outras. Uma conta é tocada por **zero ou
  mais** operações, e cada uma deixa um `Movimento` no seu extrato.
- O câmbio leva dentro de si a taxa que estava **em vigor** quando foi feito, e
  por isso repeti-lo depois de a taxa mudar dá o mesmo resultado.
- Uma transferência externa tem **no máximo um** desfecho: confirmada, ou
  devolvida à conta de origem.
- Cada entrada do log leva **uma** operação. As operações de dinheiro são estas
  oito; o log leva também três que não movem dinheiro (`RegistarUsuario`,
  `RegistarTaxa` e `Noop`, em `cluster/operacoes_de_sistema.py`).

### 7. As tabelas de cada nó

Cada nó tem uma cópia destas sete tabelas na sua própria base
([`backend/db/esquema.sql`](backend/db/esquema.sql)).

```mermaid
erDiagram
    USUARIO ||--o{ CONTA : "é dono de"
    CONTA |o--o{ OPERACAO : "origem"
    CONTA |o--o{ OPERACAO : "destino"
    SISTEMA_EXTERNO |o--o{ OPERACAO : "transferência externa"
    LOG_REPLICADO ||--o| OPERACAO : "op_id; numero = indice"

    USUARIO {
        UUID id PK
        VARCHAR nome
        VARCHAR email UK
        VARCHAR hash_senha
        FLOAT8 criado_em
    }
    CONTA {
        VARCHAR id PK
        UUID usuario_id FK
        BIGINT saldo_centavos "CHECK >= 0"
        FLOAT8 criada_em
        VARCHAR moeda "BRL, USD, PEN"
        VARCHAR produto "corrente, poupanca, prazo_fixo"
        INTEGER taxa_juros_milionesimos
        FLOAT8 ultimo_juros_em
        FLOAT8 vence_em
    }
    OPERACAO {
        VARCHAR op_id PK
        BIGINT numero UK "índice do log"
        VARCHAR tipo "8 tipos"
        VARCHAR conta_origem_id FK
        VARCHAR conta_destino_id FK
        BIGINT valor_centavos
        VARCHAR moeda_origem
        VARCHAR moeda_destino
        BIGINT taxa_milionesimos
        BIGINT valor_destino_centavos
        VARCHAR sistema_externo_id FK
        VARCHAR referencia_externa
        JSONB resposta "o corpo devolvido ao cliente"
        FLOAT8 instante
    }
    TAXA_CAMBIO {
        VARCHAR moeda_origem PK
        VARCHAR moeda_destino PK
        FLOAT8 vigente_desde PK
        BIGINT taxa_milionesimos
    }
    SISTEMA_EXTERNO {
        VARCHAR id PK
        VARCHAR nome
        VARCHAR codigo UK
        BOOLEAN ativo
    }
    LOG_REPLICADO {
        BIGINT indice PK
        BIGINT epoch
        VARCHAR op_id UK
        VARCHAR tipo
        JSONB dados
        FLOAT8 instante
    }
    ESTADO_DO_NO {
        VARCHAR no_id PK
        BIGINT epoch
        VARCHAR votou_em
        BIGINT indice_commit
        BIGINT ultimo_aplicado
    }
```

- `log_replicado` é a fonte da verdade; `conta`, `operacao`, `usuario` e
  `taxa_cambio` são o log confirmado já aplicado. A ligação entre os dois é o
  `op_id` (o mesmo nas duas tabelas) e `operacao.numero`, que é o índice da
  entrada no log — igual nos três nós.
- Nem toda a entrada do log gera uma linha em `operacao`: registar um
  utilizador, registar uma taxa e a `noop` mudam outras tabelas ou nenhuma.
- `estado_do_no` tem uma linha só: o `epoch` deste nó, em quem votou, até onde o
  log está confirmado e até onde já foi aplicado às tabelas.
- `taxa_cambio` não tem chave estrangeira: o câmbio lê a taxa em vigor e
  copia-a para a sua própria linha de `operacao`.

---

## Como funciona

**Uma regra:** o estado de um nó — as tabelas `conta`, `operacao`, `usuario`,
`taxa_cambio` — é o resultado de aplicar, por ordem de índice, as entradas
**confirmadas** do log replicado. O primário e as réplicas aplicam com a mesma
função, por isso três nós com o mesmo log confirmado têm as mesmas tabelas.

O caminho completo está no [diagrama 3](#3-o-caminho-de-uma-escrita); a
eleição e o failover nos diagramas [4](#4-os-papéis-de-um-nó) e [5](#5-o-failover).

- **Eleição.** Cada nó arranca como réplica. Sem heartbeat do primário durante um
  tempo sorteado entre 800 e 1500 ms, candidata-se com `epoch + 1` e pede votos.
  Ganha com a maioria. Um nó só vota num candidato com o log pelo menos tão
  atualizado como o seu — é isso que garante que o novo primário tem tudo o que
  foi confirmado.
- **Fencing.** Um primário antigo que volte tem um `epoch` menor: a primeira
  resposta de qualquer réplica despromove-o. Do lado minoritário de uma partição
  não se confirma nada, porque não há maioria.
- **Pronto.** Quem ganha uma eleição grava primeiro uma `noop` do seu `epoch`.
  Só depois de a confirmar e aplicar se diz `pronto` em `/interno/estado`, e só
  então o balanceador lhe manda pedidos. Até lá, uma leitura podia não ver uma
  escrita que o primário anterior já tinha prometido a um cliente. Se a
  primeira ronda da `noop` não tiver maioria, o primário volta a tentar a cada
  heartbeat; não fica à espera de uma escrita que o balanceador nunca lhe
  mandaria.
- **Tudo passa pelo log**, e não só o dinheiro: registar um utilizador e registar
  uma taxa de câmbio também — senão, depois de um failover, o utilizador não
  conseguiria entrar e os câmbios dariam valores diferentes. O que não é
  determinista (instante, ids, o sal do hash da senha) decide-se no primário e
  vai dentro da entrada.
- **Recuperação.** `estado_do_no.ultimo_aplicado` avança na mesma transação que
  aplica as entradas. Um nó que caia a meio volta e aplica o que estiver
  confirmado e por aplicar, antes de responder a quem quer que seja.
- **Escritas em grupo no primário.** Cada escrita reserva as chaves que toca
  (as contas, o número de uma conta nova, o email, o `op_id`) e só valida
  quando nenhuma outra escrita com essas chaves está a validar ou por aplicar:
  valida-se sempre contra o estado que as anteriores deixaram, e escritas de
  contas diferentes não esperam umas pelas outras. As que chegam juntas vão
  na mesma ronda de replicação, que acaba quando a **primeira** réplica
  confirma (com ela, há maioria), e aplicam-se numa só transação.
- **As réplicas confirmam ao gravar.** Respondem ao primário logo que têm as
  entradas no log, e aplicam-nas noutra thread. Cada uma recebe as mensagens
  do primário pela ordem em que ele as manda, e a mensagem monta-se quando
  sai: leva tudo o que lhe falta, sem fila a crescer se a réplica estiver em
  baixo.
- **As leituras vão todas ao primário** (o balanceador encarrega-se disso). As
  réplicas aplicam um heartbeat depois, e ler de uma delas podia devolver um
  saldo atrasado.

Os tempos estão em [`config/cluster.exemplo.json`](config/cluster.exemplo.json):
heartbeat a cada 150 ms, eleição entre 800 e 1500 ms, prazo de replicação de
500 ms. Com 3 nós, a maioria é 2: cai um e o banco continua a escrever; caem dois
e deixa de escrever.

---

## O que há aqui

```
projeto-final/
├── compose.yaml            3 × (nó + Postgres) + balanceador + painel
├── config/                 os nós e os tempos do protocolo, iguais em todos
├── backend/
│   ├── db/esquema.sql      tabelas do banco + log_replicado + estado_do_no
│   ├── banco/
│   │   ├── dominio/        regras do dinheiro, puras: sem rede, sem disco, sem relógio
│   │   ├── cluster/        o protocolo: nó, eleição, log, replicador, falhas injetadas
│   │   ├── servico/        validar uma escrita (escrita.py), aplicá-la (aplicador.py), ler
│   │   ├── repositorio/    SQL, e mais nada
│   │   ├── autenticacao/   hash da senha e token assinado
│   │   ├── integracoes/    o outro banco (simulado)
│   │   ├── api/            rotas FastAPI, internas incluídas
│   │   └── servidor.py     o arranque de um nó
│   └── tests/              unitarios/ e integracao/
├── balanceador/            descobre o primário e manda-lhe tudo; uvicorn ou Lambda
├── frontend/               React + Vite + React Router: um ecrã por operação (src/paginas/acoes)
├── provas/scripts/         a sessão de ponta a ponta pela API, e as capturas do painel
└── docs/                   implantação e reconstrução na AWS, guias de teste, linha gráfica, proposta
```

| Ficheiro do cluster | O que faz |
|---|---|
| `cluster/no.py` | Junta tudo: a ordem de uma escrita, o lado da réplica (`replicar`, `votar`), a `noop` ao assumir o mandato |
| `cluster/eleicao.py` | Papel, `epoch`, voto e as três condições para o conceder |
| `cluster/log_de_replicacao.py` | Índices, prefixo confirmado, truncagem de entradas divergentes (nunca abaixo do commit) |
| `cluster/replicacao.py` | O lado ativo: heartbeat e replicação no mesmo RPC, contagem da maioria, candidatura |
| `cluster/armazem_postgres.py` | O log e o voto na base do nó, duráveis antes de responder |
| `cluster/operacoes_de_sistema.py` | Registar utilizador, registar taxa, `noop` — o que não move dinheiro mas tem de estar igual nos três |
| `cluster/falhas.py` | Atrasar, isolar de outros nós, derrubar — para provar partições sem mexer na rede |
| `servico/aplicador.py` | Aplica uma entrada confirmada às tabelas, numa transação, com o ponteiro |

A regra de dependência: o domínio não conhece rede, disco nem relógio.

```bash
cd backend
python3 -c "import banco.dominio.operacoes"   # não toca em psycopg2 nem em fastapi
```

---

## A API

| Rota | Sessão | O que faz |
|---|---|---|
| `POST /auth/registo` `{nome, email, senha}` | — | Cria um utilizador (pelo log) |
| `POST /auth/login` `{email, senha}` | — | Devolve `{token}`; qualquer nó o valida |
| `POST /contas` `{saldo_inicial, op_id, conta?, moeda?, produto?, taxa_juros?, prazo_dias?}` | sim | Abre uma conta; o dono é quem tem a sessão. O primário sorteia o número (`agencia`, `numero`); sem `conta`, o id é `conta-<numero>` |
| `GET /contas` | sim | As contas de quem pede |
| `GET /contas/por-numero/{numero}` | sim | O titular (só o nome) e a moeda de um número, sem o saldo |
| `GET /contas/{id}`, `GET /contas/{id}/extrato` | dono | Saldo; movimentos pela ordem do log |
| `POST /contas/{id}/deposito` `{valor, op_id}` | — | Qualquer pessoa deposita; o saldo só vem na resposta para o dono |
| `POST /contas/{id}/saque` `{valor, op_id}` | dono | — |
| `POST /transferencias` `{de, para, valor, op_id}` | dono de `de` | Mesma moeda; `para` é o id ou o número. O saldo do destino só vem se a conta também for tua |
| `POST /transferencias/conversao` `{de, para, valor, op_id}` | dono de `de` | Entre moedas, à taxa em vigor; `para` também pode ser o número |
| `POST /transferencias/autotransferencia` `{de, para, valor, op_id}` | dono das duas | Entre contas próprias |
| `POST /transferencias/externa` `{de, sistema_externo_id, valor, op_id}` | dono de `de` | Débito, depois confirmação ou devolução. Se o outro banco não responder, `503 outro_banco_indisponivel` com o débito feito |
| `GET /auditoria` | sim | Soma dos saldos contra soma do histórico, por moeda |
| `GET /taxas/{origem}/{destino}` | — | A taxa de câmbio em vigor |
| `POST /admin/taxas` `{moeda_origem, moeda_destino, taxa}` | sim + `X-Chave-Admin` | Regista uma taxa nova (pelo log) |
| `POST /admin/juros` | sim | Credita os juros devidos até agora |
| `POST /admin/externas/reconciliar?idade_minima_s=30` | sim | Termina as transferências externas com débito e sem desfecho; o primário também o faz sozinho a cada 30 s |
| `GET /sistemas-externos` | — | Os bancos para onde se pode transferir |
| `GET /saude` | — | O nó está de pé, e com que papel |
| `GET /interno/estado`, `GET /interno/cluster` | — | Papel, `epoch`, líder e índices; o cluster inteiro |
| `GET /interno/log?desde=` | chave do cluster | O log |
| `POST /interno/replicar`, `POST /interno/votar` | chave do cluster (`X-Chave-Cluster`) | O protocolo, entre nós |
| `POST /admin/falha` `{tipo, ms?, nos?}` | só com `FALHAS_ATIVAS=1` | Injeção de falhas (RF-16) |

O token vai no cabeçalho `Authorization: Bearer <token>`. Os erros têm todos a
mesma forma, `{"erro": "...", "mensagem": "..."}`:
`valor_invalido` 400, `sem_sessao` / `credenciais_invalidas` 401, `proibido`
403, `conta_inexistente` 404, `conta_duplicada` / `moedas_diferentes` /
`conta_bloqueada` / `taxa_indisponivel` / `email_duplicado` / `numero_ocupado` 409,
`nao_sou_primario` 409 (com `primario_provavel`), `saldo_insuficiente` 422,
`sem_quorum` / `somente_leitura` / `sem_primario` 503. Um 503 durante um
failover quer dizer "repete com o mesmo `op_id`".

---

## Testes

```bash
cd projeto-final
python3 -m venv .venv
.venv/bin/pip install -r backend/requisitos.txt -r balanceador/requisitos.txt

# sem instalar nada: 193 correm, 113 saltam-se com o motivo escrito
(cd backend && python3 -m unittest discover -s tests)

# com a pilha mas sem base: 203 correm, os 103 que precisam de base saltam-se
(cd backend && ../.venv/bin/python -m unittest discover -s tests)

# com uma base descartável, os 306 — o nome tem de conter "teste"; o teste do cluster
# cria ao lado as bases <nome>_a, _b e _c
docker run -d --name banco-teste -p 55432:5432 -e POSTGRES_DB=banco_teste \
  -e POSTGRES_USER=banco -e POSTGRES_PASSWORD=banco postgres:16-alpine
(cd backend && BANCO_BD_TESTE=postgresql://banco:banco@localhost:55432/banco_teste \
  ../.venv/bin/python -m unittest discover -s tests)
docker rm -f banco-teste

# 15 do balanceador
(cd balanceador && ../.venv/bin/python -m unittest discover -s tests)

# o painel compila
(cd frontend && npm ci && npm run build)
```

| Ficheiro | Prova |
|---|---|
| `integracao/teste_cluster.py` | **Três processos, três bases, `kill -9` do primário**: um só primário; cada escrita nas três bases; failover com `epoch` maior dentro do orçamento; nada confirmado se perde; repetir o `op_id` não duplica; o morto volta e apanha; sem maioria não se escreve; o total não muda com o primário a morrer a meio de transferências |
| `unitarios/teste_no.py` | O mesmo, com três nós em memória e rede falsa: eleição, replicação, failover, partição sem *split-brain*, escrita por confirmar confirmada quando a maioria volta |
| `unitarios/teste_eleicao.py`, `teste_log_de_replicacao.py`, `teste_configuracao.py` | As peças do protocolo, uma a uma |
| `unitarios/teste_operacoes.py`, `teste_invariante.py`, `teste_produtos.py`, … | O domínio: operações, invariante do dinheiro, moedas e produtos |
| `integracao/teste_concorrencia.py`, `teste_idempotencia.py`, `teste_acesso.py`, `teste_produtos.py`, `teste_rotas.py` | A API contra uma base a sério |
| `integracao/teste_rotas_protegidas.py`, `unitarios/teste_chaves.py` | Replicação e voto forjados recusados com `403`; `/admin/falha` desligado por omissão; taxa nova sem chave de operador recusada |

As provas de ponta a ponta — uma sessão de 65 passos pela API com a queda do
primário a meio, e 21 capturas do painel com um failover ao vivo — estão,
a sessão em [`provas/api/sessao.md`](provas/api/sessao.md) (repete-se com
`python3 provas/scripts/operacoes_api.py`, com o compose de pé) e as capturas em
[`../prototipo-2/provas/`](../prototipo-2/provas/README.md).

**Uma nota honesta sobre o `teste_cluster.py`:** em 19 execuções seguidas,
uma falhou e as outras 18 passaram, e a falha não se repetiu nas 16 seguintes.
Não se ficou a saber qual dos sete testes foi — a saída dessa execução não foi
guardada. Pode ser um orçamento de tempo apertado com três processos Python na
mesma máquina, ou um caso do protocolo por descobrir; fica registado em vez de
esquecido.

---

## O que funciona e o que falta

**Funciona — provado nos testes e em [`provas/api/sessao.md`](provas/api/sessao.md):**

- [x] Eleição por voto com `epoch`; um só primário; réplicas sabem quem manda
- [x] Cada escrita confirmada pela maioria antes de responder (RF-10)
- [x] Failover automático em menos de 2 s (RNF-03): 1,30 s na prova guardada
- [x] Nada confirmado se perde; o total não muda com o primário a morrer a meio
      (RNF-01, RNF-02)
- [x] Repetir o `op_id` depois de um failover não duplica (RF-13)
- [x] O nó morto volta como réplica e apanha o que perdeu (RF-12)
- [x] Sem maioria, nenhuma escrita é confirmada; o primário que sobra continua
      a responder a leituras
- [x] Partição: o lado minoritário não confirma nada; o antigo primário
      despromove-se ao ver o `epoch` maior (teste em memória)
- [x] As três bases ficam com a mesma impressão digital
- [x] Utilizadores e taxas de câmbio replicados pelo log
- [x] Login e token validado em qualquer nó; dono da conta
- [x] Moedas, câmbio, autotransferência, poupança, prazo fixo, juros,
      transferência externa com devolução; auditoria por moeda (RF-19 a RF-25)
- [x] Balanceador que segue o primário (redescobre e repete uma vez); entre
      dois que se digam primários escolhe o de `epoch` maior, e numa partição
      deixa o antigo primário isolado e repete no novo
- [x] Número de conta com agência e dígito verificador, igual nos três nós;
      transferir pelo número, vendo o titular antes
- [x] Quem deposita numa conta alheia, ou transfere para ela, não fica a saber
      o saldo dela
- [x] Transferência externa sem desfecho (o outro banco não respondeu, ou o
      primário caiu a meio): `503 outro_banco_indisponivel` com o débito
      feito, e o primário termina-a sozinho a cada 30 s
      (`POST /admin/externas/reconciliar` para não esperar)
- [x] Sem primário, o balanceador lê da réplica mais adiantada e marca a
      resposta (`X-Leitura-De-Replica`); o painel avisa que os dados podem vir
      atrasados. As escritas continuam paradas
- [x] `/auditoria` exige sessão
- [x] Painel responsivo (de 360px a 1920px), um ecrã por operação, com o estado do cluster ao vivo; percorrido de ponta a ponta num navegador (registo, abrir
      conta, depositar, transferir por número, extrato, auditoria, cluster)
- [x] Rotas entre nós com a chave do cluster; `/admin/falha` desligado fora do
      compose; taxas só com a chave de operador
- [x] CI na raiz: testes com Postgres (cluster incluído), balanceador, build do
      painel e publicação das imagens; implantação atrás de `IMPLANTACAO_ATIVA`

**Falta:**

- [ ] **Implantado na AWS (23 de novembro), mas as provas ainda não se
      repetiram lá.** Os três nós (`c3f1cb9`) estão em duas contas unidas por
      *VPC peering* e elegem um só primário; o Lambda chega-lhes por IP privado
      e a porta 8001 já não está aberta à Internet (secção 10 de
      [`docs/MUDANCAS-E-PENDENTES.md`](docs/MUDANCAS-E-PENDENTES.md)). Falta o
      percurso no painel, a queda do primário, o total de dinheiro e a
      impressão digital das bases, com a
      [Parte C da guia de tolerância a falhas](docs/GUIA-TOLERANCIA-A-FALHAS.md#parte-c--na-aws-um-nó-por-pessoa).
- [ ] A implantação pelo CI continua desligada: na AWS há um só
      `/etc/banco/backend.env` comum, e o workflow espera um
      `backend-X.env` por nó, com `NO_ID` e `PGHOST`.
- [ ] Não há recuperação de senha. Sem servidor de email não há como provar
      que quem a pede é o dono do email.
- [ ] O painel não abre sem rede (não há *service worker*, de propósito), e
      ainda não tem testes automáticos próprios: foi verificado com um
      percurso num navegador, não com uma suite no CI.
- [ ] Os segredos que estiveram no git saíram do `main` do GitHub (com
      *force-push*), mas continuam em `refs/pull/1` e `refs/pull/2`, e a AWS
      manteve as senhas que já tinha. Não se rodam, por decisão: é um projeto
      de teste.
- [ ] Os IPs privados do cluster estão escritos no `cluster.json` de cada nó,
      no `CLUSTER_CONFIG_JSON` do Lambda e na Parte C da guia: se uma instância
      for relançada (não basta pará-la), têm de se mudar nos três sítios.
- [ ] Sem *snapshots*, de propósito: um nó que esteve muito tempo em baixo
      recebe o log em lotes, uma ronda de heartbeat de cada vez. Com o volume
      de uma demonstração, isso são segundos; só faria falta com milhões de
      entradas.
- [ ] Não há papéis de utilizador, de propósito: as taxas pedem a chave de
      operador (um segredo partilhado, não uma pessoa), e o *tick* de juros e a
      reconciliação correm com qualquer sessão, porque são idempotentes e só
      fazem o que já é devido.
- [ ] O `teste_cluster.py` falhou uma vez em 70 execuções, depois das
      correções: uma réplica não aplicou uma transferência durante 5 s. Não se
      sabe porquê; os testes do cluster guardam agora o estado e o registo de
      cada nó quando falham. Com a máquina carregada, falha às vezes por
      timeouts (usa eleições de 150–300 ms).
- [ ] **RNF-04 não se cumpre; RNF-05 só até 8 clientes.** Medido no
      portátil, com a pilha toda no `docker compose`: **87 escritas por
      segundo** pelo balanceador e 110 diretas ao primário, com 32 clientes (a
      meta é 500); p99 de 50 ms com um cliente, abaixo de 200 ms até 8
      clientes, 612 ms com 32. As leituras chegam a 208 por segundo pelo
      balanceador e 317 diretas
      ([`provas/desempenho/medicao.md`](provas/desempenho/medicao.md)). O
      limite agora é o processo Python do primário: ~10–14 ms de CPU por
      escrita (FastAPI e ~15 idas à base), num só núcleo por causa do GIL.
      Antes destas correções eram ~10 escritas/s (secção 9 de
      `docs/MUDANCAS-E-PENDENTES.md`).

---

## Próximos passos propostos

| # | Proposta | Porquê |
|---|---|---|
| 1 | Menos idas à base por escrita (o fim do log em memória; deduplicar e validar com a mesma ligação) e separar a API HTTP do nó em vários processos | O limite das escritas (~100/s) é a CPU do processo Python do primário (RNF-04) |
| 2 | Repetir as provas na AWS (Parte C da `docs/GUIA-TOLERANCIA-A-FALHAS.md`) e guardar as saídas na guia | O cluster já está implantado, mas ainda não se provou lá |
| 3 | Ligar a implantação pelo CI (um `backend-X.env` por nó, segredos SSH, porta 22) | Hoje implanta-se à mão |
