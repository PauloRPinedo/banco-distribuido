# Provas do Protótipo 2 — 5 de outubro de 2026

O Protótipo 2 posto a correr de raiz e exercitado de três maneiras: as suites de
testes, uma sessão de operações pela API com a queda do primário a meio, e o
painel num navegador com um failover ao vivo. Tudo o que aqui está foi gerado
por comandos que se podem repetir (no fim).

## Resultado, numa tabela

| Prova | Resultado | Ficheiro |
|---|---|---|
| Testes sem dependências (só Python 3.13) | **165 passam** — domínio e protocolo com três nós em memória; 86 saltam-se com o motivo escrito | [`testes/1-sem-dependencias.txt`](testes/1-sem-dependencias.txt) |
| Testes do backend com a pilha e um PostgreSQL 16 | **251 passam**, incluindo três processos, três bases e `kill -9` do primário | [`testes/2-backend-com-postgres.txt`](testes/2-backend-com-postgres.txt) |
| Testes do balanceador | **5 passam** | [`testes/3-balanceador.txt`](testes/3-balanceador.txt) |
| Build do painel | compila | [`testes/4-frontend-build.txt`](testes/4-frontend-build.txt) |
| `docker compose up --build --wait` | 8 contentores *healthy*; 3 s depois, C primário no epoch 2, A e B réplicas que o seguem | [`testes/5-compose-arranque.txt`](testes/5-compose-arranque.txt) |
| Sessão de operações pela API | **65 passos certos, 0 falhados** | [`api/sessao.md`](api/sessao.md) |
| Painel num Chromium sem janela | **21 capturas**, com um failover ao vivo, sem erros de JavaScript | [`capturas/`](capturas/) |
| Registos dos contentores durante as provas | nenhum 500, nenhuma exceção | [`testes/6-registos-dos-contentores.txt`](testes/6-registos-dos-contentores.txt) |

## A queda do primário

A secção 12 de [`api/sessao.md`](api/sessao.md) é a prova central do projeto:

1. **Antes:** as três bases têm a mesma impressão digital (contagens e `md5` das
   contas e das operações) — cada escrita das secções 1 a 11 foi confirmada pela
   maioria e aplicada nos três nós.
2. Três clientes transferem 0,01 da Ana para o Rui sem parar; cada um repete o
   mesmo `op_id` até alguém confirmar, como um cliente real.
3. `docker compose kill no-b` — o primário morre a meio, sem fechar nada.
4. **O nó C passou a primário 1,23 s depois** (RNF-03 pede menos de 2 s), com um
   `epoch` maior. Durante a transição, 15 tentativas receberam 503 e foram
   repetidas com o mesmo `op_id`; 27 transferências foram confirmadas.
5. Depois da queda: a sessão da Ana continua válida no novo primário; cada
   transferência confirmada está lá; a transferência do início, repetida,
   devolve o mesmo corpo; o novo primário aceita escritas; **o dinheiro total
   não mudou**.
6. `docker compose start no-b` — B volta **como réplica**, segue C, e põe-se em dia.
7. **As três bases voltam a ter a mesma impressão digital**, incluindo tudo o
   que aconteceu enquanto B estava morto:

| Nó | Base de dados do nó |
|---|---|
| A | 3 utilizadores · 11 contas · 86 operações · log até 93 · md5 59dd4ef431cd |
| B | 3 utilizadores · 11 contas · 86 operações · log até 93 · md5 59dd4ef431cd |
| C | 3 utilizadores · 11 contas · 86 operações · log até 93 · md5 59dd4ef431cd |

## O resto da sessão

| Secção | O que se verificou |
|---|---|
| 1. Cluster de pé | Os três nós respondem; há exatamente um primário e todos concordam sobre quem é |
| 2. Registo e sessão | Email repetido 409, senha errada 401, sem sessão 401 |
| 3. Abrir contas | Corrente em BRL, conta em USD, poupança a 10 %, prazo fixo de 30 dias; cada utilizador vê só as suas |
| 4. Pedidos mal formados | Dinheiro como número, três casas decimais, id inválido, conta repetida, moeda desconhecida, corrente com taxa, `op_id` curto — todos recusados |
| 5. Movimentos | Depósito, saque, saque sem saldo (422), saque de prazo fixo (409), transferência; **a mesma transferência repetida devolve o mesmo corpo** |
| 6. Dono da conta | Outro utilizador não consulta, não saca, não transfere, e não lê a resposta de um `op_id` alheio (403) |
| 7. Moedas e câmbio | Transferência entre moedas recusada; câmbio a 5,43; taxa nova a 6,00 (registada pelo log); **o câmbio repetido mantém a taxa de então** |
| 8. Outro banco | Um envio confirmado e um rejeitado (devolvido); repetir devolve o desfecho gravado |
| 9. Juros | O *tick* corre |
| 10. Concorrência | **20 depósitos simultâneos: nenhum se perde. 20 saques de 1,00 sobre 10,00: 10 aceites, 10 recusados** |
| 11. Extrato e auditoria | Cada moeda bate |

## As capturas

| # | Ecrã |
|---|---|
| 01–04 | Login, login recusado, registo, painel vazio depois de entrar |
| 05–07 | Conta corrente, depósito com extrato, saque sem saldo (a conta continua à vista) |
| 08–10 | Conta em dólares, poupança, prazo fixo com saque bloqueado |
| 11–14 | Transferência, transferência entre moedas recusada, câmbio, transferência para outro banco |
| 15 | Auditoria por moeda |
| **16** | **Cluster: três nós de pé, um primário, todos com o mesmo índice confirmado** |
| **17** | **Depois de `docker compose kill` do primário: o morto aparece "em baixo", outro nó é primário com `epoch` maior** |
| **18** | **A conta, servida pelo novo primário, com um depósito confirmado depois da queda** |
| **19** | **O nó morto de volta como réplica, com os mesmos índices dos outros** |
| 20 | O painel num telemóvel (390 px) |
| 21 | Depois de sair |

O selo no canto diz que nó é primário e em que `epoch`; nas capturas 17 a 19 já
é outro.

## O que estas provas não cobrem

- Uma **partição de rede** (nós vivos mas sem se falarem) prova-se no teste
  `TesteParticao` de `tests/unitarios/teste_no.py`, com o injetor de falhas, e
  não aqui: dentro do compose isolar contentores exigiria mexer na rede do Docker.
- Em 19 execuções seguidas de `tests/integracao/teste_cluster.py`, uma falhou e
  não se repetiu nas 16 seguintes; não se sabe qual dos sete testes foi. Está
  registado no README da etapa.
- O débito de escritas não foi medido.

## Erros que estas provas encontraram ao longo do caminho, já corrigidos

| Erro | Como apareceu | Correção |
|---|---|---|
| **O cluster não replicava** (o `cluster/` era um *stub* que confirmava tudo) | Secção 12 da primeira versão destas provas: com o nó A parado, B e C não tinham nenhuma conta | O protocolo da primeira versão da pasta, portado — ver o README da etapa |
| Depois de um saque recusado, o painel escondia a conta | O script das capturas não conseguia escrever o valor seguinte | `frontend/src/paginas/Contas.jsx` |
| Num telemóvel, a tabela do extrato alargava a página | Captura do telemóvel | `frontend/src/estilo.css` |
| `docker compose up --wait` devolvia antes de o balanceador aceitar pedidos | O primeiro login da sessão falhou | *healthcheck* no balanceador |

## Como repetir

```bash
cd prototipo-2

# 1. testes (o README da etapa explica o venv e a base de teste)
(cd backend && python3 -m unittest discover -s tests -v)

# 2. o sistema, de raiz
export SECRET_KEY=$(openssl rand -hex 32)
docker compose down -v
docker compose up --build -d --wait

# 3. as capturas (matam e trazem de volta o primário)
cd provas/scripts
npm install --no-save playwright-core
CHROMIUM=/caminho/para/chrome-headless-shell node capturas_painel.mjs
cd ../..

# 4. a sessão de operações (só a biblioteca padrão do Python)
python3 provas/scripts/operacoes_api.py

docker compose down -v
```

O `playwright-core` instala-se só para as capturas e não entra nas dependências
do projeto. As capturas foram tiradas com o `chrome-headless-shell` que o
Playwright guarda em `~/.cache/ms-playwright/`.

## Ambiente

Debian 13, Python 3.13.5 nos testes e 3.12 nas imagens, Node 20.19.2,
Docker 29.8, Compose 5.6, `postgres:16-alpine`.
