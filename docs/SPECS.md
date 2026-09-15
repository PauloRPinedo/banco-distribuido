# SPECS — Especificação técnica

Como o sistema funciona por dentro: protocolos, formatos, API e decisões de
desenho. Os requisitos (F-xx, RF-xx, RNF-xx) vêm de [`proposta.md`](proposta.md);
o calendário de execução está no [`ROADMAP.md`](ROADMAP.md).

---

## 1. Visão geral

De 2 a 3 servidores mantêm **a mesma base de contas inteira**. Não há divisão de
clientes entre servidores.

```
        cliente (CLI)
             |
     +-------+-------+
     |       |       |
   nó A    nó B    nó C
 PRIMÁRIO  réplica  réplica
```

Só o primário aceita escritas. As réplicas recebem cada operação por um único RPC
(`/interno/replicar`), que serve ao mesmo tempo de replicação e de *heartbeat*.

**A consequência mais importante deste desenho:** como todas as contas estão em
todos os nós, uma transferência entre duas contas é sempre **local ao primário** —
débito e crédito acontecem na mesma máquina, na mesma entrada de log. Não existe
*commit* em duas fases neste projeto. É a maior simplificação do sistema, e é ela
que faz RF-05 (atomicidade) sair de graça.

### Camadas

```
  interface/   servidor HTTP, rotas, CLI, painel
       |
  cluster/     replicação, eleição, concorrência
       |
  dominio/     contas, dinheiro, operações   <- puro, sem rede nem disco
       |
  persistencia/ WAL, recuperação
```

`dominio/` não importa nada de rede nem de disco. A mesma sequência de entradas de
log produz exatamente o mesmo estado em qualquer nó, e é essa pureza que faz a
replicação por log e a recuperação por *replay* funcionarem.

---

## 2. Modelo de falhas e garantias

**O que assumimos que pode acontecer**

- Um nó para de repente (queda de processo, laptop desligado).
- Um nó fica lento (disco ocupado, rede congestionada).
- Mensagens atrasam-se, perdem-se ou chegam fora de ordem.
- A rede parte-se em dois lados que não se falam.

**O que assumimos que não acontece**

- Um nó mentir: enviar dados errados de propósito, forjar mensagens de outro nó.
  O modelo é *crash-stop* e lentidão, nunca comportamento malicioso (bizantino).
- Corrupção silenciosa de disco.

**O que o sistema garante**

| Garantia | Como |
|---|---|
| A soma dos saldos nunca muda por causa de uma falha | Uma transferência é uma única entrada de log, aplicada por uma única função |
| Uma operação confirmada ao cliente sobrevive à queda do primário | Só se confirma depois de estar em disco (`fsync`) na maioria dos nós |
| Nunca existem dois primários a aceitar escritas no mesmo `epoch` | Voto por maioria + `epoch` (secção 8) |
| Uma operação repetida pelo cliente move o dinheiro uma só vez | Deduplicação por `op_id` (secção 3.3) |

**O que o sistema não garante**

- Aceitar escritas quando a maioria dos nós está inacessível. Nesse caso responde
  `503 sem_quorum` e continua a servir leituras. Recusar é a única resposta
  correta: não há como tornar uma escrita durável sozinho.

---

## 3. Modelo de dados

### 3.1 Dinheiro

Todo valor monetário é um **inteiro de centavos**. Nunca `float`, em nenhum ponto
do sistema.

```python
saldo_centavos: int    # 12345 significa R$ 123,45
```

A razão não é estética. RNF-01 exige que a soma de todos os saldos seja constante,
e é verificada em teste após milhares de operações sorteadas. Com ponto flutuante
essa soma desvia-se por arredondamento, o teste falha, e o erro parece um erro de
replicação — perde-se um dia a depurar o protocolo por causa de `0,1 + 0,2`.

A conversão para `int` acontece **uma só vez**, na fronteira: quando o CLI ou a API
recebe o texto `"123.45"`. Usa-se `decimal.Decimal` para converter, nunca `float`.
Daí para dentro só circulam centavos.

### 3.2 Conta

| Campo | Tipo | Regra |
|---|---|---|
| `id` | `str` | 1 a 32 caracteres de `[a-z0-9_-]`. Único |
| `saldo_centavos` | `int` | Nunca negativo (RF-06) |
| `criada_em` | `float` | Instante Unix |

### 3.3 Entrada de log

É a unidade de replicação, de durabilidade e do extrato. Uma linha JSON:

```json
{"indice": 42, "epoch": 7, "op_id": "3f1c8a2e", "tipo": "transferencia",
 "dados": {"de": "alice", "para": "bob", "valor_centavos": 5000},
 "instante": 1756742400.12}
```

| Campo | Papel |
|---|---|
| `indice` | Índice global, começa em 1, contíguo, sem buracos |
| `epoch` | Mandato do primário que criou a entrada |
| `op_id` | Identificador gerado **pelo cliente**. Chave de deduplicação |
| `tipo` | `criar_conta`, `deposito`, `saque`, `transferencia`, `noop` |
| `dados` | Argumentos da operação |
| `instante` | Momento em que o primário aceitou. Só informativo |

**O `op_id` é gerado pelo cliente, não pelo servidor.** É o que torna a retentativa
segura: se o cliente não recebe resposta e repete a transferência, o servidor
reconhece o `op_id` já aplicado e devolve o resultado guardado, sem mover o
dinheiro outra vez (RF-13). Se o servidor gerasse o identificador, a segunda
tentativa seria uma operação nova e o dinheiro moveria-se duas vezes.

A **transferência é uma única entrada**, aplicada por uma única função. Não existe
estado intermédio em que o dinheiro saiu de uma conta e ainda não entrou na outra.
Daí vem RF-05.

### 3.4 Estado de cada nó

| Onde | O quê | Durabilidade |
|---|---|---|
| `dados/<id>/wal.jsonl` | Log de entradas | `fsync` antes de confirmar |
| `dados/<id>/estado.json` | `epoch` e `votou_em` | `fsync` **antes** de usar numa resposta |
| `dados/<id>/servidor.log` | Eventos, uma linha JSON cada | Escrita simples |
| memória | Saldos, extrato, `op_id` aplicados, `indice_commit` | Reconstruído no arranque |

`epoch` e `votou_em` gravam-se em disco **antes** de o nó responder a um pedido de
voto. Um nó que vota, cai e esquece o voto, votaria outra vez no mesmo `epoch` — e
aí dois candidatos diferentes poderiam somar maioria. É o único ponto do sistema em
que um `fsync` está entre o cálculo e a resposta por razões de correção, e não de
durabilidade.

---

## 4. Persistência

> **Âmbito.** 4.1 a 4.3 descrevem o armazém do **log replicado**, que é o que as
> etapas 2 e 3 precisam e vive em `projeto-final/`. O Protótipo 1 não guarda um log:
> guarda o estado, em duas tabelas, e está em 4.4. A diferença não é de arrumação —
> um log replicado existe para outro nó o poder reproduzir, e no Protótipo 1 não há
> outro nó.

### 4.1 WAL

Ficheiro de texto, uma entrada de log por linha, formato JSONL. Só se acrescenta ao
fim; nunca se reescreve uma linha existente.

```
{"indice":1,"epoch":1,"op_id":"a1","tipo":"criar_conta",...}
{"indice":2,"epoch":1,"op_id":"b2","tipo":"deposito",...}
```

Escrever significa: `write` + `flush` + `os.fsync`. Só depois do `fsync` é que a
entrada conta como durável, no primário e em cada réplica.

Escolheu-se JSONL em vez de um formato binário por ser legível: quando o failover
se comporta de forma estranha durante a demonstração, abrir o WAL dos três nós lado
a lado com `tail` responde à pergunta em segundos.

### 4.2 Recuperação no arranque (RF-12)

1. Ler `estado.json` → `epoch` e `votou_em`.
2. Ler o WAL linha a linha e aplicar cada entrada ao estado em memória.
3. Se a última linha estiver truncada (o processo morreu a meio de uma escrita),
   descartá-la e truncar o ficheiro nesse ponto. Uma linha incompleta nunca foi
   confirmada a ninguém.
4. Arrancar **sempre como réplica**, mesmo que este nó fosse o primário antes de
   cair. Quem manda decide-se por eleição, nunca pelo que o nó se lembra de si.

> **Histórico.** O Protótipo 1 nunca teve papel nenhum: com um nó só, aceita
> escritas sempre e não há `epoch` para guardar. Durante a reabertura da etapa
> (11.6) o ponto 4 chegou a aplicar-se lá dentro; com a reconstrução (11.8) voltou
> a ser só das etapas seguintes. A versão reaberta vê-se em `git show 3683a0f`.

**Não há snapshots.** O estado reconstrói-se sempre por *replay* completo do WAL.
Numa demonstração o log tem centenas ou milhares de entradas e o *replay* demora
milissegundos; um mecanismo de snapshot custaria umas duzentas linhas e um conjunto
novo de casos extremos para não resolver problema nenhum aqui.

### 4.3 PostgreSQL como armazém do log

Desde setembro de 2026 o armazém principal é o **PostgreSQL**, um por laptop, com uma
base de dados por nó (`banco_a`, `banco_b`, `banco_c`). O WAL em JSONL de 4.1
continua a existir como `--armazem ficheiro`, para os testes de linha truncada e como
saída de emergência no dia da demonstração. A justificação do desvio está em 11.4.

**Cada nó tem a sua base.** O consenso é o desta especificação, implementado de raiz;
a replicação nativa do PostgreSQL **não se usa**, porque a proposta exige que o
protocolo seja escrito pelo grupo. Bases separadas garantem que os nós não partilham
estado, e têm um efeito lateral útil: matar o processo de um nó não mata o PostgreSQL
dele, que é exatamente o cenário "cai, reinicia, recupera" que se quer demonstrar.

#### Esquema

```sql
CREATE TABLE registo_do_log (
    indice   BIGINT PRIMARY KEY,
    epoch    BIGINT NOT NULL,
    op_id    TEXT   NOT NULL,
    tipo     TEXT   NOT NULL,
    dados    JSONB  NOT NULL,
    instante DOUBLE PRECISION NOT NULL
);
CREATE UNIQUE INDEX log_op_id_unico ON registo_do_log (op_id);

CREATE TABLE estado_do_no (
    no_id         TEXT PRIMARY KEY,
    epoch         BIGINT NOT NULL DEFAULT 1,
    votou_em      TEXT,
    indice_commit BIGINT NOT NULL DEFAULT 0
);
```

**O dinheiro nunca é uma coluna.** Vive dentro de `dados`, em `jsonb`, como inteiro de
centavos. Três tipos foram recusados, e o porquê importa na defesa:

| Tipo recusado | Porquê |
|---|---|
| `NUMERIC(12,2)` | Obrigaria a converter entre reais e centavos à entrada da base — um **segundo** sítio de conversão, quando 3.1 exige que haja um só |
| `MONEY` | Depende do `lc_monetary` do servidor. A mesma base em dois laptops com *locale* diferente daria valores diferentes |
| `DOUBLE PRECISION` | É literalmente o que RNF-01 proíbe |

Há um teste-guarda no contrato do armazém: grava-se `9007199254740993` centavos — um
inteiro acima de 2^53, onde um `float` perde o último dígito — e verifica-se que o que
volta é `int` e é o mesmo número.

#### Durabilidade

`synchronous_commit = on` com a ligação em `autocommit`: um `INSERT` é uma transação,
e `COMMIT` só devolve depois de o registo estar em disco. É a equivalência exata do
`write` + `flush` + `os.fsync` de 4.1, e a ordem obrigatória de uma escrita (secção 5)
não muda um passo — o "gravar no WAL + fsync" lê-se agora como "`INSERT` + commit
síncrono".

A definição é forçada por sessão, não deixada ao `postgresql.conf`, e o nó imprime
`fsync` e `synchronous_commit` na linha de arranque. É a prova que se mostra quando
perguntarem como é que se sabe que houve `fsync`.

#### `indice_commit` é um prefixo

O commit guarda-se como **um número** em `estado_do_no`, não como um campo por linha.
Neste protocolo o que está confirmado é sempre um prefixo contíguo do log; um sinal
por linha permitiria representar estados que o protocolo não consegue produzir, e a
primeira coisa que se faz com uma representação assim é enganar-se a lê-la.

No arranque aplicam-se as entradas até `indice_commit` e só até aí. As de índice maior
ficam gravadas e por aplicar — quem decide o destino delas é o primário seguinte
(secção 7).

#### Deduplicação

A tabela de `op_id` em memória, reconstruída por *replay*, continua a ser o mecanismo.
O que a base acrescenta é uma rede de segurança que o JSONL não tinha: `UNIQUE (op_id)`.
Se o processo morrer entre o commit do `INSERT` e o aplicar, uma repetição não consegue
inserir uma segunda linha com o mesmo `op_id`.

#### Dois nós contra a mesma base

`no_id` é chave primária de `estado_do_no`, e o nó recusa-se a arrancar se a base
pertencer a outro id. Sem isto, dois nós apontados ao mesmo DSN partilham log em
silêncio, e a corrupção que daí vem parece um erro de protocolo — perdem-se horas a
procurar no sítio errado.

### 4.4 Esquema do Protótipo 1

Duas tabelas. `conta` diz quanto dinheiro existe agora; `operacao` diz tudo o que
aconteceu. A auditoria (RF-14) soma as duas de maneiras independentes e compara — e é
por serem independentes que concordarem prova alguma coisa.

```sql
CREATE TABLE conta (
    id              VARCHAR(32) PRIMARY KEY CHECK (id ~ '^[a-z0-9_-]{1,32}$'),
    saldo_centavos  BIGINT NOT NULL CHECK (saldo_centavos >= 0),
    criada_em       DOUBLE PRECISION NOT NULL
);

CREATE TABLE operacao (
    op_id             VARCHAR(64) PRIMARY KEY,
    numero            BIGINT NOT NULL UNIQUE,
    tipo              VARCHAR(20) NOT NULL
                      CHECK (tipo IN ('criar_conta','deposito','saque','transferencia')),
    conta_origem_id   VARCHAR(32) REFERENCES conta(id),
    conta_destino_id  VARCHAR(32) REFERENCES conta(id),
    valor_centavos    BIGINT NOT NULL CHECK (valor_centavos >= 0),
    resposta          JSONB NOT NULL,
    instante          DOUBLE PRECISION NOT NULL
);
CREATE SEQUENCE operacao_numero;
```

**`criada_em` e `instante` são `DOUBLE PRECISION`**, e não `TIMESTAMP`, porque 3.2 diz
instante Unix. Com um `TIMESTAMP` sem fuso, dois portáteis com fusos diferentes leem
valores diferentes da mesma linha, e a conversão passa a acontecer em dois sítios em
vez de um.

**`op_id` é `VARCHAR`**, e não `UUID`. O exemplo de 3.3 é `"3f1c8a2e"`, que não é um
UUID; a coluna `UUID` apertaria mais do que esta especificação e devolveria um 500 do
driver em vez de um `400 valor_invalido` explicado. O formato é validado na fronteira.

**`resposta` guarda o corpo que o cliente recebeu**, tal e qual. É o "resultado
guardado" de 3.3: recalculá-lo a partir dos saldos de agora daria uma resposta
diferente se entretanto tivesse havido outras operações, e a retentativa deixaria de
ser indistinguível do pedido original.

**`numero` ordena, não conta.** É o `indice` de 3.3 no que importa aqui — dar uma
ordem total às operações, para o extrato não depender de dois instantes empatarem.
Não é contíguo: uma sequência do PostgreSQL não volta atrás quando a transação é
revertida. A contiguidade de 3.3 existe para uma réplica detetar entradas em falta, e
no Protótipo 1 não há réplica.

**Não há coluna `estado`.** Sem commit em duas fases, a linha só existe se a transação
confirmou. Um campo a dizer o mesmo seria um segundo sítio a poder divergir do
primeiro.

---

## 5. Concorrência

Três níveis, cada um com o seu mecanismo.

**Entre nós** — resolvido por construção, e de maneira diferente em cada etapa.

Nas etapas 2 e 3, só o primário escreve, e é ele que ordena as operações ao
atribuir o `indice`: não existe escrita concorrente entre servidores.

No Protótipo 1 com dois nós (11.9) existe escrita concorrente entre servidores, e
quem a resolve é a base que eles partilham — os dois pedem os mesmos *locks* de
linha, pela mesma ordem, e a sequência `operacao_numero` dá a ordem total. Não há
primário porque não há nada para coordenar entre eles.

**Entre contas** — *locks* por conta. Um *lock* global serializaria o banco inteiro
e tornaria RNF-04 impossível; com *locks* por conta, transferências sobre contas
diferentes correm em paralelo.

O risco que isto cria é o *deadlock* clássico: `alice→bob` e `bob→alice` ao mesmo
tempo, cada uma a segurar um *lock* e à espera do outro. A solução é **ordem
total**: os *locks* adquirem-se sempre por ordem crescente do id da conta. Como
todas as operações seguem a mesma ordem, o ciclo de espera é impossível. A operação
devolve as contas que toca já ordenadas, para que ninguém tenha de se lembrar da
regra no ponto de uso.

**Dentro de um nó** — depende de onde vive o estado, e é o único ponto em que as
etapas divergem.

Onde o estado está em memória (etapas 2 e 3), é preciso um `lock` único de estado:
aplicar uma operação mexe em estruturas partilhadas (`indice_commit`, extrato,
tabela de `op_id`) que duas *threads* com contas diferentes corromperiam. Esse
`lock` serializa a aplicação e também a leitura, porque uma consulta feita entre o
débito e o crédito de uma transferência veria dinheiro desaparecido (RF-07).

No Protótipo 1 não há estado em memória para proteger: o estado é a base. O
isolamento da transação dá a leitura consistente de RF-07, e os *locks* por conta
são `SELECT ... FOR UPDATE` em vez de objetos em memória. O que não muda é quem
decide a ordem — continua a ser `Operacao.contas_tocadas()`. Ver 11.8.

### Ordem obrigatória de uma escrita

Nenhum destes passos pode trocar de lugar:

| | Etapas 2 e 3 | Protótipo 1 |
|---|---|---|
| 1 | `op_id` já aplicado? Devolver o resultado guardado e terminar | igual |
| 2 | Adquirir os *locks* das contas envolvidas, por ordem crescente de id | `SELECT ... FOR UPDATE`, uma conta de cada vez, pela mesma ordem |
| 2b | — | Voltar a perguntar pelo `op_id`, agora já serializado pelos *locks* |
| 3 | **Validar**: as contas existem, o valor é positivo, o saldo chega | igual |
| 4 | Gravar no WAL + `fsync` | `INSERT` em `operacao` |
| 5 | Replicar e esperar pela maioria (secção 7) | não se aplica: há um nó só |
| 6 | Aplicar ao estado, guardar o resultado do `op_id`, libertar os *locks* | Aplicar e guardar; os *locks* caem com o commit |
| 7 | Responder ao cliente | igual, depois do commit |

- A validação vem **antes** do log: não se replica uma operação que vai ser rejeitada.
- O `fsync` vem **antes** do ACK, no primário e na réplica.
- A resposta ao cliente vem **depois** da maioria. É isto, e só isto, que faz uma
  operação confirmada sobreviver à queda imediata do primário.
- Os *locks* só se libertam **depois** de aplicar (RF-08).

O passo 2b não existia e faz falta nos dois desenhos: sem ele, duas retentativas
simultâneas com o mesmo `op_id` veem ambas "ainda não aplicada" no passo 1 e ambas
seguem em frente. No Protótipo 1 é visível porque o passo 1 lê fora de qualquer
*lock*; com o `lock` de estado das outras etapas o problema não chega a acontecer,
mas escrever o passo custa uma linha e torna a ordem verdadeira nos dois casos.

---

## 6. API HTTP

Transporte HTTP com corpos JSON. Escolheu-se HTTP em vez de sockets crus por uma
razão operacional: quando o cluster não converge nos laptops, um `curl` diz em cinco
segundos se o problema é a *firewall* ou o protocolo.

Quem serve depende da etapa — `http.server.ThreadingHTTPServer` no estado entregue,
FastAPI e uvicorn no Protótipo 1 reconstruído e no projeto final (11.8). O contrato
desta secção é o mesmo nos dois.

Erros têm sempre a mesma forma:

```json
{"erro": "saldo_insuficiente", "mensagem": "alice tem R$ 120,00 e a transferência pede R$ 500,00"}
```

| Código | HTTP | Quando |
|---|---|---|
| `valor_invalido` | 400 | Valor ausente, não positivo ou mal formado |
| `conta_inexistente` | 404 | A conta não existe |
| `conta_duplicada` | 409 | Já existe conta com esse id |
| `nao_sou_primario` | 409 | Escrita enviada a uma réplica. Traz `primario_provavel` |
| `saldo_insuficiente` | 422 | A operação deixaria o saldo negativo |
| `sem_quorum` | 503 | A maioria não confirmou dentro do tempo |
| `somente_leitura` | 503 | O nó não vê a maioria e recusa escritas |

Os três que falam de primário, maioria e réplica só existem onde há cluster. O
Protótipo 1 devolve apenas `valor_invalido`, `conta_inexistente`, `conta_duplicada` e
`saldo_insuficiente`.

### 6.1 Rotas de cliente

| Rota | Método | Requisito |
|---|---|---|
| `/contas` | POST | RF-01 criar conta |
| `/contas/{id}` | GET | RF-02 saldo |
| `/contas/{id}/deposito` | POST | RF-03 |
| `/contas/{id}/saque` | POST | RF-03 |
| `/transferencias` | POST | RF-04, RF-05 |
| `/contas/{id}/extrato` | GET | F-05 |
| `/auditoria` | GET | RF-14 |

**Os valores monetários viajam como texto JSON**, `"valor": "25.00"` e nunca
`"valor": 25.00`. Um número JSON seria descodificado como `float`, e um `float`
em dinheiro é a origem do desvio de arredondamento que RNF-01 proíbe. Exigir
texto mantém a conversão para centavos a acontecer num sítio só, na fronteira
(secção 3.1). Um número é recusado com `400 valor_invalido`.

Toda escrita exige `op_id` no corpo — **no corpo**, e não num cabeçalho. O
`X-Op-Id` que `projeto-final/` usa é um desvio que nunca chegou a ser registado aqui;
o Protótipo 1 segue esta secção.

O resto deste bloco só se aplica onde há cluster. Uma réplica recusa escritas com:

```json
{"erro": "nao_sou_primario", "primario_provavel": "192.168.0.12:8001"}
```

As leituras são servidas pelo primário. Uma réplica só responde a leituras com
`?desatualizado=true` explícito, e a resposta traz `desatualizado: true` e o
`indice_aplicado`, para o cliente saber quão atrasado o dado pode estar.

### 6.2 Rotas internas (entre servidores)

> Não existem no Protótipo 1: não há outro servidor a quem falar nem falhas para injetar. A única rota fora de 6.1 é
> `GET /saude`, que diz que o processo está de pé.

| Rota | Método | Papel |
|---|---|---|
| `/interno/replicar` | POST | Replicação e *heartbeat* |
| `/interno/votar` | POST | Pedido de voto |
| `/interno/log?desde=N` | GET | Réplica atrasada pede o log a partir de N |
| `/interno/estado` | GET | Papel, `epoch`, último índice, `indice_commit` |
| `/interno/cluster` | GET | **Todos** os nós, vistos por este (F-11) |

`/interno/cluster` é uma rota de **leitura**, e é deliberadamente separada de
`/interno/estado`: aquela é chamada pelos pares a cada *heartbeat* e pelo
`verificar_rede.sh`, e pô-la a fazer chamadas de rede tornaria o caminho quente
caro — e recursivo. Esta pergunta a cada par o `/interno/estado` simples, em
paralelo e com o `timeout_replicacao_ms` como prazo, por isso a recursão é
impossível por construção.

Existe porque o frontend vê o cluster através de **um** túnel, não três. Um par
que não responde volta com `vivo: false` em vez de desaparecer da lista: durante
um failover é justamente o nó em falta que interessa ver. O campo `eu` diz qual
nó respondeu — a resposta é sempre uma opinião, e apresentá-la como verdade
absoluta seria mentir.

Não há autenticação nem cifragem: está fora do âmbito por decisão da proposta, e é
coerente com o modelo de falhas — um nó pode morrer ou atrasar-se, mas não mente.

### 6.3 Rotas de administração

> Não existem no Protótipo 1: não há outro servidor a quem falar nem falhas para injetar. A única rota fora de 6.1 é
> `GET /saude`, que diz que o processo está de pé.

| Rota | Método | Requisito |
|---|---|---|
| `/admin/metricas` | GET | RF-15 |
| `/admin/falha` | POST | RF-16, F-10 |
| `/admin/ensaio` | GET, POST | Sessão de ensaio exclusiva (11.7) |
| `/painel` | GET | F-11, painel web |

**Tomar a sessão de ensaio só acontece no primário.** É um *lease* dele, que se
propaga às réplicas montado no *heartbeat*. Deixar tomá-la numa réplica foi o erro
que tornava a exclusão inútil: dois operadores tomavam-na em nós diferentes, os
dois achavam-se donos, e nenhum era recusado. **Ler** pode ser em qualquer nó —
saber quem tem a sessão é justamente o que faz falta quando o primário está em
baixo.

---

## 7. Replicação

Um único RPC serve de replicação e de *heartbeat*. Reaproveitá-lo garante que o
*heartbeat* carrega sempre o `epoch` e o `commit_lider` corretos, sem um segundo
caminho de código que possa divergir do primeiro.

`POST /interno/replicar`

```json
{"epoch": 7, "id_lider": "A", "indice_anterior": 41, "epoch_anterior": 7,
 "entradas": [ ... ], "commit_lider": 41}
```

Com `entradas` vazio, é um *heartbeat*.

**A réplica aceita se, e só se:**

1. `epoch` do pedido ≥ o seu `epoch`; e
2. tem no seu log uma entrada em `indice_anterior` com `epoch_anterior`.

Se aceita: grava as entradas, faz `fsync`, avança `indice_commit` até
`min(commit_lider, seu último índice)` e responde:

```json
{"epoch": 7, "ok": true, "indice_correspondente": 42}
```

Se a condição 1 falha, responde `ok: false` com o seu `epoch` — e o primário, ao
ver um `epoch` maior, despromove-se imediatamente a réplica.

Se a condição 2 falha, o seu log divergiu ou tem um buraco. Responde
`{"ok": false, "meu_ultimo_indice": N}` e o primário reenvia o log a partir de
`N + 1`.

> **Simplificação face ao Raft.** O Raft resolve a divergência recuando um índice de
> cada vez até encontrar o ponto comum. Aqui a réplica diz logo onde está e o
> primário reenvia daí; se as entradas nesse intervalo divergirem, a réplica trunca
> as suas e aceita as do primário. Nunca se trunca abaixo do `indice_commit`, porque
> essas entradas já foram confirmadas a um cliente. Um nó muito atrasado usa
> `GET /interno/log?desde=N` para se pôr em dia de uma vez.

**Confirmação por maioria.** O primário conta-se a si próprio. Com 3 nós, a maioria
é 2: o primário mais uma réplica. Com 2 nós, a maioria é 2: ambos.

Se a maioria não responder dentro de `timeout_replicacao_ms`, o cliente recebe
`503 sem_quorum`. A entrada fica gravada mas **não confirmada** — pode vir a
existir ou não. O cliente repete com o mesmo `op_id`; o próximo primário ou a
confirma (se chegou à maioria) ou a trunca, e a deduplicação garante que o dinheiro
se move exatamente uma vez.

Se a maioria estiver inacessível há mais do que um *timeout* de eleição, o primário
passa a **somente leitura** de imediato, em vez de acumular operações que nunca
serão confirmadas.

---

## 8. Eleição e failover

```
  [arranque] --> RÉPLICA
  RÉPLICA   --> CANDIDATO : sem heartbeat durante o timeout sorteado
  CANDIDATO --> PRIMÁRIO  : maioria dos votos
  CANDIDATO --> RÉPLICA   : perdeu, ou viu um epoch maior
  CANDIDATO --> CANDIDATO : empate — novo epoch, novo timeout
  PRIMÁRIO  --> RÉPLICA   : recebeu um epoch maior
```

### 8.1 Deteção

O primário envia um *heartbeat* a cada `heartbeat_ms` (150 ms). Uma réplica que
passe `timeout_eleicao_ms` sem receber nada incrementa o `epoch` e candidata-se.

O *timeout* de eleição é **sorteado** em `[800, 1500] ms` a cada ronda. Sem
aleatoriedade, as réplicas tornam-se candidatas ao mesmo tempo, dividem os votos e
a eleição não converge.

**A semente do sorteio é derivada por nó** — `semente_global + crc32(id_do_no)` — e
nunca a semente global pura. Isto não é detalhe: com a mesma semente nos três nós,
os três sorteiam o *mesmo* valor, candidatam-se juntos e dividem os votos
indefinidamente. Derivar de forma estável mantém RNF-06, porque a mesma semente
global continua a reproduzir a mesma execução.

Também é preciso `heartbeat_ms` muito menor que o mínimo do *timeout*. Se forem
próximos, uma lentidão momentânea derruba um primário saudável e o cluster passa a
trocar de líder sem parar. A configuração valida esta relação ao carregar.

### 8.2 Pedido de voto

`POST /interno/votar`

```json
{"epoch": 8, "id_candidato": "B", "ultimo_indice": 42, "ultimo_epoch": 7}
```

O eleitor concede o voto se **as três** condições valerem:

1. o `epoch` do candidato é maior ou igual ao seu;
2. ainda não votou neste `epoch`, ou já votou neste mesmo candidato;
3. o log do candidato está **pelo menos tão atualizado** quanto o seu — compara-se
   `ultimo_epoch` e, em empate, `ultimo_indice`.

A condição 3 é o que impede que uma operação confirmada se perca:

> Toda operação confirmada está gravada na maioria dos nós.
> Todo vencedor de eleição precisa do voto da maioria.
> Duas maiorias têm sempre pelo menos um nó em comum.
> Esse nó só votaria em quem tem o log ao menos tão atualizado quanto o dele.
> Logo, **o novo primário tem todas as operações confirmadas**.

### 8.3 Fencing por `epoch`

Cada mandato de primário tem um número, o `epoch`, que só cresce. Como cada nó vota
uma única vez por `epoch`, e duas maiorias intersectam-se sempre, **não existem dois
primários no mesmo `epoch`**.

Toda mensagem carrega o `epoch`. Um primário antigo que volta a si — depois de uma
pausa de rede, por exemplo — tem `epoch` menor, é rejeitado por todos e despromove-se
a réplica sem ter confirmado nada.

### 8.4 Ao assumir

O novo primário envia um *heartbeat* imediato, para calar candidatos concorrentes, e
grava uma entrada **`noop` no seu próprio `epoch`** antes de aceitar escritas.

A razão é subtil e vale registá-la para a defesa: uma entrada herdada do primário
anterior, mesmo presente na maioria dos nós, **não pode ser confirmada por contagem
de réplicas**. Existe um cenário conhecido em que ela é depois sobrescrita por outro
líder, e uma operação já dada como confirmada desapareceria. Confirmando primeiro a
`noop` do `epoch` atual, tudo o que vem antes fica confirmado por arrasto, em
segurança.

---

## 9. Configuração do cluster

`config/cluster.json`, igual em todos os nós:

```json
{
  "nos": [
    {"id": "A", "endereco": "192.168.0.11", "porta": 8001},
    {"id": "B", "endereco": "192.168.0.12", "porta": 8001},
    {"id": "C", "endereco": "192.168.0.12", "porta": 8002}
  ],
  "heartbeat_ms": 150,
  "timeout_eleicao_ms": [800, 1500],
  "timeout_replicacao_ms": 500,
  "semente": 42
}
```

O ficheiro está no `.gitignore`; versiona-se `config/cluster.exemplo.json`.

### Ensaio em 2 ou 3 laptops

**Usar sempre 3 nós, mesmo com 2 laptops** (o PC1 corre A, o PC2 corre B e C). Com
apenas 2 nós, a maioria é 2 e a queda de qualquer um deixa o outro em somente
leitura — não há failover com escrita para demonstrar.

- Os nós ligam-se a `0.0.0.0`, não a `127.0.0.1`, senão não são alcançáveis de fora.
- As portas têm de estar abertas na *firewall* de cada laptop.
- **Antes de subir o cluster**, testar cada endereço com `curl`. Com uma porta
  bloqueada, os sintomas — eleições sem fim, `epoch` a subir sozinho — parecem um
  erro de protocolo e levam a procurar no sítio errado.

---

## 10. Observabilidade e injeção de falhas

**Log estruturado** (RNF-07): uma linha JSON por evento, com `instante`, `no`,
`epoch`, `evento` e campos próprios do evento. Vocabulário fechado de eventos, em
[`CODESTYLE.md`](CODESTYLE.md).

**Métricas** (RF-15), em `/admin/metricas`: operações por tipo, latências (p50, p99),
`epoch` atual, número de eleições, último índice, `indice_commit`, réplicas vivas.

**Painel** (F-11), em `/painel`: página HTML servida pelo próprio nó, só leitura,
mostra os nós ativos, quem é o primário, o `epoch` e as métricas. Sem operações
bancárias. O desenho está em [`CODESTYLE.md`](CODESTYLE.md).

**Injeção de falhas** (RF-16, F-10), em `POST /admin/falha`:

```json
{"tipo": "atraso", "ms": 300}
{"tipo": "isolar", "de": ["B"]}
{"tipo": "derrubar"}
{"tipo": "limpar"}
```

`isolar` faz o nó descartar mensagens dos nós indicados, simulando uma partição de
rede sem mexer na *firewall* — é o que permite reproduzir o cenário de *split-brain*
num teste automático.

---

## 11. Desvios face à proposta

Registados aqui com a justificação, porque são pontos de discussão na defesa.

### 11.1 Failover por voto, não por posição na lista

A proposta descreve failover simples: "a próxima da lista assume". Ao detalhar o
desenho, três exigências da própria proposta revelaram-se incompatíveis:

| Exigência | Conflito |
|---|---|
| RF-10 / RNF-02: só confirmar depois de replicar | Exige pelo menos 2 nós vivos |
| RF-11: continuar a atender com um servidor fora do ar | Com 1 nó vivo não há a quem replicar |
| RF-09: promoção por posição na lista, sem votação | Um primário apenas **lento** continua a julgar-se primário |

O terceiro é o grave. Se o primário A está só lento — GC, rede congestionada, disco
travado — e B assume por *timeout*, passam a existir dois primários. Um cliente
deposita em A, outro em B, os dois logs divergem, e quando A volta ou se perde uma
operação ou se somam saldos incompatíveis. É exatamente a falha que o projeto
existe para impedir.

**Adotado:** promoção por maioria de votos com *fencing* por `epoch`. O resultado é
um Raft simplificado: mantém-se o que dá a garantia (`epoch`, voto por maioria,
restrição de voto pelo log) e deixa-se de fora o que aqui não faz falta (mudança
dinâmica de membros, compactação distribuída, leituras por *lease*).

**Efeito sobre RF-11:** com 3 servidores tolera-se 1 queda com escritas normais. Com
2 caídos, o nó vivo passa a somente leitura — responde a saldo, extrato e auditoria,
recusa escritas com 503. É o preço honesto de RNF-02. RF-11 cumpre-se no sentido de
continuar a responder; a parte de escrita fica documentada como impossível sob essa
combinação de requisitos.

### 11.2 Painel web

A proposta exclui "interface gráfica web" do âmbito. Acrescenta-se mesmo assim um
painel, com dois limites que o mantêm coerente com essa restrição: é **só de
leitura** e é de **monitorização**, não de operação bancária. Existe para cumprir
F-11 de forma demonstrável; todas as operações continuam a passar pelo CLI (F-12).

### 11.3 RNF-04 (500 transações por segundo)

Tratado como **meta de medição**, não como requisito bloqueante. Uma implementação
anterior deste mesmo desenho saturou em cerca de 270 TPS nesta classe de máquina, e
as hipóteses de estrangulamento testadas (`fsync`, contenção de *locks*,
serialização, CPU) foram todas descartadas — o tempo estava em espera, não em
trabalho.

O projeto final regista o número medido e a análise. Relatar a medição real vale
mais do que ajustar o requisito para que ele pareça cumprido.

### 11.4 PostgreSQL substitui o WAL em JSONL

Decisão do grupo, setembro de 2026. O armazém principal do log passa a ser o
PostgreSQL (4.3), e com ele entra a primeira dependência externa do projeto,
`psycopg[binary]`.

**O que se ganha:** o `INSERT` e o avanço do `indice_commit` passam a ser transações
de uma base que já resolve durabilidade e atomicidade; ganha-se `UNIQUE (op_id)` como
rede de segurança da deduplicação; e na defesa pode-se responder a perguntas sobre o
log com SQL em vez de com `grep`.

**O que se perde, e é preciso dizê-lo:** a promessa de `git clone` e executar deixa de
valer para o servidor. Perde-se também o `tail` a três WAL lado a lado, que era a
ferramenta mais rápida para perceber um failover estranho — a compensação é
`--armazem ficheiro`, que volta ao JSONL e faz o cluster funcionar na mesma.

**Porque é que o consenso não usa a replicação nativa do PostgreSQL:** a proposta
exige, nas restrições, que "o consenso e o protocolo de transações são implementados
do zero, sem bibliotecas prontas para essas funções". Usar *streaming replication*
resolveria o problema apagando justamente o trabalho que a disciplina avalia. Cada nó
tem a sua base, e o que as mantém de acordo é o protocolo da secção 7.

### 11.5 Frontend web que opera o banco

A proposta exclui "interface gráfica web" do âmbito. O desvio 11.2 já acrescentou um
painel de monitorização, só de leitura. Este vai mais longe: é um frontend que
**opera** o banco — cria contas, deposita, saca e transfere — publicado na Vercel e
ligado a um nó por um túnel HTTPS.

**Limites que o mantêm honesto:** o CLI continua a ser a interface oficial do trabalho
(F-12, RF-17) e é por ele que passam as demonstrações avaliadas; o frontend não tem
nenhuma capacidade que o CLI não tenha; e nenhuma regra de negócio vive no navegador —
o `op_id` é gerado no cliente e os valores viajam como texto, tal como no CLI, e é o
servidor que valida tudo.

**O que o túnel implica:** durante a demonstração, um banco sem autenticação fica
acessível a partir da internet, com URL aleatória. Levanta-se para a demonstração e
fecha-se a seguir. Autenticação e cifragem continuam fora do âmbito por decisão da
proposta, e omitir esta consequência seria desonesto.

**Porque é que o nó do túnel encaminha as escritas:** o túnel aponta a um nó só.
Quando esse nó deixa de ser primário, responderia `409 nao_sou_primario` com um
`primario_provavel` que é um endereço de LAN — inalcançável do navegador. O nó passa
então a encaminhar a escrita ao primário como cliente puro, sem gravar nada
localmente, o que não mexe na ordem da secção 5. Sem isto, o failover partia a página
web justamente no momento que ela existe para mostrar.

### 11.6 As etapas 2 e 3 dentro de `prototipo-1/` — revertido

**Esta decisão foi desfeita.** Ficou registada porque explica o estado do
repositório entre setembro de 2026 e a reconstrução, e porque a razão por que foi
desfeita é a mesma que a tornava má desde o início.

O que se tinha decidido: o Protótipo 1, entregue em setembro de 2026, foi reaberto
logo a seguir para receber a replicação, a eleição, a injeção de falhas, a sessão de
ensaio exclusiva e o frontend — âmbito acrescentado depois da entrega, a pedido do
grupo, e não um erro corrigido tarde.

O custo estava escrito aqui mesmo, e acabou por ser o que pesou: **deixava de haver
uma pasta que mostrasse o banco de um nó só a funcionar isolado**, que era a razão de
ser da divisão em etapas. Com o trabalho da etapa 2 já a viver dentro da pasta da
etapa 1, a progressão que as três pastas existem para mostrar tinha desaparecido.

O Protótipo 1 foi reconstruído sobre a pilha do projeto final (ver 11.8). O estado
reaberto continua acessível em `git show 3683a0f` e o estado entregue em
`git show 7b430e6`.

### 11.7 Sessão de ensaio exclusiva

Não está na proposta, e é uma regra de **operação**, não de banco: na demonstração
há dois laptops e três pessoas, todas com o CLI. Dois operadores a derrubar nós ao
mesmo tempo produzem um cluster sem maioria por acidente, e o que se vê no ecrã
deixa de ser a experiência que se estava a fazer — passa a ser um acidente que
ainda por cima parece um erro do protocolo.

A tranca vive no primário, em memória, e viaja para as réplicas no *heartbeat*.
Duas alternativas foram recusadas:

- **local a cada nó** não excluiria nada: um operador tomava-a em A e o outro em B;
- **pelo log replicado** sobreviveria ao failover, mas meteria estado operativo na
  pista de auditoria do dinheiro, correria os índices e sujaria o extrato das
  contas com eventos que não são operações bancárias.

Morre com o primário, e ainda bem: quem tem a sessão é exatamente quem acabou de o
matar, e voltar a tomá-la é um comando. A caducidade existe para o outro caso, o do
operador que a toma e vai almoçar.

### 11.8 O Protótipo 1 reconstruído sobre a pilha do projeto final

Decidido em setembro de 2026, logo a seguir a 11.6 ser desfeita. O Protótipo 1
passou a ser uma versão básica do projeto final em vez de um programa à parte: as
mesmas camadas, a mesma pilha, os mesmos nomes, sem replicação nem autenticação.

**Porquê reconstruir em vez de repor o estado entregue.** Repor `7b430e6` daria uma
etapa 1 correta, mas escrita noutra tecnologia que a etapa 3: `http.server` contra
FastAPI, WAL em JSONL contra PostgreSQL, `interface/` contra `api/`. Quem lesse as
duas pastas de seguida veria dois programas, não um a crescer. Partilhando a pilha,
a diferença entre as etapas passa a ser só o que foi acrescentado — que é
exatamente o que se quer mostrar na defesa.

**O que isto custa, e é caro.** Há quatro desvios a registar, todos contra regras
que o próprio grupo escreveu:

| Desvio | Contra | Porquê se aceita |
|---|---|---|
| Quatro dependências (`fastapi`, `uvicorn`, `psycopg2-binary`, `pydantic`) | `CONVENCOES.md` 4, "há exatamente uma dependência externa" | São as do projeto final, e a decisão é ter uma pilha só. Acrescentar uma quinta continua a ser decisão do grupo |
| `dominio`, `repositorio`, `servico`, `api` | `CODESTYLE.md` 3, que fixa `dominio`, `persistencia`, `cluster`, `interface` | A árvore antiga tem um `cluster/` que aqui estaria vazio e um `persistencia/` que aqui é só SQL. A regra que importava — as setas apontam para dentro e o domínio não conhece rede nem disco — continua a valer, e é verificável: `python3 -c "import banco.dominio.operacoes"` não toca em `psycopg2` nem em `fastapi` |
| Os testes de integração pedem `pip install` | `CONVENCOES.md` 4, "os testes correm sem instalar nada" | Os 55 do domínio continuam a correr numa máquina limpa; os 42 de integração saltam-se sozinhos com o motivo escrito. Era isso ou não ter testes de concorrência contra uma base real, que são os únicos que provam a invariante debaixo de carga |
| Não há cliente de linha de comando | F-12 e RF-17 da proposta | O projeto final também não tem. Ficam por cobrir no repositório inteiro, e o único sítio onde existem é `git show 7b430e6`. Está dito no README da etapa, em vez de omitido |

**O estado é estado, não log.** Esta etapa guarda duas tabelas — `conta`, com o
saldo de agora, e `operacao`, com o histórico. Não guarda um log replicado com
`indice` e `epoch`: isso é do protocolo das etapas seguintes, e as secções 4.1 a 4.3
descrevem-no. O esquema está em 4.4.

**O `op_id` viaja no corpo**, como 6.1 sempre disse. O cabeçalho `X-Op-Id` que
`projeto-final/` usa é um desvio que nunca chegou a ser registado; o Protótipo 1 não
o herda.

**RF-07 e RF-08 passam a ser garantidos pelo PostgreSQL.** O estado entregue
serializava as escritas com um *lock* único em memória. Aqui não há estado em
memória para proteger: o isolamento da transação dá a leitura consistente (RF-07) e
o `SELECT ... FOR UPDATE` sobre as contas tocadas, por ordem crescente de id, dá o
conflito entre operações concorrentes (RF-08). A ordem vem de
`Operacao.contas_tocadas()`, tal como no estado entregue — o que mudou foi quem
guarda o *lock*, não quem decide a ordem.

Isto não é delegar o consenso ao motor, que a proposta proíbe e o ADR-0001 recusa:
é delegar o *lock* de linha dentro de um nó. A replicação entre nós continua por
implementar à mão, na etapa seguinte.

### 11.9 Dois nós contra a mesma base, no Protótipo 1

Decidido em setembro de 2026. Os ensaios da disciplina fazem-se com dois
portáteis a servir ao mesmo tempo, e as contas têm de ser as mesmas nos dois. A
montagem é: cada portátil corre o seu nó e o seu painel, e os dois escrevem numa
**única** base PostgreSQL gerida. Está descrita em `prototipo-1/REDE.md`.

**Não custou uma linha de código de domínio, e a razão é o desenho.** O servidor
não guarda estado entre pedidos: cada pedido abre a sua ligação, e os *locks*
(`SELECT ... FOR UPDATE`), a chave de deduplicação (`operacao.op_id`) e a ordem
total (`operacao_numero`) vivem todos na base. Dois processos em máquinas
diferentes pedem exatamente os mesmos *locks* que dois fios no mesmo processo
pediriam, e o PostgreSQL serializa-os da mesma maneira. `conexao.py` já aceitava
uma linha de ligação qualquer em `BANCO_BD`, incluindo uma com `sslmode=require`.

O que se acrescentou foi configuração (`compose.nuvem.yaml`, `.env.exemplo`), um
guião (`REDE.md`) e, sobretudo, os testes que o demonstram:
`tests/integracao/teste_dois_nos.py` levanta **dois processos** do servidor, com
`NO_ID` diferente, contra a mesma base. Dois processos e não dois fios de
propósito — contra dois fios ainda se poderia objetar que partilham memória.

**Isto não é replicação, e é a parte que não pode ser mal lida na defesa.**

| | Dois nós, uma base (Protótipo 1) | Replicação por log (etapa 2) |
|---|---|---|
| Quem garante a correção | Os *locks* de linha do PostgreSQL | O protocolo, escrito à mão |
| Onde está o dinheiro | Num sítio | Em três, com um log replicado |
| Se cair uma máquina de servidor | A outra continua a servir | A outra continua a servir |
| **Se cair a base** | **Cai tudo** | Não há uma base única para cair |
| RF-09 (eleição), RF-10 (maioria) | **Por cumprir** | Cumpridos |

A base partilhada é um ponto único de falha, e por isso esta montagem **não**
cobre F-08 nem RF-09 a RF-13. O que cobre, e antes não cobria, é RF-04 no seu
sentido literal: uma transferência pedida a um servidor mexe em contas que o
outro servidor também serve.

**Porque é que isto não é delegar o consenso ao motor**, que a proposta proíbe e
o ADR-0001 recusa: não se delega nada, porque não há consenso nenhum a acontecer.
Há uma base só, e um *lock* de linha dentro de uma base não é um algoritmo
distribuído — é o mesmo mecanismo que o Protótipo 1 já usava com um nó. A
replicação entre bases continua por implementar à mão, na etapa seguinte, tal
como o ADR-0001 decidiu.

**O que se perde, dito sem rodeios:** o servidor deixa de correr sem uma base
alcançável pelos dois portáteis, o que na prática significa uma base gerida e
uma conta num fornecedor. E cada pedido paga uma ligação TLS nova, porque não há
*pool* — a medição e o critério para acrescentar um estão em `REDE.md`.

---

## 12. Fora de âmbito

| O quê | Porquê |
|---|---|
| Autenticação e cifragem | Excluído pela proposta |
| Snapshots do estado | *Replay* do WAL basta na escala da demonstração (secção 4.2) |
| Mudança de membros em execução (RF-18) | Prioridade Baixa na proposta. Fica documentado como extensão |
| Contas repartidas entre servidores | Todos os nós têm todas as contas — é o que dispensa o *commit* em duas fases |
| Replicação entre regiões | Excluído pela proposta |
| Dependências externas além do `psycopg` | Uma só, e confinada a um módulo. Ver [`CONVENCOES.md`](CONVENCOES.md) e 11.4 |

---

## 13. Rastreabilidade

### Funcionalidades

| ID | Funcionalidade | Etapa |
|---|---|---|
| F-01 | Criar conta | Protótipo 1 |
| F-02 | Consultar saldo | Protótipo 1 |
| F-03 | Depositar e sacar | Protótipo 1 |
| F-04 | Transferir entre contas | Protótipo 1 |
| F-05 | Extrato de operações | Protótipo 1 |
| F-06 | Auditoria da soma dos saldos | Protótipo 1 |
| F-07 | Operações concorrentes | Protótipo 1 |
| F-08 | Funcionar com servidores fora do ar | Projeto final |
| F-09 | Recuperar estado após reinício | Projeto final |
| F-10 | Injeção de falhas | Projeto final |
| F-11 | Visualizar o estado do sistema | Projeto final |
| F-12 | Cliente de linha de comando | **Por cobrir** (11.8) |

### Requisitos funcionais

| ID | Etapa | Onde se cumpre |
|---|---|---|
| RF-01 | Protótipo 1 | `dominio/contas`, `POST /contas` |
| RF-02 | Protótipo 1 | `GET /contas/{id}` |
| RF-03 | Protótipo 1 | `POST /contas/{id}/deposito`, `/saque` |
| RF-04 | Protótipo 1 | `POST /transferencias`; entre servidores diferentes com a montagem de 11.9 |
| RF-05 | Protótipo 1 | Débito e crédito numa só transação (4.4, secção 5) |
| RF-06 | Protótipo 1 | Validação antes de gravar (secção 5) |
| RF-07 | Protótipo 1 | Isolamento da transação (secção 5) |
| RF-08 | Protótipo 1 | `FOR UPDATE` por conta, em ordem total (secção 5) |
| RF-09 | Projeto final | Eleição por maioria (secção 8) |
| RF-10 | Projeto final | Confirmação por maioria (secção 7) |
| RF-11 | Projeto final | Failover; com 2 caídos, somente leitura (11.1) |
| RF-12 | Projeto final | Recuperação por *replay* + reintegração (4.2, 7) |
| RF-13 | Protótipo 1 | Deduplicação por `op_id` (3.3, 4.4) |
| RF-14 | Protótipo 1 | `GET /auditoria` |
| RF-15 | Projeto final | `GET /admin/metricas` |
| RF-16 | Projeto final | `POST /admin/falha`, com sessão de ensaio exclusiva |
| RF-17 | **Por cobrir** | Não há CLI em nenhuma etapa (11.8) |
| RF-18 | — | Fora de âmbito, documentado (secção 12) |

### Requisitos não funcionais

| ID | Critério | Etapa | Como se verifica |
|---|---|---|---|
| RNF-01 | A soma nunca muda | Todas | Teste de invariante sob milhares de operações sorteadas |
| RNF-02 | Operação confirmada sobrevive | Projeto final | `SIGKILL` no primário a meio de transferências |
| RNF-03 | Novo primário em menos de 2 s | Projeto final | Medição do tempo de failover |
| RNF-04 | 500 TPS local | Projeto final | *Benchmark*; meta de medição (11.3) |
| RNF-05 | p99 abaixo de 200 ms | Projeto final | *Benchmark* com concorrência crescente |
| RNF-06 | Mesma semente, mesmo resultado | Projeto final | Semente derivada por nó (8.1) |
| RNF-07 | Log estruturado e métricas | Projeto final | Secção 10 |
| RNF-08 | Módulos com código, testes e documentação | As três | Estrutura em `CODESTYLE.md` |
| RNF-09 | Um comando em Linux e macOS | Protótipo 1 | `docker compose up`. Sem instalar nada correm só os testes do domínio (11.8) |
| RNF-10 | Cada componente documenta os seus modos de falha | As três | README de cada etapa |

**Duas linhas dizem "por cobrir", e é a sério.** F-12 e RF-17 — o cliente de linha
de comando — não existem em nenhuma pasta desde que o Protótipo 1 foi reconstruído
(11.8). O único sítio onde se veem é `git show 7b430e6`. Deixar a linha a apontar
para uma etapa dava a tabela por cumprida quando não está.
