# Projeto final — o que mudou e o que falta

Data: 22 de novembro de 2026; a integração da versão do Jefferson, 23 de
novembro. Estado do trabalho: **no GitHub (`c3f1cb9`, com *force-push*) e
implantado na AWS a 23 de novembro** (secção 10). Falta repetir as provas na
AWS.

## Ponto de partida

A revisão da pasta `projeto-final/` (o *scaffolding* em espanhol dos commits de
14 a 21 de setembro) encontrou onze problemas:

| # | Problema |
|---|---|
| 1 | Senhas do Postgres e `SECRET_KEY` reais no histórico do git (limpas em `GUIA-DESPLIEGUE.md`, mas ainda nos commits antigos) |
| 2 | Duplo gasto: o saldo lia-se sem `FOR UPDATE` e gravava-se em valor absoluto; dois levantamentos concorrentes passavam os dois |
| 3 | Idempotência partida: dois pedidos simultâneos com o mesmo `X-Op-Id` aplicavam-se os dois |
| 4 | Não havia réplica: `cluster/nodo.py` dizia-se sempre primário e dava tudo por confirmado; as bases divergiam ao cair um nó |
| 5 | O frontend guardava o token mas não o enviava: depois do login, tudo dava 401 |
| 6 | O CI/CD estava em `projeto-final/.github/`, onde o GitHub não o lê; nunca correu |
| 7 | `/interno/*`, `/docs` e `/auditoria` expostos através do balanceador; porta 8001 aberta à Internet |
| 8 | `POST /cuentas` sem sessão e com `usuario_id` livre: criavam-se contas em nome de outros |
| 9 | Erros mal traduzidos: `ValueError` → 404, email duplicado → 500, mensagens internas devolvidas ao cliente |
| 10 | Balanceador com `httpx` síncrono dentro de `async def`, que bloqueava o laço de eventos |
| 11 | `vercel.json` com a URL do Lambda fixa; texto solto na guia de implantação |

## O que se fez

### 1. Histórico do git sem os segredos

- Cópia de segurança completa antes de tocar em nada (`git bundle --all`).
- `git filter-repo --replace-text` trocou as duas senhas do Postgres e a
  `SECRET_KEY` por `***REMOVED***` em todos os commits. Verificado com
  `git log --all -S '<segredo>'`, que agora não encontra nenhum commit, e com
  um `grep` à árvore de trabalho.
- Os hashes de todos os commits a partir de `04f20a2` mudaram. Os documentos que os
  citam foram atualizados: `README.md` da raiz, `prototipo-1/README.md`,
  `prototipo-2/docs/PROPOSTA-ARQUITETURA-AWS.md` e a cópia em `projeto-final/docs/`.

| Antes | Agora |
|---|---|
| `d8e1754` | `dababcc` |
| `eab7c4a` | `be54f62` |
| `13fd95b` | `b653cb0` |
| `18debfd` | `d78719d` |

### 2. Port do Protótipo 2 para esta pasta

O conteúdo antigo de `projeto-final/` foi substituído pelos ficheiros versionados
de `prototipo-2/`. O Protótipo 2 já resolvia os problemas 2, 3, 4, 5, 8, 9 e 10, e
já trazia em português os documentos da etapa final:

- cluster real: log replicado, confirmação pela maioria, eleição com `epoch`,
  failover e reintegração;
- `SELECT … FOR UPDATE` e deduplicação por `op_id`, com testes de concorrência;
- autenticação, dono da conta, moedas, câmbio, poupança, prazo fixo,
  transferência externa;
- painel React completo (contas, transferências, auditoria, cluster);
- balanceador com `run_in_threadpool` e Mangum para o Lambda;
- `docs/GUIA-IMPLANTACAO.md`, `PROPOSTA-ARQUITETURA-AWS.md`,
  `INVENTARIO-INSTANCIAS.md`, `GUIA-REPLICA-POSTGRESQL.md` e diagramas.

Não se copiaram o `RELATORIO.md`, o `MUDANCAS-DESDE-PROTOTIPO-1.md` nem as provas
guardadas do Protótipo 2 (são dessa etapa; o README liga-os). Os rótulos
«Protótipo 2» do painel, da API e dos scripts passaram a «projeto final».

### 3. O que se acrescentou para a AWS

| Mudança | Ficheiros | Porquê |
|---|---|---|
| Chave do cluster, derivada da `SECRET_KEY`, exigida em `/interno/replicar`, `/interno/votar` e `/interno/log` (cabeçalho `X-Chave-Cluster`) | `backend/banco/autenticacao/chaves.py`, `api/seguranca.py`, `api/rotas_internas.py`, `cluster/cliente_interno.py` | Com a porta 8001 aberta, uma replicação forjada com `epoch` alto era aceite: podia criar dinheiro |
| `POST /admin/falha` só com `FALHAS_ATIVAS=1` | `api/rotas_internas.py`, `compose.yaml` | Na AWS, `{"tipo": "derrubar"}` matava um nó a pedido de qualquer um |
| `POST /admin/taxas` exige `X-Chave-Admin` (`CHAVE_ADMIN`) | `api/rotas_admin.py`, `compose.yaml`, `provas/scripts/operacoes_api.py` | Com qualquer sessão, uma taxa absurda seguida de um câmbio criava dinheiro |
| Erros novos `nao_e_par_do_cluster`, `sem_chave_de_admin`, `falhas_desativadas` (403) | `servico/erros.py` | A mesma forma `{"erro", "mensagem"}` do resto da API |
| A guia dá a cada backend o `cluster.json` com os IPs privados dos três, `CLUSTER_CONFIG`, `CHAVE_ADMIN` e caminhos de `projeto-final/` | `docs/GUIA-IMPLANTACAO.md` | Sem o `cluster.json`, cada nó arrancava sozinho e não replicava |
| CI/CD na raiz do repositório | `/.github/workflows/projeto-final.yml` (o `docs/ci-cd.yml` foi apagado) | Problema 6 |

No CI:

- testes do backend contra um Postgres de serviço (incluído o do cluster),
  testes do balanceador e `npm run build`, também nos *pull requests*;
- o nome da imagem passa a minúsculas (`PauloRPinedo` partia a etiqueta do Docker);
- a implantação só corre com `IMPLANTACAO_ATIVA=true`, nó a nó, e com os
  mesmos nomes da guia (`backend-X`, `/etc/banco/backend-X.env`).

Testes novos: `tests/unitarios/teste_chaves.py`,
`tests/integracao/teste_rotas_protegidas.py` e um caso em
`tests/integracao/teste_produtos.py` (taxa sem chave de operador → 403, e a
taxa em vigor não muda).

### 4. Documentação

- `README.md`: novo cabeçalho da etapa, variáveis `CHAVE_ADMIN` e
  `FALHAS_ATIVAS`, tabela da API com as proteções, contagem de testes, e as
  listas «funciona» e «falta» reescritas.
- `docs/PROPOSTA-ARQUITETURA-AWS.md`: nota de estado com as lacunas G1–G11
  feitas e por fazer.
- `README.md` da raiz: a etapa final aparece na tabela das três etapas.

### 5. Integração da versão do Jefferson (23 de novembro)

(Ver também a secção 6, sobre o balanceador numa partição.)

O Jefferson tinha feito, no seu fork, outra versão desta pasta: em espanhol,
sobre o *scaffolding* antigo, com um protocolo próprio. Entrou no `main` do
GitHub pelo PR #3 (`b12b436`). As duas versões não partilham código, por isso
não se fundiram: compararam-se, e da dele trouxe-se o que era melhor,
traduzido para português e arrumado na estrutura desta.

**O que se trouxe**

| Da versão dele | Aqui | Notas |
|---|---|---|
| Painel de aplicação bancária: início com saldo e atalhos, menu, um ecrã por operação, registo com termos, cartões de conta, olho para esconder saldos | `frontend/src/paginas/`, `paginas/acoes/`, `componentes/`, `lib/` | Por cima do `api/cliente.js` daqui, que guarda um `op_id` por intenção: na versão dele um duplo clique eram dois depósitos |
| Logótipo, favicon, ícones | `frontend/public/` | |
| (novo, não estava na dele) Página responsiva em vez da moldura de telefone | `componentes/Ecra.jsx`, `estilo.css`, `lib/useEcraLargo.js` | A mesma cor, letra e logótipo; ocupa sempre a janela; grelhas no tablet; barra lateral de 1024px para cima ([`docs/LINHA-GRAFICA.md`](LINHA-GRAFICA.md)) |
| Rotas no navegador (React Router) e *rewrite* SPA | `App.jsx`, `vercel.json`, `nginx.conf` | Recarregar em `/transferir` já não dá 404 |
| Número de conta: agência `0001`, 8 dígitos, dígito verificador módulo 11 | `backend/banco/dominio/numero_conta.py`, `CriarConta.numero`, coluna `conta.numero` | Na dele, cada nó calculava o número a partir do id; aqui o primário sorteia-o e ele viaja na entrada do log |
| Procurar uma conta pelo número e transferir para ela | `GET /contas/por-numero/{numero}`; `para` aceita o número | Devolve só o nome do titular e a moeda |
| Guias de teste e de reconstrução | `docs/GUIA-TESTES-RF-RNF.md`, `docs/GUIA-TESTE-SERVIDORES.md`, `docs/GUIA-RECONSTRUIR-EC2.md`, `docs/LINHA-GRAFICA.md` | Reescritas para esta API e para três nós, não só traduzidas |

**O que não se trouxe, e porquê**

| Da versão dele | Porquê |
|---|---|
| Protocolo de arrendamento a dois nós (`PARES`, `ROL`, `en_solitario`) | Num corte de rede entre os dois, os dois aceitam escritas; a guia dele admite que «as filas do perdedor não se desfazem». Aqui, sem maioria, não se escreve, e para ter failover levanta-se o 3.º nó |
| Réplicas que aplicam a entrada ao recebê-la | Aplicavam antes de haver maioria; sem verificação do log nem truncagem, um log divergente nunca se corrigia |
| `/interno/latido`, `/interno/replicar`, `/interno/votar` sem chave | `replicar` fazia `UPDATE cuenta SET saldo = X`: qualquer pessoa com acesso à porta 8001 fixava saldos |
| Validação do saldo fora do lock de escrita, saldo absoluto no log | Dois saques ao mesmo tempo validavam contra o mesmo saldo: gasto duplo |
| `POST /auth/recuperar` | Quem soubesse um email trocava a senha dessa pessoa, sem verificação nenhuma. Sem servidor de email não há recuperação segura; o painel diz isso nos termos |
| Seletor espanhol / português | O grupo decidiu: o projeto final é todo em português |
| *Service worker* (PWA com cache) | Num banco, um saldo velho no ecrã é pior do que não abrir. Ficou o manifesto (instalar no telefone), sem cache |
| Inter do Google Fonts | Ficou a Instrument Sans auto-alojada: o painel não depende de um CDN |

**O que se corrigiu pelo caminho.** Com transferências pelo número para
desconhecidos, a resposta deixava ver o saldo do destinatário; o depósito
(aberto, sem sessão) também devolvia o saldo da conta. Agora:

- a resposta de uma transferência só traz o saldo das contas de quem pede;
- a de um depósito só traz o saldo ao dono da conta.

Testes novos: `tests/unitarios/teste_numero_conta.py`,
`tests/integracao/teste_numero_conta.py`, três casos em `teste_acesso.py`; a
impressão digital do `teste_cluster.py` passou a incluir o número de cada conta,
o que prova que é igual nos três nós.

### 6. Balanceador numa partição e guia de tolerância a falhas (23 de novembro)

Ao ensaiar a partição para a guia, apareceu uma falha no balanceador. Com o
primário isolado dos outros dois nós, mas ainda ao alcance do balanceador:

- os outros dois elegiam um primário novo, de `epoch` maior;
- o balanceador continuava a mandar tudo ao antigo, porque o tinha em cache e
  ele ainda se dizia primário;
- todas as escritas davam `503 somente_leitura` até a rede voltar.

Agora, em `balanceador/balanceador/encaminhador.py`:

- entre vários nós que se dizem primários, escolhe o de `epoch` maior;
- a um `503 somente_leitura` ou `sem_quorum`, volta a procurar e, se houver
  outro primário, repete lá com o mesmo `op_id`. Senão, devolve o 503.

Três testes novos em `balanceador/tests/teste_encaminhador.py` (de 5 para 8).
Contra o `docker compose`, a mesma partição passou a dar `200` pelo balanceador.

A guia nova é [`GUIA-TOLERANCIA-A-FALHAS.md`](GUIA-TOLERANCIA-A-FALHAS.md):
ajudas de consola (`estado`, `vigiar`, `rajada`, `falha`, `failover`), os testes
num só portátil e a montagem em dois ou três portáteis na mesma rede, com
`docker run` e um `config/cluster.lan.json`. Os testes e a montagem em rede
foram ensaiados, a montagem com os três nós no mesmo portátil a falarem pelo IP
da rede local; com portáteis diferentes não se ensaiou.

### 7. Menos guias (23 de novembro)

Saíram duas guias que repetiam o que já estava noutros sítios:

| Guia retirada | Para onde foi o que só ela tinha |
|---|---|
| `GUIA-REPLICA-POSTGRESQL.md` | O porquê já estava na `PROPOSTA-ARQUITETURA-AWS.md` (2.4) e no `README.md` («Como funciona»). A nota sobre cópias de segurança e a configuração de réplica que não se faz passaram ao Passo 2 da `GUIA-IMPLANTACAO.md` |
| `GUIA-TESTE-SERVIDORES.md` | As verificações na AWS (nós, Lambda, painel, bases, queda) são agora o Passo 6 da `GUIA-IMPLANTACAO.md`. A comparação das bases usa a impressão digital da `GUIA-TOLERANCIA-A-FALHAS.md` |

As menções a estas guias nas secções 2 e 5 são o registo do que se fez na
altura.

### 8. Os pendentes que não dependiam da AWS (23 de novembro)

**Transferência externa a meio.** O débito e o desfecho são duas escritas no
log; se o primário cai entre as duas, o dinheiro sai da conta e o desfecho
fica por gravar. Agora termina-se de duas formas, ambas com o mesmo código
(`backend/banco/api/externas.py`): o cliente repete com o mesmo `op_id`, ou o
primário reconcilia sozinho, a cada `BANCO_RECONCILIAR_S` segundos (30 por
omissão), os débitos sem desfecho com mais de 30 s. Também há
`POST /admin/externas/reconciliar`. Voltar a perguntar ao outro banco é seguro
porque ele deduplica pelo `op_id` (o simulado decide de forma determinística
por `op_id`). Se o outro banco não responde, a API dá
`503 outro_banco_indisponivel`, a dizer que o débito ficou feito.
Provado ao vivo: matar o primário 150 ms depois de pedir uma externa deu
`503 sem_primario` com o débito já gravado; o novo primário registou
`reconciliação: 1 concluídas` sozinho, e repetir o pedido devolveu
`confirmada` sem debitar outra vez (saldo 70,00 de 100,00, auditoria sem
divergência).

**`/auditoria` pede sessão.** Sem token dá `401`; o painel, os scripts de
provas e a guia de tolerância a falhas já a pediam com sessão.

**Só uma réplica viva.** O balanceador, sem primário, manda as leituras ao nó
vivo com mais log aplicado e marca a resposta com `X-Leitura-De-Replica`. O
painel mostra então um aviso: «O banco está sem primário. Estes dados vêm do
nó B e podem estar atrasados…». As escritas continuam a dar `503`. Provado ao
vivo com dois nós mortos, incluindo o aviso num Chromium.

**Primário «pronto».** Um nó que acaba de ganhar uma eleição só é primário
pronto depois de confirmar e aplicar a `noop` do seu mandato, e com ela tudo
o que o primário anterior confirmou. `/interno/estado` diz `pronto`, e o
balanceador só encaminha para um primário pronto. Antes, havia uma janela em
que uma leitura ao novo primário podia não ver uma escrita já confirmada a um
cliente.

**O `teste_cluster.py` intermitente.** Correu-se em ciclo, com a saída de cada
execução guardada. Eram dois problemas:

1. *Do teste.* Logo a seguir a um failover, uma escrita única apanhava a
   eleição a meio (`409 nao_sou_primario`, `503 somente_leitura`). Uma escrita
   de um cliente nesse momento falha e repete-se; o teste não repetia. Agora
   repete durante até 10 s nesses erros, e só nesses, voltando a procurar o
   primário. Nenhuma das falhas tinha dinheiro errado.
2. *Do sistema.* Se a primeira ronda da `noop` de um novo primário não tinha
   maioria (uma réplica ainda a arrancar), o primário ficava não pronto até à
   próxima escrita de um cliente, e o balanceador não lhe mandava nenhuma:
   ficava parado. Agora, depois de cada heartbeat, um primário não pronto
   volta a tentar confirmar a `noop`. Há um teste unitário que falha sem isto.

Depois: 40 de 40 execuções seguidas com a máquina parada (antes, 27 de 30).
Fica por explicar uma falha, numa série anterior de 30: uma réplica não
aplicou uma transferência durante 5 s. Os testes do cluster passaram a
guardar, quando falham, o estado e o registo de cada nó, para a próxima vez.
Com metade dos núcleos ocupados por outros processos, o teste ainda falha
às vezes com erros de disponibilidade: usa timeouts de eleição de
150–300 ms, que uma máquina carregada não garante.

**RNF-04 e RNF-05, medidos.** `provas/scripts/medir_desempenho.py` mede
escritas (depósitos) e leituras (saldo) com 1 a 32 clientes, pelo
balanceador e direto ao primário
([`provas/desempenho/medicao.md`](../provas/desempenho/medicao.md)). No
portátil, com tudo no `docker compose` e um navegador aberto:

| | Melhor débito | p99 com 1 cliente | Meta |
|---|---:|---:|---|
| Escritas, direto ao primário | 10/s | 161 ms | 500/s, p99 < 200 ms |
| Escritas, pelo balanceador | 9/s | 260 ms | |
| Leituras, direto ao primário | 140/s | 34 ms | |
| Leituras, pelo balanceador | 47/s | 109 ms | |

As escritas não passam de ~10 por segundo com 1 ou com 32 clientes: vão uma
de cada vez (cada uma segura o lock de escrita durante a sua ronda de
replicação) e a ronda espera pelas duas réplicas, não só pela primeira. Com
mais clientes só cresce a fila, e a latência com ela. O balanceador acrescenta
~40 ms a cada pedido porque pergunta ao primário se ainda o é antes de lho
enviar. As duas correções fizeram-se a seguir (secção 9).

### 9. Os dois gargalos do desempenho (23 de novembro)

Medido antes de mudar, com o tempo de cada fase no primário (instrumentação
temporária, já retirada) e um *profiler*. Uma escrita esperava ~310 ms com 32
clientes: a ronda de replicação demorava ~113 ms porque a réplica aplicava o
lote anterior antes de responder; aplicar no primário custava ~5,7 ms por
entrada, cada uma na sua transação; e abrir uma ligação à base custava
11,6 ms, quatro ou cinco vezes por escrita. Mudou:

| Onde | O quê |
|---|---|
| `cluster/no.py` | Escritas em grupo: cada escrita reserva as chaves que toca (contas, número da conta nova, email, `op_id`) e valida fora do lock; só gravar no log é um de cada vez. As que chegam juntas vão na mesma ronda e aplicam-se numa transação. As réplicas respondem ao gravar e aplicam noutra thread |
| `cluster/replicacao.py` | A ronda acaba quando a **primeira** réplica confirma. Um canal por réplica, com a mensagem montada à saída (leva tudo o que falta; sem fila a crescer com uma réplica em baixo) e o ponto até onde cada réplica confirmou (o `matchIndex` do Raft) |
| `cluster/log_de_replicacao.py` | Uma réplica só apaga a partir da primeira entrada **diferente**: uma mensagem antiga e mais curta, chegada tarde, já não apaga entradas confirmadas ao líder |
| `cluster/cliente_interno.py` | Ligações HTTP entre nós mantidas abertas |
| `repositorio/conexao.py` | *Pool* de ligações: `close()` desfaz o que ficou por confirmar e devolve a ligação |
| `servico/aplicador.py` | `aplicar_lote`: um lote numa transação, com um *savepoint* por entrada |
| `api/app.py` e o balanceador | Cada resposta de um nó diz `X-Primario-Pronto`; o balanceador confia no primário em cache e só volta a procurar quando uma resposta diz `nao`, um pedido falha ou recebe 409/503. Um `httpx.Client` partilhado |

Resultado, na mesma máquina ([`provas/desempenho/medicao.md`](../provas/desempenho/medicao.md)):

| | Antes | Depois |
|---|---:|---:|
| Escritas, pelo balanceador, 32 clientes | 2/s (66 erros) | **87/s** (0 erros) |
| Escritas, direto ao primário, melhor | 10/s | **110/s** |
| Escritas, p99 com 1 cliente | 260 ms | **50 ms** |
| Leituras, pelo balanceador, melhor | 47/s | **208/s** |
| Leituras, p99 com 1 cliente, pelo balanceador | 109 ms | **19 ms** |

RNF-05 (p99 < 200 ms) cumpre-se até 8 clientes; RNF-04 (500/s) continua
longe. O limite agora é outro: o processo Python do primário gasta ~10–14 ms
de CPU por escrita (medido com um só cliente, 14 ms; com 32, 9 ms), e com o
GIL só usa um núcleo. Passar disso pede menos idas à base por escrita ou
separar a API HTTP do nó em vários processos.

Testes novos: escritas de contas diferentes partilham rondas; duas escritas da
mesma conta não validam contra o mesmo saldo (falha com o bloqueio por chaves
desligado); o mesmo `op_id` em paralelo aplica-se uma vez; a regra de
truncar da réplica; o *pool* devolve as ligações limpas; o balanceador não
pergunta antes de cada pedido e segue um primário que deixou de o ser. O
`teste_cluster.py` passou 30 de 30 seguidas depois disto.

### 10. Implantação na AWS (23 de novembro)

Feita pelo Jefferson, a partir do `c3f1cb9`, seguindo a
[`GUIA-RECONSTRUIR-EC2.md`](GUIA-RECONSTRUIR-EC2.md).

**Onde está cada coisa.** O cluster está em duas contas AWS (`us-east-2`),
unidas por *VPC peering*, porque a conta antiga não tinha quota de vCPU para o
nó C:

| Nó | Conta | Rede |
|---|---|---|
| A (`backend-a`, `postgres-a`) e o Lambda | antiga | VPC por omissão, `172.31.0.0/16` |
| B e C (`backend-X`, `postgres-X`) | nova | VPC própria, `10.1.0.0/16` (não a de omissão, que se sobrepunha à outra e o *peering* não o aceita) |

Os três nós alcançam-se por IP privado na porta 8001, através do *peering*.

**O que se fez**

| Passo | Como ficou |
|---|---|
| Bases | Os três `postgres-X` recriados com o `esquema.sql` desta versão (sem migração; os dados de teste perderam-se). `\dt` lista as 7 tabelas nas três |
| Backends | Imagem construída a partir do clone do repositório em cada instância. `/etc/banco/cluster.json` com os IPs **privados** dos três nós. As variáveis comuns (`PG*`, `SECRET_KEY`, `CHAVE_ADMIN`, `CLUSTER_CONFIG`, `PORTA`) estão num único `/etc/banco/backend.env`, igual nos três; `NO_ID` e `PGHOST` passam-se no `docker run` com `-e`. Sem `FALHAS_ATIVAS` |
| Eleição | Um só primário (A), B e C réplicas, o mesmo `epoch` e o mesmo `lider` nos três, índices do log iguais, `pronto: true` |
| Lambda | Imagem nova no ECR e *Deploy new image* na função. O CloudShell estava bloqueado («verificação da conta em curso»), por isso a imagem construiu-se em `backend-a`, com o papel IAM temporário `backend-ecr-temporal`. `CLUSTER_CONFIG_JSON` com os IPs **privados**: o Lambda já estava ligado à VPC |
| Vercel | Sem mudanças: a Function URL é a mesma, e o `vercel.json` já apontava para ela |
| Porta 8001 | Sem `0.0.0.0/0`. Só a abrem a outra VPC (pelo *peering*), o próprio *security group* dos backends e o do Lambda |

**Verificado:** `/interno/estado` em cada nó; `<Function URL>/saude` →
`{"balanceador":"ativo"}`; `<Function URL>/interno/estado` e
`https://<site>.vercel.app/api/interno/estado` → o estado do primário.

**Diferença em relação à guia:** o CI espera um `/etc/banco/backend-X.env` por
nó, com `NO_ID` e `PGHOST` dentro (`projeto-final.yml`, que não passa `-e`). Na
AWS há um só `backend.env` sem essas duas. Para a implantação manual não
importa; para ligar a do CI é preciso criar os três ficheiros por nó (cópia do
comum mais `NO_ID` e `PGHOST`).

## Verificação

| O quê | Resultado |
|---|---|
| Backend, com um Postgres descartável | **306 testes OK**, incluídos os 7 com três processos e `kill -9` do primário |
| Backend sem base / sem dependências | 203 / 193 correm, os outros saltam-se com o motivo |
| Balanceador | 15 OK |
| Painel | `npm run build` OK; percurso num Chromium a 390 × 844 contra o `docker compose`: registo, abrir conta, depositar, transferir pelo número (com o titular), extrato, auditoria, cluster, recarregar numa rota interna. Depois, a página responsiva a 360, 390, 600, 820, 1024, 1180, 1440 e 1920px: entrar, início com três contas, transferir, extrato, auditoria, cluster e abrir conta, sem deslocamento horizontal em nenhuma. Sem erros na consola |
| `docker compose up` + `provas/scripts/operacoes_api.py` | **65 de 65 passos**, com volumes novos; C assumiu **1,30 s** depois do `kill` do primário; impressão digital igual nas três bases ([`provas/api/sessao.md`](../provas/api/sessao.md)) |
| Ao vivo, pelo balanceador | replicação forjada → 403; `/interno/log` sem chave → 403; taxa sem chave de operador → 403 |
| `teste_cluster.py` em ciclo | 40 de 40 com a máquina parada (secção 8) |
| RNF-04/05 | 87 escritas/s pelo balanceador (eram ~10); p99 < 200 ms até 8 clientes (secção 9) |
| `teste_cluster.py` depois da secção 9 | 30 de 30 |
| Segredos | 0 commits e 0 ficheiros os contêm |
| `prototipo-2/` | os seus testes continuam a passar (o único ficheiro mudado foi a proposta, com os hashes novos) |

## Revisão: estado de cada problema

| # | Problema | Estado |
|---|---|---|
| 1 | Segredos no histórico | **Resolvido no `main` do GitHub** (*force-push*). Continuam em `refs/pull/1` e `refs/pull/2` e não se rodam, por decisão (ver «O que falta») |
| 2 | Duplo gasto | Resolvido |
| 3 | Idempotência | Resolvido |
| 4 | Sem réplica | Resolvido, também na AWS (secção 10) |
| 5 | Frontend sem token | Resolvido |
| 6 | CI que não corria | Resolvido; correu no push de `c3f1cb9` (testes e build). A implantação pelo CI continua desligada |
| 7 | Rotas expostas | Resolvido no código e na AWS: a 8001 já não está aberta à Internet (secção 10) |
| 8 | Contas em nome de outros | Resolvido |
| 9 | Erros mal traduzidos | Resolvido |
| 10 | Balanceador bloqueante | Resolvido |
| 11 | `vercel.json` e guia | Texto solto da guia resolvido; a URL fixa do Lambda continua |

## O que falta

### Urgente

- **Rodar as senhas do Postgres e a `SECRET_KEY`: não se faz, por decisão** (é
  um projeto de teste). Na reimplantação de 23 de novembro mantiveram-se as que
  já estavam na AWS (só a `CHAVE_ADMIN` é nova), e podem ser as que estiveram
  no histórico: essas continuam para sempre em `refs/pull/1` e `refs/pull/2`,
  que um *force-push* não apaga.
- [x] **Commit e *force-push*** do histórico reescrito (`c3f1cb9`). O fork do
      Jefferson foi alinhado com `git reset --hard upstream/main` e *force-push*.
      A versão anterior dele ficou na rama `respaldo-jefferson` desse fork, com o
      histórico antigo: apagá-la se tiver os segredos.

### Implantação na AWS

- [x] Implantar este código nas instâncias, com as bases recriadas (secção 10).
- [x] Confirmar o nó C. A em `172.31.x` e B/C em `10.1.x` são VPCs de contas
      diferentes, unidas por *VPC peering*; os três alcançam-se por IP privado e
      elegem um só primário.
- [x] Criar `/etc/banco/cluster.json` e as variáveis de cada backend. Ficaram num
      `backend.env` comum, e não em `backend-X.env` (ver secção 10 para o CI).
- [x] Voltar a implantar o Lambda. A URL não mudou, por isso o
      `frontend/vercel.json` não precisou de mudança.
- [x] Lambda na VPC e porta 8001 fechada à Internet. O Lambda já estava ligado à
      VPC e chega aos nós por IP **privado**, que não muda ao parar uma instância.
- [ ] Repetir as provas na AWS: o percurso no painel, failover com *Stop
      instance* do primário, total de dinheiro e impressão digital das três
      bases.
- [ ] Implantação pelo CI (opcional; a manual chega para a entrega). Antes de
      ligar `IMPLANTACAO_ATIVA`:
      - os segredos `SSH_HOST_A/B/C`, `SSH_USER`, `SSH_KEY` e as variáveis
        `AWS_ROLE_ARN`, `AWS_REGION`, `ECR_REGISTRY` vão no repositório do
        grupo, e só quem é admin os pode pôr;
      - criar `/etc/banco/backend-X.env` por nó (secção 10);
      - a porta 22 dos backends só aceita o IP de quem administra e o EC2
        Instance Connect; o SSH a partir do GitHub Actions não entra sem a abrir;
      - o cluster está em duas contas: o job do Lambda só conhece uma
        (`AWS_ROLE_ARN`, `ECR_REGISTRY`), o que basta, porque o Lambda e o ECR
        estão os dois na conta antiga;
      - confirmar no primeiro *run* que `secrets[format('SSH_HOST_{0}', matrix.no)]`
        resolve com o nó em minúsculas (não foi testado).

### Limitações conhecidas do sistema

- [x] `/auditoria` pede sessão (secção 8). `/interno/estado` e
      `/interno/cluster` continuam públicos: o balanceador e o painel precisam
      deles antes de haver sessão, e não mostram contas.
- [x] Se o único nó que sobra é uma réplica, as leituras continuam, marcadas
      com `X-Leitura-De-Replica`, e o painel avisa (secção 8). As escritas
      continuam a dar `503 sem_primario`, como devem.
- [x] Uma transferência externa que caia entre o débito e o desfecho termina
      sozinha: o primário reconcilia a cada 30 s (secção 8).
- [x] O `teste_cluster.py` intermitente: eram dois problemas, um dos testes e
      um do sistema, ambos corrigidos (secção 8).
- [ ] **RNF-04 não se cumpre**: 87 escritas por segundo pelo balanceador
      (meta 500). RNF-05 cumpre-se até 8 clientes. O limite é a CPU do
      processo Python do primário (secção 9).
- [ ] Não há papéis de utilizador, de propósito: a chave de operador é um
      segredo partilhado, não uma pessoa; o *tick* de juros e a reconciliação
      correm com qualquer sessão (são idempotentes e só fazem o que já é devido).
- [ ] Sem *snapshots*, de propósito: um nó que esteve muito tempo em baixo
      recebe o log aos lotes. Com o volume de uma demonstração são segundos.

## Ficheiros mudados fora de `projeto-final/`

| Ficheiro | Mudança |
|---|---|
| `.github/workflows/projeto-final.yml` | Novo: o CI/CD |
| `README.md` | Linha da etapa final na tabela; hashes novos |
| `prototipo-1/README.md` | Um hash novo |
| `prototipo-2/docs/PROPOSTA-ARQUITETURA-AWS.md` | Hashes novos |
