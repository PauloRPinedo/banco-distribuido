# Testar requisito a requisito (RF e RNF)

Para cada requisito: a rota, quem fala com quem e a resposta esperada. Segue a
ideia da guia do Jefferson (`GUIA-PRUEBA-RF-RNF.md`, na versão dele), reescrita
para esta API e para três nós.

**Em local, quase tudo isto já corre sozinho.** Com `docker compose up`,
`python3 provas/scripts/operacoes_api.py` faz os 65 passos (incluída a queda do
primário) e escreve o resultado em [`provas/api/sessao.md`](../provas/api/sessao.md).
Esta guia serve para repetir as provas à mão, na AWS ou numa demonstração.
Os testes de falhas pela consola (num portátil ou em vários) estão em
[`GUIA-TOLERANCIA-A-FALHAS.md`](GUIA-TOLERANCIA-A-FALHAS.md).

## O caminho de um pedido

1. O navegador chama `https://<site>/api/...`. O Vercel reenvia para a Lambda e
   tira o prefixo `/api`.
2. A Lambda (o balanceador) pergunta `GET /interno/estado` aos nós e manda o
   pedido ao primário de `epoch` mais alto.
3. Numa escrita, o primário valida, grava a entrada no seu log, replica-a
   (`POST /interno/replicar`, com a chave do cluster) e espera pela **maioria**
   (2 de 3). Só então a aplica e responde `200`. As réplicas aplicam-na quando
   sabem que está confirmada.
4. As leituras vão também ao primário.

Nos exemplos, `B=<FUNCTION_URL>` (ou `http://localhost:8000` em local) e `T` é o
token do login. Toda a escrita leva um `op_id` no corpo, de 8 a 64 caracteres:
um novo por intenção, e **o mesmo** quando se repete a mesma intenção. O dinheiro
vai sempre em texto (`"25.00"`), nunca como número JSON.

```bash
pedir() { curl -sS -X "$1" "$B$2" -H 'Content-Type: application/json' \
          ${T:+-H "Authorization: Bearer $T"} ${3:+-d "$3"}; echo; }
```

---

## 0. Sessão (RF-26, CU-17)

| Passo | Pedido | Esperado |
|---|---|---|
| Registo | `pedir POST /auth/registo '{"nome":"Ana","email":"ana@ex.pt","senha":"segredo1"}'` | `200`. O utilizador vai pelo log e existe nos três nós |
| Email repetido | o mesmo | `409` `email_duplicado` |
| Entrar | `pedir POST /auth/login '{"email":"ana@ex.pt","senha":"segredo1"}'` | `200` e `token`. Senha errada ou email inexistente: `401` `credenciais_invalidas`, com a mesma mensagem nos dois casos |

O token dura 8 horas e é assinado com a `SECRET_KEY`, igual nos três nós:
qualquer nó o valida sem perguntar a ninguém. Depois de um failover, a sessão
continua a valer. **Não há recuperação de senha:** sem um servidor de email
não há como provar que quem pede é o dono do email.

## RF-01 — Abrir conta

```bash
pedir POST /contas '{"saldo_inicial":"100.00","op_id":"abrir-conta-1"}'
```

`200` com `conta` (o id interno, `conta-12345678-9`), `agencia` `0001`, `numero`
e `saldo`. O primário sorteia o número (8 dígitos e dígito verificador módulo
11), e o número viaja na entrada do log: é o mesmo nas três bases. O dono é o
utilizador do token, nunca um campo do corpo.

Também se pode dar o id (`"conta":"alice"`), e aceitam-se `moeda` (`BRL`, `USD`,
`PEN`) e `produto` (`corrente`, `poupanca` com `taxa_juros`, `prazo_fixo` com
`taxa_juros` e `prazo_dias`). Sem sessão: `401`. Id repetido: `409`
`conta_duplicada`.

## RF-02 — Consultar saldo

`pedir GET /contas/<id>` → `200` com `saldo`, `moeda`, `produto`, `agencia` e
`numero`. Sem sessão: `401`. Conta de outra pessoa: `403` `proibido`. Id que não
existe: `404` `conta_inexistente`.

`pedir GET /contas/por-numero/0001%2012345678-9` → o `titular` (só o nome) e a
`moeda`. Nunca o saldo. É o que o painel mostra para confirmar o destino de uma
transferência. Um número com o dígito verificador errado dá `400`.

## RF-03 — Depositar e sacar

```bash
pedir POST /contas/<id>/deposito '{"valor":"25.50","op_id":"deposito-1"}'
pedir POST /contas/<id>/saque    '{"valor":"10.00","op_id":"saque-1"}'
```

O depósito é aberto: qualquer pessoa deposita em qualquer conta, como num
balcão. Só o dono recebe o saldo na resposta; os outros, e quem deposita sem
sessão, recebem a confirmação sem o saldo. O saque exige sessão e ser o dono.

## RF-06 — O saldo nunca fica negativo

Um saque maior que o saldo dá `422` `saldo_insuficiente`, e o saldo não muda.
Um saque de um prazo fixo antes do vencimento dá `409` `conta_bloqueada`.

## RF-04 e RF-05 — Transferir, tudo ou nada

```bash
pedir POST /transferencias '{"de":"<a minha>","para":"0001 / 12345678-9","valor":"30.00","op_id":"transf-1"}'
```

O `para` pode ser o id ou o número da conta. As duas contas mudam na mesma
transação do Postgres, em cada nó. A resposta traz o saldo da origem; o do
destino só vem se a conta também for tua. Moedas diferentes: `409`
`moedas_diferentes` (para converter, usa `/transferencias/conversao`).

## RF-19, RF-20 e CU-06 — Moedas, câmbio e autotransferência

- `POST /admin/taxas` (com `X-Chave-Admin`) regista uma taxa. Sem a chave dá `403`.
- `POST /transferencias/conversao` converte à taxa em vigor. A taxa fica gravada
  com a operação, e repetir o `op_id` devolve a mesma.
- `POST /transferencias/autotransferencia` move entre duas contas tuas; se as
  moedas diferem, é um câmbio.

## RF-23/24 — Poupança e prazo fixo

`POST /admin/juros` credita os juros devidos. É idempotente: corrê-lo duas vezes
no mesmo instante não paga duas vezes.

## RF-25 — Para outro banco

`POST /transferencias/externa` com `sistema_externo_id` (a lista está em
`GET /sistemas-externos`). Primeiro debita; depois pergunta ao outro banco. Se o
outro banco recusar, o valor volta à conta.

## RF-14 e RNF-01 — Auditoria: o dinheiro não se cria nem se destrói

`pedir GET /auditoria` (com sessão) → por moeda, `total` (a soma dos saldos) e
`total_esperado` (a soma do histórico). A `divergencia` é zero. Repete depois de
cada passo desta guia: o total muda com depósitos, saques e juros, e nunca com
transferências.

## RF-07 e RF-13 — Repetir sem duplicar

O mesmo pedido com o **mesmo** `op_id` devolve o mesmo corpo, e o dinheiro move-se
uma só vez. O mesmo `op_id` com outro valor também devolve o resultado guardado.
O painel reutiliza o `op_id` quando se carrega outra vez com os mesmos dados (por
exemplo, depois de um `503`); só gera um novo quando os dados mudam.

Uma escrita que chegue a uma réplica dá `409` `nao_sou_primario`, com
`primario_provavel`; o balanceador reenvia uma vez.

## RF-09 e RNF-03 — Eleição em menos de 2 segundos

`GET /interno/estado` em cada nó: um só `primário`. Mata o primário
(`docker compose kill no-x` em local; **Stop instance** na AWS). Mede até outro
nó dizer `primário` com o `epoch` + 1. Em local mediu-se 1,23 s
([`provas/api/sessao.md`](../provas/api/sessao.md)).

## RF-10, RF-11, RF-12 e RNF-02 — Replicar antes de responder, seguir, voltar

- O `200` de uma escrita só sai depois de 2 dos 3 nós a gravarem. Matar o
  primário logo a seguir não a perde: está na base do novo primário.
- Com um nó em baixo, os outros dois continuam a escrever.
- O nó que volta entra como réplica e pede o que lhe falta (`GET /interno/log`).
  O seu `ultimo_aplicado` alcança o dos outros.
- As três bases ficam iguais: compara-as como em
  [`GUIA-TOLERANCIA-A-FALHAS.md`, A.8](GUIA-TOLERANCIA-A-FALHAS.md#a8-as-três-bases-ficaram-iguais).

## RNF-06 — Sem maioria, não se escreve

Com dois nós em baixo, uma escrita dá `503` (`sem_quorum` ou `somente_leitura`), e
nada muda. As leituras continuam. Quando volta um nó, a mesma escrita, com o
mesmo `op_id`, passa.

## RF-16 — Injetar falhas

Só com `FALHAS_ATIVAS=1` (o `compose.yaml` liga-o; na AWS fica desligado):
`POST /admin/falha` com `{"tipo":"atraso","ms":300}`, `{"tipo":"isolar","nos":["B"]}`,
`{"tipo":"limpar"}` ou `{"tipo":"derrubar"}`. Desligado, dá `403`
`falhas_desativadas`.

## Segurança das rotas entre nós

`/interno/replicar`, `/interno/votar` e `/interno/log` sem `X-Chave-Cluster` dão
`403` `nao_e_par_do_cluster`. Uma replicação forjada com um `epoch` alto não muda
nada. `/interno/estado` e `/interno/cluster` são públicos: o balanceador e o
painel precisam deles, e não mostram contas.

## O que não há

| Requisito | Estado |
|---|---|
| RF-15, métricas | Não há rota de métricas |
| RF-17, cliente de linha de comandos | Não há; usa-se `curl` ou o script de provas |
| RNF-04 e RNF-05, débito e latência | Medidos, e **não se cumprem**: ~10 escritas/s (meta 500). `python3 provas/scripts/medir_desempenho.py` com o `docker compose` de pé; resultado em [`provas/desempenho/medicao.md`](../provas/desempenho/medicao.md) |
| Recuperação de senha | Retirada de propósito (ver acima) |
