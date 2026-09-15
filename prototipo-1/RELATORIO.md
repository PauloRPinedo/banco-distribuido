# Relatório do Protótipo 1

O que foi construído, que decisões foram tomadas, e porquê.

Este documento existe para a defesa: o código mostra **o que** o sistema faz, e
aqui fica **porque é que faz assim** — incluindo o que se decidiu não fazer.

---

## 1. O que foi entregue

Um banco completo num só nó: criar conta, saldo, depósito, saque, transferência,
extrato e auditoria, servidos por HTTP e operados por linha de comando, com o
estado a sobreviver a um reinício.

| | |
|---|---|
| Testes | 305, todos a passar |
| Código | 4192 linhas em `banco/` |
| Testes | 3348 linhas em `tests/` |
| Dependências externas | uma: `psycopg[binary]` |
| Requisitos cobertos | F-01 a F-12 · RF-01 a RF-14, RF-16, RF-17 · RNF-01 a RNF-03, RNF-06, RNF-09, RNF-10 |

> **Nota de leitura.** As secções 1 a 5 descrevem a etapa **como foi entregue** no
> commit `7b430e6`: um banco correto num nó só, com 103 testes. A secção 7
> descreve o que mudou quando a etapa foi reaberta. Manteve-se a ordem
> cronológica de propósito: a progressão do raciocínio é o que esta etapa tem
> para mostrar, e reescrever o passado apagá-la-ia.

---

## 2. As decisões, e o seu porquê

### 2.1 Dinheiro em centavos inteiros, nunca `float`

Todo valor monetário é um `int` de centavos. A conversão de texto acontece uma
única vez, na fronteira (`dominio/dinheiro.py`).

A razão não é estética. RNF-01 exige que a soma de todos os saldos seja constante
depois de milhares de operações. Com ponto flutuante essa soma desvia-se por
arredondamento, o teste da invariante falha — **e o erro parece um erro de
replicação**. Na etapa 2, perder-se-iam dias a depurar o protocolo por causa de
`0,1 + 0,2`.

A regra vale também nos testes: nenhum teste usa `float` para dinheiro.

### 2.2 A transferência é uma única função

Débito e crédito acontecem na mesma chamada, sem estado intermédio
(`Transferencia.aplicar`). Não existe instante nenhum em que o dinheiro tenha
saído de uma conta e ainda não tenha entrado na outra.

É daqui que vem a atomicidade de RF-05, e é a maior simplificação do projeto
inteiro: como na etapa 2 todos os nós vão ter todas as contas, a transferência é
sempre local ao primário, e **não é preciso commit em duas fases**.

### 2.3 A auditoria compara dois cálculos independentes

F-06 pede somar os saldos "e comparar com o total esperado". Somar duas vezes a
mesma estrutura não auditaria nada, por isso a auditoria calcula:

- **pelos saldos** — `Livro.total_centavos()`, a soma das contas;
- **pelo log** — `total_esperado()`, deduzido da sequência de operações: criar
  conta e depósito acrescentam, saque retira, transferência é neutra.

Os dois lados nunca olham para a mesma estrutura. É a igualdade entre eles que
verifica alguma coisa, e é ela que dá conteúdo a RNF-01.

### 2.4 O `op_id` é gerado pelo cliente

É o que torna a retentativa segura. Se a resposta se perde e o cliente repete, o
nó reconhece o `op_id` e devolve o resultado guardado, sem mover o dinheiro outra
vez. Se fosse o servidor a gerar o identificador, a segunda tentativa seria uma
operação nova e o dinheiro moveria-se a dobrar.

A deduplicação sobrevive ao reinício sem persistência extra: o `op_id` está em
cada entrada do WAL, e o *replay* reconstrói a tabela.

### 2.5 Ordem total dos *locks*, e onde ela nasce

`Operacao.contas_tocadas()` devolve os ids **já ordenados**, e `adquirir()` volta
a ordená-los. A regra está em dois sítios de propósito: esquecê-la produz um
*deadlock* que só aparece sob carga, e nessa altura já ninguém se lembra dela.

**Observação honesta:** nesta etapa os *locks* por conta quase não fazem nada. O
`lock` de estado do nó serializa toda a aplicação — e também toda a leitura, sem
o que uma consulta feita entre o débito e o crédito veria dinheiro desaparecido
(RF-07). O paralelismo entre contas só se vai notar quando a etapa 2 tirar a
replicação de dentro desse lock.

Existem na mesma porque a disciplina tem de nascer aqui, **testada**: 100 threads
em transferências cruzadas, 20 execuções seguidas sem uma falha.

### 2.6 Validar antes de gravar

A ordem dos passos de uma escrita não pode mudar: deduplicar, tomar os *locks*,
**validar**, gravar com `fsync`, aplicar, responder. Não se grava no log uma
operação que vai ser recusada — na etapa 2, isso seria replicar lixo para os
outros nós.

O passo que falta é o 5, replicar e esperar pela maioria. Não há abstração
nenhuma a prepará-lo: como cada etapa vive na sua pasta, fica só um comentário a
marcar o sítio. Construir hoje um mecanismo de extensão para um requisito de
amanhã é o tipo de generalidade que as convenções do projeto mandam cortar.

### 2.7 Os valores monetários viajam como texto

A API aceita `"valor": "25.00"` e **recusa** `"valor": 25.00` com `400`.

Um número JSON seria descodificado como `float` pelo `json.loads`, e aí o
`float` entrava no sistema pela porta das traseiras, apesar de todo o cuidado do
domínio. Exigir texto mantém a conversão a acontecer num sítio só.

### 2.8 Sem papel, sem eleição, sem snapshots

O SPECS manda um nó arrancar sempre como réplica. Aqui não: isso pressupõe uma
eleição que ainda não existe, e uma réplica sozinha recusaria todas as escritas.
O nó único aceita escritas sempre.

O `estado.json` com `epoch` e `votou_em` é gravado na mesma, sem ser lido para
decidir nada, para o formato do WAL não mudar entre etapas.

Não há snapshots: o estado reconstrói-se sempre por *replay* completo. À escala
da demonstração são milissegundos, e um snapshot custaria umas duzentas linhas e
um conjunto novo de casos extremos para não resolver problema nenhum.

---

## 3. Decisões que mudaram durante a implementação

### 3.1 `unittest` em vez de `pytest`

Os documentos diziam `pytest`. Ao verificar, o `pytest` só existia dentro do
`.venv` do trabalho anterior — e o ROADMAP exigia que a suíte corresse "numa
máquina limpa, sem venv".

Manter o `pytest` significaria um `pip install` em cada um dos 2 a 3 laptops da
demonstração, e a promessa de `git clone` e executar deixaria de ser verdade
justamente no dia em que interessa. Passou-se ao `unittest` da biblioteca
padrão. Quem tiver o `pytest` continua a poder usá-lo: ele corre estes ficheiros
sem alteração nenhuma.

`docs/CONVENCOES.md`, `docs/ROADMAP.md` e os README foram corrigidos.

### 3.2 Uma falha ao gravar deixava a ligação cair

Ao escrever o quadro de modos de falha deste protótipo, afirmou-se que um disco
cheio devolveria `500`. **Ao verificar, não devolvia nada**: a exceção subia até
ao `BaseHTTPRequestHandler`, que fechava a ligação sem resposta.

O saldo ficava correto — a invariante aguentou — mas o cliente lia o silêncio
como "servidor em baixo" e saía com o código 3, quando o servidor estava de pé e
apenas não conseguia gravar. Os dois problemas têm soluções diferentes: um pede
para arrancar o processo, o outro para libertar disco.

Corrigiu-se em dois sítios: o servidor passa a responder `500 erro_interno` com o
rasto no seu terminal, e o CLI distingue "não respondeu" de "não conseguiu
atender". Ficaram dois testes a fixar o comportamento.

### 3.3 O critério do `float` no ROADMAP era literal demais

O ROADMAP dizia "pronto quando nenhum `float` aparece em
`grep -rn float banco/dominio/`". Aparecem: `criada_em` e `instante` são
instantes de tempo e são `float` **por especificação** (SPECS 3.2). O critério
foi reescrito para falar de dinheiro, que era o que queria dizer.

### 3.4 Correções de menor peso

- Uma exceção intermédia em `dinheiro.py` e dois `import` escondidos dentro de
  funções foram removidos: não resolviam problema nenhum de camadas, e as
  camadas já estavam certas.
- A suíte demorava 11 segundos por causa do `poll_interval` de meio segundo do
  `serve_forever`, que o `shutdown()` tem de esperar em cada teste. Passou a 8.
- `banco/cli.py` chegou às 257 linhas e fazia duas coisas. O cliente HTTP saiu
  para `interface/cliente_http.py` — que é exatamente a parte que a etapa 2 vai
  ter de estender para encontrar o primário.

---

## 4. O que foi verificado

| Verificação | Resultado |
|---|---|
| Suíte completa, sem instalar nada | 103 testes, cerca de 8 s |
| Testes de concorrência, 20 execuções seguidas | 0 falhas |
| Avisos de recursos tratados como erros | nenhum |
| `dominio/` importa rede ou disco? | não |
| `float` em dinheiro? | nenhum |
| Módulos acima de 250 linhas | nenhum |
| Linhas acima de 90 colunas | nenhuma |
| Invariante sob 3000 operações sorteadas | soma inalterada |
| Reinício do processo | saldos e extrato idênticos |
| Saída redirecionada | sem um único escape ANSI |
| Códigos de saída 0, 1, 2, 3 | distintos e testados |

---

## 5. Limitações conhecidas

Escritas, não omitidas. A implementação é avaliada pelo que se sabe dela.

- **A vazão não foi medida.** O *benchmark* é do projeto final. Sabe-se que o
  `lock` de estado serializa tudo, incluindo o `fsync`, e que isso é um limite
  claro — mas não se põe um número onde não houve medição.
- **Um nó só.** Sem replicação, um disco perdido é o banco perdido. É o problema
  que a etapa 2 existe para resolver.
- **O WAL cresce sem limite.** Aceitável à escala da demonstração; se crescesse,
  o *replay* no arranque começaria a doer.
- **Sem autenticação nem cifragem**, por decisão da proposta.
- **RF-18** (adicionar e remover servidores) continua fora de âmbito.

---

## 6. O que a etapa 2 herda

- O domínio puro e determinístico: a mesma sequência de operações dá sempre o
  mesmo estado, que é o que faz a replicação por log funcionar.
- O formato da entrada de log, com o campo `epoch` já lá.
- A deduplicação por `op_id`, que passa a ser o que impede uma retentativa
  depois de um failover de duplicar dinheiro (RF-13).
- A ordem total dos *locks*, já testada contra *deadlock*.
- `interface/cliente_http.py`, que é onde entra a descoberta do primário.
- O ponto exato, marcado a comentário em `cluster/no.py`, onde a replicação e a
  espera pela maioria se inserem.


---

## 7. A reabertura da etapa (setembro de 2026)

Depois da entrega, o grupo decidiu alargar o âmbito do Protótipo 1: PostgreSQL em
vez do WAL, replicação real entre laptops, injeção de falhas com sessão exclusiva
e um frontend web. Isto contraria a regra de que uma etapa entregue não se altera,
e o que se perde está escrito em [`SPECS.md`](../docs/SPECS.md) 11.6 — deixa de
haver uma pasta que mostre o banco de um nó só a funcionar isolado. O estado
entregue continua acessível em `git show 7b430e6`.

### 7.1 O PostgreSQL entrou por um porto, não por substituição direta

A tentação era trocar `Wal` por `ArmazemPostgres` e seguir. Fez-se outra coisa:
criou-se a interface `ArmazemDeLog` e três implementações — PostgreSQL, ficheiro e
memória.

Não foi gosto de abstrair. Foi para manter uma promessa concreta: **os 305 testes
correm numa máquina sem PostgreSQL instalado**. Com uma dependência dura, a suíte
passaria a exigir uma base a funcionar em cada laptop, e o primeiro dia em que ela
não arrancasse seria o dia em que ninguém correria os testes. Os 27 que exigem a
base saltam-se sozinhos, com o motivo escrito.

A terceira implementação, a de ficheiro, tem outra função: é a saída de emergência
da demonstração. `--armazem ficheiro` e o cluster funciona igual.

### 7.2 O dinheiro nunca é uma coluna

Em `registo_do_log`, os valores vivem dentro de `dados`, em `jsonb`, como inteiros
de centavos. Três tipos foram recusados, e o porquê de cada um está em SPECS 4.3:
`NUMERIC(12,2)` criaria um segundo sítio de conversão, `MONEY` depende do
`lc_monetary` do servidor — dois laptops com *locale* diferente dariam valores
diferentes — e `DOUBLE PRECISION` é literalmente o que RNF-01 proíbe.

Há um teste-guarda no contrato do armazém: grava-se `9007199254740993` centavos,
um inteiro acima de 2^53 onde um `float` perde o último dígito, e verifica-se que
o que volta é `int` e é o mesmo número.

### 7.3 Dois locks, e a razão é de correção

O nó tem o `lock` de estado, que já existia, e ganhou um segundo para a eleição. A
regra que os acompanha — nunca tomar o de estado tendo o de eleição — está escrita
no docstring de `no.py`.

Não é arrumação. `/interno/votar` **tem de** conseguir responder enquanto uma
escrita espera pela maioria, porque é exatamente essa a situação em que a eleição
faz falta. Se partilhassem o lock, um primário atascado sem quórum bloquearia a
eleição que o desataria, e o cluster ficaria preso à espera de si próprio.

### 7.4 A sessão de ensaio é um *lease*, não consenso

Com dois laptops e três pessoas, todas com o CLI, dois operadores a derrubar nós
ao mesmo tempo produzem um cluster sem maioria por acidente — e o que se vê no ecrã
deixa de ser a experiência que se estava a fazer.

A tranca vive no primário e viaja para as réplicas montada no heartbeat.
Rejeitaram-se duas alternativas:

- **local a cada nó** não excluiria nada: um operador tomava-a em A e o outro em B;
- **pelo log replicado** sobreviveria ao failover, mas meteria estado operativo na
  pista de auditoria do dinheiro, correria os índices e sujaria o extrato das
  contas com eventos que não são operações bancárias.

Morre com o primário, e ainda bem: quem tem a sessão é exatamente quem acabou de o
matar, e voltar a tomá-la é um comando.

### 7.5 O que se descobriu ao verificar

Três erros apanhados por olhar para o sistema a correr, e não por raciocinar sobre
ele. Ficam escritos porque a forma como apareceram é a parte útil.

**O nó intruso envenenava a base do nó legítimo.** `ArmazemPostgres` inseria a sua
linha em `estado_do_no` e só depois verificava se a base já era de outro nó. Em
`autocommit` já não havia transação para desfazer: a base ficava com dois donos e,
a partir daí, nem o nó legítimo a conseguia abrir. Uma tentativa errada arruinava
o nó certo. Passou a ler antes de escrever, e há dois testes a fixá-lo.

**Um nó derrubado a meio de uma escrita dava `500`.** O `ThreadPoolExecutor` do
replicador recusava trabalho novo depois do `shutdown`, e o `RuntimeError` subia
até à camada HTTP como erro interno. O que houve foi um nó a fechar
ordenadamente, e a resposta correta é `503 sem_quorum` — que é a verdade e diz ao
cliente que vale a pena repetir.

**A tranca de ensaio não excluía ninguém.** Na primeira versão a sessão tomava-se
em qualquer nó, e a fixação não viajava para as réplicas. Resultado: dois
operadores tomavam-na em nós diferentes e nenhum era recusado; depois de corrigir
o primeiro problema, a réplica sabia que alguém tinha a sessão mas não reconhecia
o dono, e recusava toda a gente — incluindo quem a tinha. Tomar passou a exigir o
primário, e a fixação passou a viajar no heartbeat.

### 7.6 O que se decidiu não fazer

- **Não se usa a replicação nativa do PostgreSQL.** A proposta exige que o
  consenso seja implementado de raiz; *streaming replication* resolveria o
  problema apagando o trabalho que a disciplina avalia.
- **Não há `GET /painel`.** O frontend é servido à parte. O painel embutido no nó
  continua por fazer.
- **A alternativa *pipelined* para a espera pela maioria ficou documentada e não
  implementada.** Soltar o `lock` de estado durante a ida e volta melhoraria a
  latência das leituras, mas SPECS 11.3 já trata RNF-04 como meta de medição, e
  escolher o simples é coerente com o critério que o projeto se fixou.

### 7.7 Limitações novas, escritas e não omitidas

- **A vazão continua por medir.** O `lock` de estado serializa tudo, agora
  incluindo a espera pela maioria. Não se põe um número onde não houve medição.
- **Falta o teste de *split-brain* completo.** `falha isolar` existe e há um teste
  a tirar um nó do quórum, mas o cenário dos dois lados sem maioria não está
  escrito.
- **Não há log estruturado nem métricas** (RNF-07, RF-15).
- **`operacoes.py` tem 273 linhas e `no.py` 251**, acima das ~250 que o CODESTYLE
  marca. `no.py` já foi dividido uma vez, e o que sobra é coeso; `operacoes.py`
  são as cinco operações e o registo, que se leem juntas.
- **O túnel expõe um banco sem autenticação à internet** enquanto está de pé.
  Levanta-se para a demonstração e fecha-se a seguir. É coerente com a proposta,
  que exclui autenticação do âmbito, mas omiti-lo seria desonesto.


---

## 8. O frontend, e o que ele obrigou a mudar

O frontend existia desde a secção 7, mas era incoerente com o seu próprio desenho:
o canvas definia cinco ecrãs e o código empilhava tudo num scroll único, noutra
ordem e com outro agrupamento. Dois artefactos a descrever coisas diferentes.

### 8.1 Quatro ecrãs, e a configuração fora do caminho

`Início`, `Operações`, `Extrato` e `Cluster`, com o estado no *hash* do endereço
para sobreviver a uma recarga. Navegação com `<button role="tab">` a sério —
setas, `Home`, `End`, `aria-selected` — e não `<div>` com `onclick`.

O `Endereço do banco` saiu da primeira posição para um botão na cabeceira. Era
configuração a ocupar o lugar de honra: a primeira coisa que se via ao abrir um
banco era um formulário para colar uma URL.

### 8.2 O ecrã não mostrava o failover, que é o que há para mostrar

O painel do cluster desenhava **um** cartão — o do nó ao qual o túnel aponta —
embora o desenho mostrasse três. Justamente o que interessa numa defesa (quem caiu,
quem assumiu, quanto vai atrasado cada um) era o que não se via.

Nasceu `GET /interno/cluster` (SPECS 6.2): o nó pergunta aos pares em paralelo e
devolve todos. É uma rota nova e não um campo a mais em `/interno/estado` de
propósito — aquela é chamada em cada *heartbeat*, e pô-la a fazer chamadas de rede
tornaria o caminho quente caro e recursivo.

A implementação foi depois extraída para `cluster/vista.py`, com **executor
próprio**. Não é arrumação: partilhar o `ThreadPoolExecutor` de dois lugares que
envia os *heartbeats* deixaria uma página aberta atrasar o batimento, e um
batimento atrasado derruba um primário saudável.

### 8.3 O que se descobriu, outra vez, a olhar em vez de a raciocinar

**Os quatro ecrãs apareciam todos ao mesmo tempo.** O atributo `hidden` do HTML
vale `display: none` na folha do navegador, e qualquer `display` do autor
ganha-lhe — `.cartao { display: grid }` e `[role=tabpanel] { display: grid }`
anulavam-no. Os testes de `aria-selected` passavam na mesma; só se viu na captura
de ecrã. Ficou `[hidden] { display: none !important }` e uma asserção de
visibilidade no teste, para não voltar.

**O frontend não conseguia escrever nada.** Com o túnel apontado a uma réplica,
toda escrita levava `409 nao_sou_primario` com um `primario_provavel` que é um
endereço de LAN — inalcançável do navegador. Com um único túnel, a página era
inútil. Apareceu `--encaminhar-escritas`: a réplica reenvia o pedido ao primário
como cliente puro, sem gravar nada, por isso a ordem da secção 5 fica intacta, e o
`op_id` do corpo original torna o reenvio seguro de repetir.

**Uma conta apagada gerava um 404 por segundo, para sempre.** A página guardava os
ids das contas que tinha visto e voltava a pedi-los a cada atualização. Passou a
esquecer as que o banco já não conhece — distinguindo um `404` de um erro de rede,
porque nesse a conta existe e o que falhou foi a ligação.

### 8.4 Onde se desviou das recomendações de interface, e porquê

As *Web Interface Guidelines* pedem `Intl.NumberFormat` para moeda. Aqui **não**:
`emReais()` trabalha sobre inteiros de centavos, e o `Intl` recebe um número em
reais — obrigaria a dividir por 100 e a meter um `float` no dinheiro, que é
exatamente o que RNF-01 proíbe. O resto aplicou-se: `aria-live` na região de
avisos, `prefers-reduced-motion`, `touch-action`, alvos de toque de 44 px, e o erro
ao lado do campo que o causou com o foco a saltar para lá.

### 8.5 O que continua por fazer no frontend

- **A página não funciona sem JavaScript.** Mostra a estrutura, não os números: não
  há servidor a renderizá-la, e pô-lo a fazê-lo seria um projeto à parte.
- **`GET /painel` continua a não existir.** O frontend é servido em separado, não
  pelo nó, e é por isso que F-11 se cumpre por um caminho diferente do previsto.
- **A publicação depende de um túnel.** Enquanto ele estiver de pé, um banco sem
  autenticação fica acessível a partir da internet. Levanta-se para a demonstração
  e fecha-se a seguir.
