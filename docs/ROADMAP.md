# ROADMAP — Fases do projeto

Três entregas. Cada uma numa pasta própria, autocontida, e cada uma continua a
funcionar depois de a seguinte começar.

Regras que valem para as três:

- Uma etapa entregue **não se altera**. Erros descobertos tarde corrigem-se na
  etapa em curso e registam-se na secção "o que mudou face à etapa anterior" do
  README dessa etapa.
- Uma subfase só está feita quando tem **código, testes e documentação**. Sem as
  três, está a meio (RNF-08).
- Cada pessoa escreve os testes do seu próprio módulo.

| Etapa | Pasta | Objetivo numa frase |
|---|---|---|
| Protótipo 1 | `prototipo-1/` | Um banco correto num só nó |
| Protótipo 2 | `prototipo-2/` | Sobrevive à queda de um servidor |
| Projeto final | `projeto-final/` | Prova, mede e mostra |

---

# Etapa 1 — Protótipo 1

> Um banco correto num só nó. — **entregue** em setembro de 2026, 103 testes a passar
> (`git show 7b430e6`).
>
> Foi **reaberta** a seguir à entrega para receber o PostgreSQL, a replicação, a
> injeção de falhas e o frontend, e essa decisão foi depois **desfeita**: o trabalho
> das etapas 2 e 3 tinha passado a viver na pasta da etapa 1, e deixara de haver uma
> pasta a mostrar o banco de um nó só isolado. A versão reaberta vê-se em
> `git show 3683a0f`.
>
> A etapa foi **reconstruída** sobre a pilha do projeto final — FastAPI, PostgreSQL,
> as mesmas camadas — sem replicação nem autenticação. **97 testes a passar.** A
> justificação e os quatro desvios que isto custa estão em [`SPECS.md`](SPECS.md)
> 11.8; as alíneas estão em 1.9, abaixo.

Ainda não há rede entre servidores, nem replicação, nem eleição. O que há é a base
sem a qual nada disso faz sentido: o dinheiro tem de estar certo **antes** de ser
distribuído. Um erro de arredondamento ou uma corrida entre duas *threads* que
passe despercebida nesta etapa vai parecer, na etapa 2, um erro de replicação — e
procurar-se-á no sítio errado durante dias.

**Cobre:** F-01 a F-07 · RF-01 a RF-08, RF-13, RF-14 · RNF-01, RNF-08, RNF-10

F-12 e RF-17, o cliente de linha de comando, **deixaram de estar cobertos** com a
reconstrução — o projeto final também não tem CLI. Está registado em
[`SPECS.md`](SPECS.md) 11.8 e no README da etapa, em vez de omitido.

### 1.1 Fundação do repositório — *Paulo*

- [x] Estrutura de pastas de `prototipo-1/` conforme o `CODESTYLE.md`
- [x] `banco/` com os pacotes `dominio`, `persistencia`, `cluster`, `interface`
- [x] Testes com o `unittest` da biblioteca padrão, sem ficheiro de
      configuração: `python3 -m unittest` já põe o diretório atual no
      `sys.path`
- [x] Confirmar que corre com Python 3.10+ sem `pip install` de nada
- **Pronto quando:** `python3 -m unittest discover -s tests` corre numa máquina limpa, sem venv

### 1.2 Domínio: dinheiro e contas — *Jefferson*

- [x] Conversão de texto para centavos com `decimal.Decimal`, **nunca** `float`
- [x] Formatação de centavos para `R$ 1.234,56`
- [x] `Conta` com `id`, `saldo_centavos`, `criada_em`; validação do formato do id
- [x] Hierarquia de erros com raiz `ErroDoBanco`, cada um com `codigo` e
      `estado_http`
- [x] Testes: conversão nos dois sentidos, ida e volta, valores negativos e mal
      formados, id inválido
- **Pronto quando:** nenhum `float` toca em dinheiro. O `grep` tem de
      excluir `instante` e `criada_em`, que são instantes de tempo e são
      `float` por especificação (SPECS 3.2)

### 1.3 Domínio: operações e invariante — *Jefferson*

- [x] `criar_conta`, `deposito`, `saque`, `transferencia` como funções puras sobre
      o estado
- [x] Recusa de saque e transferência que deixem saldo negativo (RF-06)
- [x] Cada operação devolve as contas que toca, **já ordenadas** por id — a ordem
      total dos *locks* nasce aqui, para ninguém ter de se lembrar dela no ponto
      de uso
- [x] Transferência aplicada por **uma única função**, sem estado intermédio (RF-05)
- [x] Extrato por conta (F-05)
- [x] Auditoria: soma de todos os saldos (RF-14, F-06)
- [x] Teste da invariante: 3000 operações sorteadas com semente fixa, a soma no
      fim é igual à do início
- **Pronto quando:** o teste da invariante passa e o domínio não importa `socket`,
  `http` nem `os`

### 1.4 Persistência: WAL e recuperação — *Jefferson*

- [x] Escrita de `EntradaDeLog` em JSONL com `write` + `flush` + `os.fsync`
- [x] Leitura do WAL no arranque e *replay* de todas as entradas
- [x] Linha final truncada: descartar e truncar o ficheiro nesse ponto
- [x] `estado.json` com `epoch` e `votou_em`, com `fsync` (já preparado para a
      etapa 2, mesmo sem uso agora)
- [x] Deduplicação por `op_id`: guardar o resultado e devolvê-lo na repetição
- [x] Testes: *replay* reconstrói o estado exato, linha truncada não quebra o
      arranque, `op_id` repetido não move dinheiro duas vezes
- **Pronto quando:** matar o processo e reiniciar devolve exatamente o mesmo saldo

### 1.5 Concorrência — *Cristhian*

- [x] *Locks* por conta, adquiridos por ordem crescente de id
- [x] `lock` único de estado por nó, a serializar aplicação **e** leitura (RF-07)
- [x] Ordem obrigatória de uma escrita conforme a secção 5 do `SPECS.md`
- [x] Teste de *deadlock*: `alice→bob` e `bob→alice` em paralelo, com limite de
      tempo, não bloqueiam
- [x] Teste de corrida: N *threads* a sacar da mesma conta, o saldo nunca fica
      negativo e nenhuma operação se perde
- [x] Teste de leitura consistente: consultas durante transferências nunca veem
      dinheiro a menos (RF-07)
- **Pronto quando:** os testes de concorrência passam 20 vezes seguidas sem falhar
  uma

### 1.6 Servidor HTTP e rotas de cliente — *Paulo*

- [x] `ThreadingHTTPServer` da biblioteca padrão, a ligar em `0.0.0.0`
- [x] Encaminhamento de rotas e leitura de corpos JSON
- [x] Rotas de cliente da secção 6.1 do `SPECS.md`
- [x] Tradução uniforme de `ErroDoBanco` para código HTTP e corpo JSON, num só
      sítio
- [x] `op_id` obrigatório em toda escrita
- [x] Testes de integração: cada rota no caminho feliz e nos erros

### 1.7 Cliente de linha de comando — *Paulo*

- [x] `argparse` com os comandos `criar-conta`, `saldo`, `depositar`, `sacar`,
      `transferir`, `extrato`, `auditoria`, `estado` (F-12, RF-17)
- [x] Geração do `op_id` **no cliente**, para a retentativa ser segura
- [x] Formatação de tabelas e de dinheiro conforme a secção 9 do `CODESTYLE.md`
- [x] Cor ANSI só quando `sys.stdout.isatty()`
- [x] Erros em três linhas, a terceira com o passo seguinte
- [x] Códigos de saída 0, 1, 2 e 3 distintos

### 1.8 Fecho da etapa — *todos*

- [x] `prototipo-1/README.md` com objetivo, execução, requisitos cobertos e
      divisão de trabalho
- [x] Modos de falha documentados: o que acontece com o disco cheio, com o
      processo morto a meio de uma escrita (RNF-10)
- [x] Todos os testes passam; o número real fica no README
- **Etapa entregue quando:** um avaliador clona o repositório, corre um comando e
  faz uma transferência sem instalar nada

> As alíneas 1.1 a 1.8 descrevem a etapa **tal como foi entregue** em `7b430e6`, e
> ficam como estão: reescrevê-las apagaria a história que estas pastas existem para
> mostrar. A reconstrução é 1.9.

### 1.9 Reconstrução sobre a pilha do projeto final — *todos*

> Porquê, e o que custa: [`SPECS.md`](SPECS.md) 11.8.

- [x] `db/esquema.sql` com duas tabelas: `conta` e `operacao` (SPECS 4.4)
- [x] `banco/dominio/` trazido do projeto final sem alterações, exceto a `para_centavos`
      passar a recusar o que não é texto (SPECS 6)
- [x] `banco/repositorio/`: `bloquear` com `FOR UPDATE` por ordem crescente de id, e
      `inserir`/`atualizar` em vez do *upsert*, que repunha o saldo de uma conta já
      existente
- [x] `banco/servico/escrita.py`: a ordem obrigatória de SPECS 5 numa só função, com
      o passo 2b — voltar a perguntar pelo `op_id` depois de tomar os *locks*
- [x] `banco/api/`: as rotas de SPECS 6.1, dinheiro como texto, `op_id` no corpo, e a
      tradução dos erros em tratadores registados na aplicação
- [x] `tests/unitarios/` a correr sem instalar nada; `tests/integracao/` a falar com
      um servidor a sério por `urllib`, e a saltar-se sozinhos com o motivo escrito
- [x] Testes de concorrência que falham se o `FOR UPDATE` for retirado — verificado
- [x] `frontend/` sem autenticação e sem *router*, com a paleta de `CODESTYLE.md` 8.1
- [x] `compose.yaml` com *healthcheck*, para o nó não arrancar antes da base
- [x] README com o que mudou, os modos de falha e o que deixou de estar coberto
- **Pronto quando:** `docker compose up --build` levanta tudo, e uma transferência
  feita no painel aparece na auditoria sem divergência

---

# Etapa 2 — Protótipo 2

> Sobrevive à queda de um servidor.
>
> **Feita, e vive em `projeto-final/`.** Chegou a executar-se dentro de
> `prototipo-1/` (11.6), mas essa decisão foi desfeita — ver 11.8 do
> [`SPECS.md`](SPECS.md). `prototipo-2/` continua vazia: a etapa não tem pasta
> própria, tem o código do projeto final.

O coração do trabalho. Aqui aparecem replicação, quórum, eleição e failover — e é
aqui que se prova, com um servidor a ser morto ao vivo, que o dinheiro não se
perde.

**Cobre:** F-08, F-09 · RF-09 a RF-13 · RNF-01 a RNF-03, RNF-06

### 2.1 Configuração do cluster — *Paulo*

- [x] `config/cluster.exemplo.json` com o formato da secção 9 do `SPECS.md`
- [x] Carregamento com validação: ids únicos, endereços alcançáveis,
      `heartbeat_ms` muito menor que o mínimo do *timeout* de eleição
- [x] Cliente HTTP interno entre nós, com *timeout* e sem bloquear o nó que chama
- [x] `config/cluster.json` no `.gitignore`
- **Pronto quando:** subir 3 nós locais e cada um listar os outros dois

### 2.2 Log de replicação — *Cristhian*

- [x] Estrutura do log em memória sobre o WAL: `ultimo_indice`, `ultimo_epoch`,
      `indice_commit`
- [x] Acrescentar entradas com verificação de `indice_anterior` e `epoch_anterior`
- [x] Truncar entradas divergentes e não confirmadas, **nunca abaixo do
      `indice_commit`**
- [x] `POST /interno/replicar` com replicação e *heartbeat* no mesmo RPC
- [x] `GET /interno/log?desde=N` para a réplica muito atrasada
- [x] Testes unitários: correspondência de log, truncagem, recusa de `epoch` menor

### 2.3 Confirmação por maioria — *Cristhian*

- [x] O primário replica em paralelo e conta-se a si próprio no quórum
- [x] Só responde ao cliente **depois** da maioria (RF-10)
- [x] `503 sem_quorum` quando a maioria não responde a tempo, com a entrada
      gravada mas não confirmada
- [x] Modo somente leitura quando a maioria está inacessível há mais de um
      *timeout* de eleição
- [x] Teste: com 2 dos 3 nós vivos as escritas passam; com 1, são recusadas e as
      leituras continuam

### 2.4 Heartbeat e deteção — *Cristhian*

- [x] *Heartbeat* a cada `heartbeat_ms`, reaproveitando `/interno/replicar`
- [x] *Timeout* de eleição **sorteado** em `[800, 1500] ms` a cada ronda
- [x] **Semente derivada por nó** (`semente_global + crc32(id)`) — com a mesma
      semente nos três, todos sorteiam o mesmo valor, candidatam-se juntos e a
      eleição nunca converge. É o erro mais caro desta etapa
- [x] Teste de reprodutibilidade: a mesma semente global produz a mesma execução
      (RNF-06)

### 2.5 Eleição e fencing — *Cristhian*

- [x] Máquina de estados réplica / candidato / primário
- [x] `POST /interno/votar` com as três condições da secção 8.2 do `SPECS.md`
- [x] `epoch` e `votou_em` gravados com `fsync` **antes** de responder ao voto
- [x] Despromoção imediata ao ver um `epoch` maior (*fencing*)
- [x] *Heartbeat* imediato ao assumir, e entrada `noop` no próprio `epoch` antes
      de aceitar escritas
- [x] Testes: nunca dois primários no mesmo `epoch`; empate resolve-se com novo
      `epoch`; um nó não vota duas vezes no mesmo `epoch`

### 2.6 Réplica e reintegração — *Jefferson*

- [x] A réplica aplica entradas até ao `indice_commit` recebido do líder
- [x] Arranque **sempre como réplica**, mesmo tendo sido primário antes de cair
- [x] Recuperação por *replay* e depois sincronização com o primário (RF-12, F-09)
- [x] Testes: nó reiniciado apanha o log e volta a participar; nó parado durante
      50 operações põe-se em dia

### 2.7 Cliente que encontra o primário — *Paulo*

- [x] Lista de endereços; segue `primario_provavel` em `409 nao_sou_primario`
- [x] Retentativa com o **mesmo** `op_id` (RF-13)
- [x] `banco.cli estado` mostra papel, `epoch` e índice de cada nó
- [x] Mensagem clara quando não há maioria, com o passo seguinte

### 2.8 Ensaio em 2 ou 3 laptops — *Paulo, com todos*

- [x] Guia de rede: IPs, portas, *firewall* — [`projeto-final/GUIA-DESPLIEGUE.md`](../projeto-final/GUIA-DESPLIEGUE.md)
- [x] **Testar cada endereço com `curl` antes de subir o cluster.** Com uma porta
      bloqueada, os sintomas — eleições sem fim, `epoch` a subir sozinho —
      parecem erro de protocolo e levam a procurar no sítio errado
      — `scripts/verificar_rede.sh`, e a tabela sintoma→causa do `REDE.md`
- [ ] **3 nós mesmo com 2 laptops** (PC1 corre A, PC2 corre B e C). Com 2 nós a
      maioria é 2 e a queda de um deixa o outro em somente leitura — não há
      failover com escrita para demonstrar
- [ ] Demonstração gravada: transferências a correr, matar o primário, o cluster
      reeleger, a auditoria dar o mesmo total
- **Pronto quando:** a demonstração corre de ponta a ponta em máquinas reais
- *Estado: o guia e os scripts estão escritos e o failover foi verificado com três
  processos reais numa máquina. Falta o ensaio nos dois laptops.*

### 2.9 Testes de falha — *Cristhian e Jefferson*

- [x] `SIGKILL` no primário a meio de transferências concorrentes; a soma no fim
      é a mesma (RNF-01, RNF-02)
- [x] Tempo de failover medido e abaixo de 2 s (RNF-03)
- [x] Retentativa depois do failover não duplica a operação
- [x] Primário antigo que regressa é rejeitado e despromove-se

### 2.10 Fecho da etapa — *todos*

- [x] `prototipo-2/README.md` completo, com a divisão de trabalho
- [x] Modos de falha documentados: partição de rede, primário lento, maioria
      perdida (RNF-10)
- [x] Decisões e desvios registados no `SPECS.md` **com a justificação**

---

# Etapa 3 — Projeto final

> Prova, mede e mostra.

O sistema já funciona. Esta etapa serve para o demonstrar de forma controlada, para
o medir com honestidade e para o apresentar.

**Cobre:** F-10, F-11 · RF-15, RF-16, RF-26 · RNF-04, RNF-05, RNF-07 a RNF-10

> **Nota de alcance:** RF-19 a RF-25 (moedas múltiplas, produtos financeiros,
> transferência externa) já estão especificados em
> `docs/entregables/01-requisitos/requisitos-funcionais.md`, mas ainda não têm
> subfase própria neste ROADMAP — fica registado como pendente de reconciliar,
> não omitido.

### 3.0 Pila expandida (Postgres, balanceador, frontend, autenticação, Docker/CI-CD)

Decidido com o grupo: em vez de subir a pilha aos poucos, esta subfase junta
o que as ADR-0002/0003 e `docs/entregables/` já tinham decidido mas nenhuma
subfase cobria ainda. Fica em `projeto-final/`, com `prototipo-2/` a
manter-se como está (Python puro, ainda não iniciada).

#### 3.0.1 Persistência real com PostgreSQL — *a definir*

- [ ] Cada nó com o seu próprio Postgres (contentor Docker), *schema* de
      [`docs/entregables/05-modelo-de-datos/modelo-fisico.md`](../entregables/05-modelo-de-datos/modelo-fisico.md)
- [ ] `repositorio/` substitui o WAL em JSONL por SQL contra esse Postgres
- [ ] **Sem replicação nativa do motor** — `cluster/` continua a decidir o
      quê replicar (Decisão 1 do `ADR-0001`); nada de `streaming replication`
      nem serviço gerido
- **Pronto quando:** matar o processo e reiniciar recupera o estado a partir
  do Postgres local, e as bases dos 2-3 nós ficam com o mesmo conteúdo

#### 3.0.2 Balanceador — *a definir*

- [ ] Serviço próprio, sem estado: pergunta `/interno/estado` aos nós,
      cacheia quem é o primário, reencaminha escritas e segue
      `409 nao_sou_primario` + `primario_provavel`
- [ ] Expõe as mesmas rotas públicas de um nó, para o cliente não notar
      diferença
- **Pronto quando:** matar o primário e o balanceador continua a encaminhar
  corretamente para o novo, sem precisar de reiniciar

#### 3.0.3 Frontend em React — *a definir*

- [ ] *Scaffold* com Vite, reaproveitando a linha gráfica de
      [`docs/entregables/02-casos-de-uso/mockups/estilo.css`](../entregables/02-casos-de-uso/mockups/estilo.css)
- [ ] Fala com a API só através do balanceador, nunca direto com um nó
- **Pronto quando:** um mockup vira ecrã real que faz uma transferência de
  ponta a ponta

#### 3.0.4 Autenticação (RF-26) — *a definir*

- [ ] `password_hash` com `PBKDF2-HMAC-SHA256`, nunca a senha em claro nem
      cifrada de forma reversível (RN-15)
- [ ] Token assinado com `HMAC-SHA256` e uma chave simétrica partilhada por
      todos os nós (RN-16)
- [ ] Teste: token emitido por um nó valida-se **noutro**, sem nenhuma
      chamada de rede entre eles
- **Pronto quando:** o login funciona e um token continua válido depois de
  um failover

#### 3.0.5 Docker e CI/CD — *a definir*

- [ ] `Dockerfile` do backend, do balanceador e do frontend
- [ ] `docker-compose.yml` a subir os 3 nós + balanceador + frontend
      localmente com um único comando
- [ ] GitHub Actions: build das imagens em cada `push`, *deploy* por SSH às
      instâncias configuradas
- **Pronto quando:** um `git push` para `main` atualiza sozinho as instâncias
  já configuradas, sem passo manual

### 3.1 Injeção de falhas — *Cristhian*

> Feita dentro de `projeto-final/`: é o que permite derrubar um nó a partir
> do CLI de qualquer laptop. Ganha uma exigência que não estava prevista — a **sessão
> de ensaio exclusiva**, para que dois operadores não injetem falhas ao mesmo tempo.

- [x] `POST /admin/falha` com `atraso`, `isolar`, `derrubar` e `limpar` (RF-16, F-10)
- [x] `isolar` faz o nó descartar mensagens dos nós indicados — permite reproduzir
      uma partição de rede num teste automático, sem mexer na *firewall*
- [ ] Teste de *split-brain*: isolar o primário, deixar os outros dois eleger, e
      verificar que o antigo não confirma nada ao voltar
      — *o mecanismo existe (`falha isolar`) e há um teste a tirar um nó do
      quórum; o cenário completo continua por escrever*
- [ ] Teste de partição simétrica: nenhum lado tem maioria, ninguém aceita escritas

### 3.2 Métricas e log estruturado — *Paulo*

- [ ] Log JSONL com o vocabulário fechado da secção 10 do `CODESTYLE.md` (RNF-07)
- [ ] `voto_negado` traz sempre **qual** das três condições falhou — sem isso,
      depurar uma eleição que não converge é adivinhar
- [ ] `GET /admin/metricas`: operações por tipo, p50 e p99, `epoch`, número de
      eleições, índices, réplicas vivas (RF-15)

### 3.3 Painel web — *Paulo*

- [ ] `GET /painel`: um ficheiro HTML com CSS embutido, servido pelo nó, sem
      framework nem *build* (F-11)
      — *existe um frontend equivalente em `projeto-final/frontend/`, servido à
      parte e publicado na Vercel; o painel embutido no nó continua por fazer*
- [x] O total em circulação em destaque, com o cronómetro de "inalterado há…"
- [ ] Faixa de mandatos com os `epoch` e quem mandou em cada um
- [x] Cartões de nó com papel por palavras e atraso em número de entradas
- [x] Estados de carregamento, de sem quórum e de sem contacto
- [ ] Atualização por `fetch` a cada segundo; legível sem JavaScript
      — *o `fetch` a cada segundo está feito; sem JavaScript a página mostra a
      estrutura mas não os números, porque não há servidor a renderizá-la*
- [ ] Cor só quando há desvio; contraste AA verificado

### 3.4 Medições — *Jefferson*

- [ ] Script de *benchmark* com concorrência crescente (1, 2, 4, 8, 16, 32)
- [ ] Vazão em TPS e latência p50/p99 (RNF-04, RNF-05)
- [ ] Investigar o estrangulamento e **registar o número real**, cumpra ou não o
      requisito. Uma medição relatada vale mais do que um requisito que parece
      cumprido
- [ ] Tabela de resultados no README da etapa

### 3.5 Suíte completa — *Cristhian e Jefferson*

- [ ] Todos os testes das três etapas a correr juntos
- [ ] Sem `sleep` de valor arbitrário: espera por condição com limite de tempo
- [ ] Execução determinística com a mesma semente (RNF-06)
- [ ] Sem testes marcados como pendentes, ou com o motivo escrito

### 3.6 Documentação e UML — *Paulo, revisto por todos*

- [ ] Diagrama de classes do domínio e da persistência
- [ ] Diagrama de classes da replicação e da eleição
- [ ] Sequência de uma transferência confirmada por maioria
- [ ] Sequência do failover com *fencing* por `epoch`
- [ ] Estados do papel de um nó
- [ ] Diagramas em Mermaid, para renderizarem sozinhos no GitHub
- [ ] `SPECS.md` atualizado com tudo o que mudou pelo caminho

### 3.7 Entrega — *todos*

- [ ] `projeto-final/README.md` com resultados, medições e divisão de trabalho
- [ ] `README.md` da raiz com o mapa das três etapas
- [ ] Rastreabilidade completa: todo F-xx, RF-xx e RNF-xx com o seu estado real
- [ ] Limitações conhecidas escritas, não omitidas
- [ ] Ensaio final nos laptops, de ponta a ponta

---

## Riscos conhecidos

Estão aqui porque já se sabe que vão aparecer. Vê-los escritos poupa dias.

| Risco | Onde aparece | O que fazer |
|---|---|---|
| Semente igual nos três nós | 2.4 | Derivar por nó. Sem isto a eleição nunca converge e parece erro de protocolo |
| Porta bloqueada pela *firewall* | 2.8 | Testar com `curl` **antes** de subir o cluster |
| Nó ligado a `127.0.0.1` | 2.8 | Ligar a `0.0.0.0`, senão não é alcançável de outro laptop |
| `heartbeat_ms` próximo do *timeout* | 2.1 | Validar a relação ao carregar a configuração |
| `float` a entrar no dinheiro | 1.2 | A invariante falha e parece erro de replicação |
| Confirmar entrada herdada por contagem | 2.5 | Gravar a `noop` do próprio `epoch` ao assumir |
| `sleep` fixo nos testes | 1.5, 3.5 | Esperar por condição; um `sleep` passa numa máquina e falha noutra |
| Deixar a etapa anterior "só mais um ajuste" | Sempre | Uma etapa entregue não se altera |
