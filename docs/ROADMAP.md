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

> Um banco correto num só nó.

Ainda não há rede entre servidores, nem replicação, nem eleição. O que há é a base
sem a qual nada disso faz sentido: o dinheiro tem de estar certo **antes** de ser
distribuído. Um erro de arredondamento ou uma corrida entre duas *threads* que
passe despercebida nesta etapa vai parecer, na etapa 2, um erro de replicação — e
procurar-se-á no sítio errado durante dias.

**Cobre:** F-01 a F-07, F-12 · RF-01 a RF-08, RF-14, RF-17 · RNF-01, RNF-09

### 1.1 Fundação do repositório — *Paulo*

- [ ] Estrutura de pastas de `prototipo-1/` conforme o `CODESTYLE.md`
- [ ] `banco/` com os pacotes `dominio`, `persistencia`, `cluster`, `interface`
- [ ] Configurar `pytest` sem instalação (`pytest.ini` com `pythonpath`)
- [ ] Confirmar que corre com Python 3.10+ sem `pip install` de nada
- **Pronto quando:** `python3 -m pytest -q` corre numa máquina limpa, sem venv

### 1.2 Domínio: dinheiro e contas — *Jefferson*

- [ ] Conversão de texto para centavos com `decimal.Decimal`, **nunca** `float`
- [ ] Formatação de centavos para `R$ 1.234,56`
- [ ] `Conta` com `id`, `saldo_centavos`, `criada_em`; validação do formato do id
- [ ] Hierarquia de erros com raiz `ErroDoBanco`, cada um com `codigo` e
      `estado_http`
- [ ] Testes: conversão nos dois sentidos, ida e volta, valores negativos e mal
      formados, id inválido
- **Pronto quando:** nenhum `float` aparece em `grep -rn float banco/dominio/`

### 1.3 Domínio: operações e invariante — *Jefferson*

- [ ] `criar_conta`, `deposito`, `saque`, `transferencia` como funções puras sobre
      o estado
- [ ] Recusa de saque e transferência que deixem saldo negativo (RF-06)
- [ ] Cada operação devolve as contas que toca, **já ordenadas** por id — a ordem
      total dos *locks* nasce aqui, para ninguém ter de se lembrar dela no ponto
      de uso
- [ ] Transferência aplicada por **uma única função**, sem estado intermédio (RF-05)
- [ ] Extrato por conta (F-05)
- [ ] Auditoria: soma de todos os saldos (RF-14, F-06)
- [ ] Teste da invariante: 3000 operações sorteadas com semente fixa, a soma no
      fim é igual à do início
- **Pronto quando:** o teste da invariante passa e o domínio não importa `socket`,
  `http` nem `os`

### 1.4 Persistência: WAL e recuperação — *Jefferson*

- [ ] Escrita de `EntradaDeLog` em JSONL com `write` + `flush` + `os.fsync`
- [ ] Leitura do WAL no arranque e *replay* de todas as entradas
- [ ] Linha final truncada: descartar e truncar o ficheiro nesse ponto
- [ ] `estado.json` com `epoch` e `votou_em`, com `fsync` (já preparado para a
      etapa 2, mesmo sem uso agora)
- [ ] Deduplicação por `op_id`: guardar o resultado e devolvê-lo na repetição
- [ ] Testes: *replay* reconstrói o estado exato, linha truncada não quebra o
      arranque, `op_id` repetido não move dinheiro duas vezes
- **Pronto quando:** matar o processo e reiniciar devolve exatamente o mesmo saldo

### 1.5 Concorrência — *Cristhian*

- [ ] *Locks* por conta, adquiridos por ordem crescente de id
- [ ] `lock` único de estado por nó, a serializar aplicação **e** leitura (RF-07)
- [ ] Ordem obrigatória de uma escrita conforme a secção 5 do `SPECS.md`
- [ ] Teste de *deadlock*: `alice→bob` e `bob→alice` em paralelo, com limite de
      tempo, não bloqueiam
- [ ] Teste de corrida: N *threads* a sacar da mesma conta, o saldo nunca fica
      negativo e nenhuma operação se perde
- [ ] Teste de leitura consistente: consultas durante transferências nunca veem
      dinheiro a menos (RF-07)
- **Pronto quando:** os testes de concorrência passam 20 vezes seguidas sem falhar
  uma

### 1.6 Servidor HTTP e rotas de cliente — *Paulo*

- [ ] `ThreadingHTTPServer` da biblioteca padrão, a ligar em `0.0.0.0`
- [ ] Encaminhamento de rotas e leitura de corpos JSON
- [ ] Rotas de cliente da secção 6.1 do `SPECS.md`
- [ ] Tradução uniforme de `ErroDoBanco` para código HTTP e corpo JSON, num só
      sítio
- [ ] `op_id` obrigatório em toda escrita
- [ ] Testes de integração: cada rota no caminho feliz e nos erros

### 1.7 Cliente de linha de comando — *Paulo*

- [ ] `argparse` com os comandos `criar-conta`, `saldo`, `depositar`, `sacar`,
      `transferir`, `extrato`, `auditoria`, `estado` (F-12, RF-17)
- [ ] Geração do `op_id` **no cliente**, para a retentativa ser segura
- [ ] Formatação de tabelas e de dinheiro conforme a secção 9 do `CODESTYLE.md`
- [ ] Cor ANSI só quando `sys.stdout.isatty()`
- [ ] Erros em três linhas, a terceira com o passo seguinte
- [ ] Códigos de saída 0, 1, 2 e 3 distintos

### 1.8 Fecho da etapa — *todos*

- [ ] `prototipo-1/README.md` com objetivo, execução, requisitos cobertos e
      divisão de trabalho
- [ ] Modos de falha documentados: o que acontece com o disco cheio, com o
      processo morto a meio de uma escrita (RNF-10)
- [ ] Todos os testes passam; o número real fica no README
- **Etapa entregue quando:** um avaliador clona o repositório, corre um comando e
  faz uma transferência sem instalar nada

---

# Etapa 2 — Protótipo 2

> Sobrevive à queda de um servidor.

O coração do trabalho. Aqui aparecem replicação, quórum, eleição e failover — e é
aqui que se prova, com um servidor a ser morto ao vivo, que o dinheiro não se
perde.

**Cobre:** F-08, F-09 · RF-09 a RF-13 · RNF-01 a RNF-03, RNF-06

### 2.1 Configuração do cluster — *Paulo*

- [ ] `config/cluster.exemplo.json` com o formato da secção 9 do `SPECS.md`
- [ ] Carregamento com validação: ids únicos, endereços alcançáveis,
      `heartbeat_ms` muito menor que o mínimo do *timeout* de eleição
- [ ] Cliente HTTP interno entre nós, com *timeout* e sem bloquear o nó que chama
- [ ] `config/cluster.json` no `.gitignore`
- **Pronto quando:** subir 3 nós locais e cada um listar os outros dois

### 2.2 Log de replicação — *Cristhian*

- [ ] Estrutura do log em memória sobre o WAL: `ultimo_indice`, `ultimo_epoch`,
      `indice_commit`
- [ ] Acrescentar entradas com verificação de `indice_anterior` e `epoch_anterior`
- [ ] Truncar entradas divergentes e não confirmadas, **nunca abaixo do
      `indice_commit`**
- [ ] `POST /interno/replicar` com replicação e *heartbeat* no mesmo RPC
- [ ] `GET /interno/log?desde=N` para a réplica muito atrasada
- [ ] Testes unitários: correspondência de log, truncagem, recusa de `epoch` menor

### 2.3 Confirmação por maioria — *Cristhian*

- [ ] O primário replica em paralelo e conta-se a si próprio no quórum
- [ ] Só responde ao cliente **depois** da maioria (RF-10)
- [ ] `503 sem_quorum` quando a maioria não responde a tempo, com a entrada
      gravada mas não confirmada
- [ ] Modo somente leitura quando a maioria está inacessível há mais de um
      *timeout* de eleição
- [ ] Teste: com 2 dos 3 nós vivos as escritas passam; com 1, são recusadas e as
      leituras continuam

### 2.4 Heartbeat e deteção — *Cristhian*

- [ ] *Heartbeat* a cada `heartbeat_ms`, reaproveitando `/interno/replicar`
- [ ] *Timeout* de eleição **sorteado** em `[800, 1500] ms` a cada ronda
- [ ] **Semente derivada por nó** (`semente_global + crc32(id)`) — com a mesma
      semente nos três, todos sorteiam o mesmo valor, candidatam-se juntos e a
      eleição nunca converge. É o erro mais caro desta etapa
- [ ] Teste de reprodutibilidade: a mesma semente global produz a mesma execução
      (RNF-06)

### 2.5 Eleição e fencing — *Cristhian*

- [ ] Máquina de estados réplica / candidato / primário
- [ ] `POST /interno/votar` com as três condições da secção 8.2 do `SPECS.md`
- [ ] `epoch` e `votou_em` gravados com `fsync` **antes** de responder ao voto
- [ ] Despromoção imediata ao ver um `epoch` maior (*fencing*)
- [ ] *Heartbeat* imediato ao assumir, e entrada `noop` no próprio `epoch` antes
      de aceitar escritas
- [ ] Testes: nunca dois primários no mesmo `epoch`; empate resolve-se com novo
      `epoch`; um nó não vota duas vezes no mesmo `epoch`

### 2.6 Réplica e reintegração — *Jefferson*

- [ ] A réplica aplica entradas até ao `indice_commit` recebido do líder
- [ ] Arranque **sempre como réplica**, mesmo tendo sido primário antes de cair
- [ ] Recuperação por *replay* e depois sincronização com o primário (RF-12, F-09)
- [ ] Testes: nó reiniciado apanha o log e volta a participar; nó parado durante
      50 operações põe-se em dia

### 2.7 Cliente que encontra o primário — *Paulo*

- [ ] Lista de endereços; segue `primario_provavel` em `409 nao_sou_primario`
- [ ] Retentativa com o **mesmo** `op_id` (RF-13)
- [ ] `banco.cli estado` mostra papel, `epoch` e índice de cada nó
- [ ] Mensagem clara quando não há maioria, com o passo seguinte

### 2.8 Ensaio em 2 ou 3 laptops — *Paulo, com todos*

- [ ] Guia de rede: IPs, portas, *firewall*
- [ ] **Testar cada endereço com `curl` antes de subir o cluster.** Com uma porta
      bloqueada, os sintomas — eleições sem fim, `epoch` a subir sozinho —
      parecem erro de protocolo e levam a procurar no sítio errado
- [ ] **3 nós mesmo com 2 laptops** (PC1 corre A, PC2 corre B e C). Com 2 nós a
      maioria é 2 e a queda de um deixa o outro em somente leitura — não há
      failover com escrita para demonstrar
- [ ] Demonstração gravada: transferências a correr, matar o primário, o cluster
      reeleger, a auditoria dar o mesmo total
- **Pronto quando:** a demonstração corre de ponta a ponta em máquinas reais

### 2.9 Testes de falha — *Cristhian e Jefferson*

- [ ] `SIGKILL` no primário a meio de transferências concorrentes; a soma no fim
      é a mesma (RNF-01, RNF-02)
- [ ] Tempo de failover medido e abaixo de 2 s (RNF-03)
- [ ] Retentativa depois do failover não duplica a operação
- [ ] Primário antigo que regressa é rejeitado e despromove-se

### 2.10 Fecho da etapa — *todos*

- [ ] `prototipo-2/README.md` completo, com a divisão de trabalho
- [ ] Modos de falha documentados: partição de rede, primário lento, maioria
      perdida (RNF-10)
- [ ] Decisões e desvios registados no `SPECS.md` **com a justificação**

---

# Etapa 3 — Projeto final

> Prova, mede e mostra.

O sistema já funciona. Esta etapa serve para o demonstrar de forma controlada, para
o medir com honestidade e para o apresentar.

**Cobre:** F-10, F-11 · RF-15, RF-16 · RNF-04, RNF-05, RNF-07 a RNF-10

### 3.1 Injeção de falhas — *Cristhian*

- [ ] `POST /admin/falha` com `atraso`, `isolar`, `derrubar` e `limpar` (RF-16, F-10)
- [ ] `isolar` faz o nó descartar mensagens dos nós indicados — permite reproduzir
      uma partição de rede num teste automático, sem mexer na *firewall*
- [ ] Teste de *split-brain*: isolar o primário, deixar os outros dois eleger, e
      verificar que o antigo não confirma nada ao voltar
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
- [ ] O total em circulação em destaque, com o cronómetro de "inalterado há…"
- [ ] Faixa de mandatos com os `epoch` e quem mandou em cada um
- [ ] Cartões de nó com papel por palavras e atraso em número de entradas
- [ ] Estados de carregamento, de sem quórum e de sem contacto
- [ ] Atualização por `fetch` a cada segundo; legível sem JavaScript
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
