# Protótipo 1 — Um banco que não perde dinheiro

Primeira das três entregas do [Banco Distribuído](../README.md), **reaberta** em
setembro de 2026 para receber o PostgreSQL, a replicação entre laptops, a injeção
de falhas e um frontend web.

**Estado: 305 testes passam.** Sem instalar nada.

---

## Objetivo

De 2 a 3 servidores mantêm a mesma base de contas, e mesmo com um servidor a cair
no meio de uma transferência o dinheiro nunca é criado nem destruído.

O primário só responde ao cliente depois de a operação estar gravada em disco na
**maioria** dos nós. Se ele cai, os restantes elegem outro e o serviço continua.
Um primário antigo que regressa é rejeitado por ter um `epoch` menor.

---

## O que ficou pronto

- Criar conta, saldo, depositar, sacar, transferir, extrato
- Auditoria que compara **dois cálculos independentes**: a soma dos saldos e o
  total deduzido do log
- Dinheiro em centavos inteiros, nunca `float`
- **PostgreSQL** como armazém do log, com durabilidade declarada pela própria base
- Recuperação do estado por *replay* no arranque
- Deduplicação por `op_id`, reforçada por um índice único na base
- *Locks* por conta em ordem total, sem *deadlock*
- **Replicação com confirmação por maioria**, heartbeat e eleição com *fencing*
- **Injeção de falhas** com sessão de ensaio exclusiva entre operadores
- Servidor HTTP, cliente de linha de comando e **frontend web**

**Requisitos cobertos:** F-01 a F-12 · RF-01 a RF-14, RF-16, RF-17 · RNF-01 a
RNF-03, RNF-06, RNF-09, RNF-10

As decisões e o seu porquê estão em [`RELATORIO.md`](RELATORIO.md); os diagramas
em [`UML.md`](UML.md).

---

## Como executar

### Os testes, sem instalar nada

```bash
cd prototipo-1
python3 -m unittest discover -s tests        # 305 testes, 27 saltados
```

Os 27 saltados são os que precisam de uma base de dados a sério. Para os correr:

```bash
BANCO_BD_TESTE=postgresql:///banco_teste python3 -m unittest discover -s tests
```

### Um nó só

```bash
pip install -r requisitos.txt
./scripts/preparar_postgres.sh a
python3 -m banco.servidor --id A --porta 8001 --bd postgresql:///banco_a

python3 -m banco.cli criar-conta alice --saldo 100.00
python3 -m banco.cli transferir alice bob 25.00
python3 -m banco.cli auditoria
```

Sem PostgreSQL à mão, `--armazem ficheiro` volta ao log em JSONL e tudo funciona
na mesma.

### Três nós em dois laptops

O guia completo está em [`REDE.md`](REDE.md) — endereços, *firewall*, e a tabela
de sintoma→causa que poupa a tarde. O resumo:

**Sempre 3 nós, mesmo com 2 laptops** — o PC1 corre A, o PC2 corre B e C. Com 2
nós a maioria é 2, e a queda de qualquer um deixa o outro em somente leitura: não
haveria failover com escrita para demonstrar.

```bash
cp config/cluster.exemplo.json config/cluster.json   # e escrever os IPs reais
./scripts/verificar_rede.sh config/cluster.json      # ANTES de subir o cluster
./scripts/preparar_postgres.sh a                     # no PC1
./scripts/preparar_postgres.sh b c                   # no PC2

python3 -m banco.servidor --id A --porta 8001 --bd postgresql:///banco_a \
    --config config/cluster.json
```

O `verificar_rede.sh` não é cerimónia: com uma porta bloqueada pela *firewall*, os
sintomas — eleições sem fim, `epoch` a subir sozinho — parecem um erro de
protocolo e levam a procurar no sítio errado durante horas.

### Demonstrar o failover

```bash
python3 -m banco.cli --cluster config/cluster.json estado       # quem manda?
python3 -m banco.cli --cluster config/cluster.json auditoria    # anotar o total

python3 -m banco.cli --cluster config/cluster.json ensaio tomar --dono paulo
python3 -m banco.cli --cluster config/cluster.json falha derrubar --no C

python3 -m banco.cli --cluster config/cluster.json estado       # outro assumiu
python3 -m banco.cli --cluster config/cluster.json transferir alice bob 10.00
python3 -m banco.cli --cluster config/cluster.json auditoria    # o mesmo total
```

**A sessão de ensaio é exclusiva.** Enquanto um operador a tem, o outro recebe
`409` e não consegue injetar falha nenhuma — dois operadores a derrubar nós ao
mesmo tempo produzem um cluster sem maioria por acidente, e o que se vê no ecrã
deixa de ser a experiência que se estava a fazer.

### O frontend

Quatro ecrãs — Início, Operações, Extrato e Cluster — que são os mesmos do
desenho em [`frontend/desenho/`](frontend/desenho/).

```bash
cd frontend && python3 -m http.server 8080      # local
cloudflared tunnel --url http://localhost:8001  # expor um nó por HTTPS
```

Depois abre-se a página com `?api=<url do túnel>`, ou cola-se o endereço no botão
«Endereço». A URL do túnel muda a cada arranque, por isso não está gravada em lado
nenhum.

O ecrã **Cluster** mostra os três nós a partir de um endereço só: o nó
perguntado consulta os pares em paralelo (`GET /interno/cluster`) e diz quem
respondeu. Durante um failover vê-se o nó derrubado ficar coral, outro assumir, e
o total em circulação não se mexer.

Para isso o nó exposto arranca com `--encaminhar-escritas`: quando deixa de ser
primário, reenvia as escritas ao primário em vez de as recusar com um
`primario_provavel` que é um endereço de LAN, inalcançável do navegador.

---

## Divisão do trabalho

| Pessoa | Responsabilidade |
|---|---|
| **Jefferson Daniel Flores Montenegro** | **Domínio e persistência.** Centavos inteiros e formatação em reais, contas, as quatro operações como funções puras, invariante da soma, extrato, auditoria. O porto `ArmazemDeLog` e as três implementações — PostgreSQL, ficheiro e memória —, o esquema SQL, a recuperação por *replay* e a aplicação até ao `indice_commit` na réplica. |
| **Cristhian Jesus Maylle Briceño** | **Concorrência e núcleo distribuído.** *Locks* por conta em ordem total e o `lock` de estado do nó. Log de replicação e correspondência de índices, confirmação por maioria, *heartbeat*, *timeout* sorteado com semente derivada por nó, máquina de estados da eleição, *fencing* por `epoch` e a entrada `noop` ao assumir. Injeção de falhas e sessão de ensaio. |
| **Paulo Sebastian Rojo Pinedo** | **Interface.** Servidor HTTP, as rotas de cliente, internas e de administração, tradução uniforme de erros e CORS. Configuração do cluster e cliente entre nós. CLI completo, incluindo a descoberta do primário e os comandos de ensaio e falha. Frontend web, publicação na Vercel e os diagramas. |

Cada pessoa escreveu os testes do seu próprio módulo. A documentação foi revista
pelos três.

---

## O que mudou face à etapa entregue

O Protótipo 1 foi entregue no commit `7b430e6` com 103 testes e um nó só. O que
mudou desde então, e porquê, está em [`SPECS.md`](../docs/SPECS.md) 11.4 a 11.6.
Em resumo:

| Mudança | Onde |
|---|---|
| O **PostgreSQL** substituiu o WAL em JSONL como armazém principal | `persistencia/armazem*.py` |
| Apareceu a primeira **dependência externa** do projeto, `psycopg` | `requisitos.txt` |
| O nó ganhou **papel, `epoch` e eleição**; arranca sempre como réplica | `cluster/eleicao.py` |
| As escritas passaram a esperar pela **maioria** antes de responder | `cluster/replicacao.py` |
| Apareceu **injeção de falhas** e a **sessão de ensaio** exclusiva | `cluster/falhas.py`, `ensaio.py` |
| O servidor ganhou **CORS** e o cliente aprendeu a **encontrar o primário** | `interface/` |
| Uma réplica pode **reenviar escritas** ao primário, para o frontend atrás de um túnel | `interface/servidor_http.py` |
| `GET /interno/cluster` mostra **todos os nós** a partir de um endereço só | `cluster/vista.py` |
| Apareceu um **frontend web**, publicado na Vercel | `frontend/` |
| `--servidor` passou a aceitar `192.168.0.12:8001` sem o `http://` | `interface/cliente_http.py` |

O último era um erro com consequência prática: sem o esquema, o CLI dizia «o
servidor não respondeu» e saía com o código 3 — a mensagem exata de um processo em
baixo — quando o servidor estava perfeitamente vivo.

---

## Modos de falha conhecidos (RNF-10)

| Situação | O que acontece |
|---|---|
| Processo morto a meio de uma escrita | A transação não confirma. No arranque seguinte a entrada não existe, e como o `COMMIT` não devolvera, essa operação nunca foi confirmada a ninguém |
| Processo morto **depois** do commit, antes de responder | A operação está no log e é aplicada no arranque. O cliente repete com o mesmo `op_id` e recebe o resultado guardado, sem mover o dinheiro outra vez |
| A base de dados em baixo, ou disco cheio | `503 armazem_indisponivel`, e o saldo não muda. É 503 e não 500 de propósito: o banco está de pé e o cliente deve repetir quando o problema passar |
| Dois nós apontados ao mesmo DSN | O segundo recusa-se a arrancar. Sem isto partilhariam log em silêncio e a corrupção pareceria um erro de protocolo |
| A maioria não confirma a tempo | `503 sem_quorum`. A entrada fica **gravada e por confirmar**; o primário seguinte confirma-a ou trunca-a, e a deduplicação garante que o dinheiro se move uma vez só |
| A maioria inacessível há mais de um *timeout* de eleição | O primário passa a **somente leitura**: responde a saldo, extrato e auditoria, recusa escritas |
| Dois nós caídos de três | Somente leitura, e é o preço honesto de RNF-02 — não há a quem replicar |
| Primário antigo que regressa | Vê um `epoch` maior e despromove-se sem ter confirmado nada |
| Uma leitura durante a espera pelo quórum | Pode esperar até `timeout_replicacao_ms` (500 ms). Com o cluster são, são milissegundos |
| Dois operadores a injetar falhas | O segundo recebe `409 ensaio_tomado`, com o dono e quanto falta |
| O túnel cai com o frontend aberto | O total esbate-se e aparece «última leitura há N s». Nunca se mostra um número velho como se fosse atual |
| Pedido com corpo que não é JSON | `400 corpo_invalido`, sem tocar no estado |
| Valor monetário enviado como número JSON | `400 valor_invalido`. Um número seria descodificado como `float` |

---

## Resultados

| | |
|---|---|
| Testes | **305**, todos a passar |
| Testes que exigem PostgreSQL | 27, saltados com o motivo escrito quando não há base |
| Linhas de código | 4192 em `banco/` |
| Linhas de teste | 3348 em `tests/` |
| Duração da suíte | cerca de 15 segundos |
| Dependências externas | uma: `psycopg[binary]` |
| Módulos acima de 250 linhas | dois: `operacoes.py` (273) e `no.py` (261) |
| Linhas acima de 90 colunas | nenhuma |

**O que não está feito**, e fica escrito em vez de omitido:

- **A vazão não foi medida.** Sabe-se que o `lock` de estado serializa tudo,
  incluindo a espera pela maioria, e que isso é um limite claro — mas não se põe
  um número onde não houve medição.
- **O teste de *split-brain* com partição simétrica não existe.** A injeção de
  falhas suporta-o (`falha isolar`), e há um teste de isolamento a tirar um nó do
  quórum, mas o cenário completo dos dois lados sem maioria ainda não está escrito.
- **Não há log estruturado nem métricas** (RNF-07, RF-15).
- **O `GET /painel` não existe**: o frontend é servido à parte, não pelo nó.
- **A página não funciona sem JavaScript.** Mostra a estrutura, não os números:
  não há servidor a renderizá-la.
- **O WAL cresce sem limite.** Aceitável à escala da demonstração.
- **Sem autenticação nem cifragem**, por decisão da proposta — e é preciso dizer
  que o túnel expõe um banco sem autenticação à internet enquanto está de pé.
- **RF-18** (adicionar e remover servidores) continua fora de âmbito.
