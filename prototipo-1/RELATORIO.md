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
| Testes | 103, todos a passar |
| Código | 1408 linhas em `banco/` |
| Testes | 1226 linhas em `tests/` |
| Dependências externas | nenhuma |
| Requisitos cobertos | F-01 a F-07, F-12 · RF-01 a RF-08, RF-14, RF-17 · RNF-01, RNF-09 |

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
