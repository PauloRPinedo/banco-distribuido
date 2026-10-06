# O que mudou do Protótipo 1 para o Protótipo 2

**Numa frase:** o Protótipo 1 é um banco correto num nó, contra uma base; o
Protótipo 2 é o mesmo banco em **três nós, cada um com a sua base**, que
replicam cada escrita por maioria e continuam a funcionar quando o primário
morre.

O Protótipo 1 deixava um lugar vazio no caminho de uma escrita — o passo 5,
"replicar e esperar pela maioria" — e dizia que a etapa 2 o preenchia. É isso,
no essencial, que esta etapa faz. O resto do que mudou ou é consequência disso
(utilizadores e taxas também têm de ser replicados, o cliente precisa de um
balanceador que saiba quem é o primário) ou são os requisitos de negócio
RF-19 a RF-25, que entram aqui.

---

## Visto de fora

| | Protótipo 1 | Protótipo 2 |
|---|---|---|
| Servidores | 1 nó (ou 2 contra a mesma base) | 3 nós |
| Bases de dados | 1 PostgreSQL, partilhado | 3 PostgreSQL, um por nó |
| Se o nó morre | Com um nó, o banco para; com dois, o outro serve | Outro nó assume em ~1,2 s; nada se perde |
| Se a base morre | O banco para (ponto único de falha) | Cai esse nó; os outros dois continuam |
| Uma escrita é durável quando… | o PostgreSQL faz commit | está no log de 2 dos 3 nós |
| Quem o cliente chama | o nó, em `:8001` | o balanceador, em `:8000`, que encontra o primário |
| Sessão | nenhuma: qualquer um mexe em qualquer conta | registo, login e token; cada conta tem dono |
| Moedas | só BRL | BRL, USD e PEN, com câmbio |
| Produtos | conta simples | corrente, poupança e prazo fixo, com juros |
| Outros bancos | — | transferência externa com confirmação ou devolução |
| Painel | separadores Contas, Transferir e Auditoria, sem login | + login e separador Cluster, com os três nós ao vivo |
| `docker compose up` | 3 contentores | 8 contentores |
| Testes | 111 (55 sem dependências) | 251 (165 sem dependências) |

---

## Por dentro

### O caminho de uma escrita

No Protótipo 1, uma escrita era uma transação do PostgreSQL, feita por
`ServicoDeEscrita.aplicar()`:

```
op_id já aplicado? → FOR UPDATE das contas → validar → UPDATE + INSERT → COMMIT
```

No Protótipo 2 é a mesma sequência, partida em duas metades com a replicação no
meio:

```
primário, No.executar():
  sou primário e vejo a maioria? → op_id já aplicado? → validar contra as tabelas
  → gravar a entrada no log → replicar → maioria respondeu? → confirmar
AplicadorPostgres.aplicar(entrada), em cada nó:
  FOR UPDATE das contas → aplicar a operação do domínio → UPDATE + INSERT
  → avançar ultimo_aplicado → COMMIT
```

A segunda metade corre **igual no primário e nas réplicas**: é isso que deixa as
três bases idênticas. As tabelas de cada nó deixam de ser a fonte da verdade e
passam a ser a **materialização do log confirmado**.

### Peças novas

| Pasta / ficheiro | O que é |
|---|---|
| `backend/banco/cluster/` | O protocolo inteiro: `no.py`, `eleicao.py`, `log_de_replicacao.py`, `replicacao.py`, `armazem_postgres.py`, `falhas.py`, `operacoes_de_sistema.py` |
| `backend/banco/servico/aplicador.py` | Aplica uma entrada confirmada às tabelas, numa transação |
| `backend/banco/autenticacao/` | Hash da senha com sal, token assinado com `SECRET_KEY` |
| `backend/banco/integracoes/` | O outro banco, simulado |
| `backend/banco/api/rotas_internas.py` | `/interno/estado`, `/interno/cluster`, `/interno/replicar`, `/interno/votar`, `/interno/log`, `/admin/falha` |
| `backend/banco/api/rotas_auth.py`, `rotas_admin.py`, `seguranca.py` | Registo, login, dono da conta, taxas, juros |
| `balanceador/` | Descobre o primário em paralelo, manda-lhe tudo, redescobre e repete uma vez se ele mudar |
| `config/cluster.exemplo.json` | Os três nós e os tempos do protocolo |
| `frontend/src/paginas/Cluster.jsx` | Os três nós ao vivo |
| `provas/` | Uma execução de ponta a ponta com a queda do primário, e capturas |

### A organização do código

O Protótipo 1 tinha `banco/` na raiz da pasta. Aqui há três aplicações, por
isso cada uma tem a sua: `backend/`, `balanceador/` e `frontend/`. Dentro de
`backend/banco/` as camadas são as mesmas e as setas apontam para o mesmo lado
(`api → servico → {dominio, repositorio}`), com `cluster/` entre o serviço e o
repositório.

### A base de dados

| Tabela | Protótipo 1 | Protótipo 2 |
|---|---|---|
| `conta` | id, saldo, criada_em | + `usuario_id` (dono), `moeda`, `produto`, taxa de juros, vencimento, últimos juros creditados |
| `operacao` | `op_id` até 64 caracteres; `numero` de uma sequência; 4 tipos | `op_id` até 80; `numero` = **índice do log**, igual nos três nós; tipos de câmbio, juros, transferência externa e desfecho |
| `usuario` | — | nome, email único, hash da senha (com o sal) |
| `taxa_cambio` | — | histórico de taxas, em milionésimos inteiros |
| `sistema_externo` | — | os bancos para onde se transfere |
| `log_replicado` | — | o log: índice, `epoch`, `op_id` único, tipo, dados, instante |
| `estado_do_no` | — | `epoch`, voto, `indice_commit` e `ultimo_aplicado` deste nó |

A sequência `operacao_numero` desaparece: com três bases, três sequências dariam
três numerações. O índice do log é o mesmo em todas.

### A API

As rotas do Protótipo 1 continuam com o mesmo contrato: dinheiro como texto,
`op_id` escolhido pelo cliente e enviado no corpo, id da conta escolhido pelo
cliente, a mesma forma de erro. O que muda:

- **Pedem sessão** (`Authorization: Bearer <token>`): abrir conta, listar as
  minhas, saldo, extrato, saque e transferência — as quatro últimas só ao dono.
  O depósito continua aberto.
- **O dono da conta vem do token**, nunca do corpo.
- **Rotas novas:** `/auth/registo`, `/auth/login`, `GET /contas`,
  `/transferencias/conversao`, `/transferencias/autotransferencia`,
  `/transferencias/externa`, `/taxas/...`, `/admin/taxas`, `/admin/juros`,
  `/sistemas-externos`, e as `/interno/*` do protocolo.
- **Erros novos:** `sem_sessao` e `credenciais_invalidas` 401, `proibido` 403,
  `moedas_diferentes`, `conta_bloqueada`, `taxa_indisponivel` e
  `email_duplicado` 409, `nao_sou_primario` 409, `sem_quorum`,
  `somente_leitura` e `sem_primario` 503.

---

## O que se manteve, de propósito

- **O domínio é puro:** `banco/dominio/` não importa rede, disco nem relógio, e
  testa-se sem instalar nada.
- **Dinheiro em centavos inteiros**, convertido de texto uma vez, na fronteira.
  As taxas seguem a mesma regra, em milionésimos.
- **O `op_id` do cliente e a resposta guardada.** No Protótipo 1 protegiam de um
  pedido repetido; aqui protegem também de um pedido repetido **depois de um
  failover**, que é quando o cliente mais precisa de repetir.
- **`SELECT … FOR UPDATE` por ordem crescente de id**, agora ao aplicar cada
  entrada.
- **A auditoria que soma de duas maneiras** — saldos contra histórico — agora
  separada por moeda.
- **A mesma pilha:** FastAPI, uvicorn, psycopg2, PostgreSQL 16, React + Vite.

## O que se deixou

- **Os dois portáteis contra a mesma base** (`compose.nuvem.yaml` e `REDE.md` do
  Protótipo 1). Partilhar a base era justamente o ponto único de falha; aqui
  cada nó tem a sua, e pôr nós em máquinas diferentes faz-se com um
  `cluster.json` com os endereços de cada um.
- **O cliente de linha de comando** (F-12, RF-17) continua por fazer, como no
  Protótipo 1.

---

## Requisitos

| | Protótipo 1 | Protótipo 2 |
|---|---|---|
| RF-01 a RF-08, RF-14 | cobertos | cobertos |
| RF-09 a RF-13 — eleição, replicação por maioria, queda de um nó, reintegração, seguir o primário | fora da etapa | cobertos |
| RF-15 — métricas | fora da etapa | por fazer |
| RF-16 — injeção de falhas | fora da etapa | coberto (`/admin/falha`) |
| RF-19 a RF-25 — moedas, câmbio, produtos, juros, outro banco | — | cobertos |
| RNF-02, RNF-03 — sem perda, failover em < 2 s | fora da etapa | cobertos (1,23 s) |
| RNF-04, RNF-05 — débito | — | **por medir** |
| F-12, RF-17 — cliente de linha de comando | por fazer | por fazer |

---

## Modos de falha: antes e agora

| Situação | Protótipo 1 | Protótipo 2 |
|---|---|---|
| O nó que serve morre | Um nó: banco parado. Dois: o outro serve | Outro nó é eleito; o cliente repete com o mesmo `op_id` e recebe a resposta certa |
| A base fica inacessível | Todas as rotas dão 500 | Só esse nó cai; os outros dois têm maioria |
| Morre a meio de uma transferência | Nada fica a meio (transação) | Nada fica a meio, e nada confirmado se perde |
| Dois nós em baixo | — | Nenhuma escrita é confirmada (`503`). Se sobra o primário, as leituras continuam; se sobra uma réplica, só diretamente a ela |
| Rede partida em dois | — | Só o lado com maioria confirma; o antigo primário despromove-se ao ver um `epoch` maior |
| Um nó volta depois de muito tempo | — | Põe-se em dia pelo log, em lotes (não há *snapshots*) |

O que ainda falta resolver está no fim do [README](README.md#o-que-funciona-e-o-que-falta).
