# Protótipo 2 — sobrevive à queda de um servidor

Trabalho de Computação Distribuída — USP/ICMC, São Carlos.

**O que esta etapa faz, numa frase:** três servidores mantêm uma única cópia
lógica das contas, e quando um deles morre a meio de uma transferência, outro
assume e o dinheiro continua exatamente o mesmo.

**Estado: 305 testes passam**, e correm num clone limpo **sem instalar nada** —
os 27 que exigem PostgreSQL saltam-se sozinhos, com o motivo escrito.

O failover foi verificado com três nós a sério: mata-se o primário com `kill -9`,
outro assume com um `epoch` maior, as escritas continuam, e a auditoria dá o
mesmo total antes e depois. O nó morto, ao voltar, recupera o seu log do disco e
apanha o que perdeu junto do primário.

> **Três nós, não dois.** A maioria é metade mais um, por isso com dois nós a
> maioria continua a ser dois: a queda de qualquer um deixaria o outro em
> somente-leitura e não haveria failover para mostrar. Com três, cai um e os
> outros dois ainda são maioria. Ver [`REDE.md`](REDE.md).

---

## Objetivo

O coração do trabalho. Três servidores mantêm a mesma base de contas; o
primário só confirma uma operação depois de ela estar em disco na **maioria** dos
nós; se o primário cai, os restantes elegem outro em menos de 2 segundos e o
serviço continua.

Prova-se com um servidor a ser morto ao vivo, no meio de transferências
concorrentes, e a auditoria a dar o mesmo total antes e depois.

---

## O que fica pronto

- Replicação por log, com o mesmo RPC a servir de replicação e de *heartbeat*
- Confirmação por maioria antes de responder ao cliente
- Eleição de primário por voto majoritário, com *fencing* por `epoch`
- Failover automático e reintegração do nó reiniciado
- Modo somente leitura quando não há maioria
- Cliente que encontra o primário sozinho e repete com o mesmo `op_id`
- Ensaio em 2 ou 3 laptops numa rede local

**Requisitos cobertos:** F-08, F-09 · RF-09 a RF-13 · RNF-01 a RNF-03, RNF-06

---

## Desvio face à proposta

A proposta descrevia um failover simples: "a próxima da lista assume". Adota-se em
vez disso **promoção por maioria de votos com *fencing* por `epoch`**.

O motivo: se o primário está apenas **lento** — GC, rede congestionada, disco
travado — e outro nó assume por *timeout*, passam a existir dois primários. Um
cliente deposita num, outro no outro, os logs divergem, e quando o antigo regressa
ou se perde uma operação ou se somam saldos incompatíveis. É exatamente a falha que
o projeto existe para impedir.

---

## Como executar

### Num só computador, três nós

```bash
cd prototipo-2
cp config/cluster.exemplo.json config/cluster.json   # pôr 127.0.0.1 nos três,
                                                     # portas 8101/8102/8103

python3 -m banco.servidor --id A --porta 8101 --config config/cluster.json \
        --armazem ficheiro --dados dados/A &
python3 -m banco.servidor --id B --porta 8102 --config config/cluster.json \
        --armazem ficheiro --dados dados/B &
python3 -m banco.servidor --id C --porta 8103 --config config/cluster.json \
        --armazem ficheiro --dados dados/C &

python3 -m banco.cli --cluster config/cluster.json estado
python3 -m banco.cli --cluster config/cluster.json criar-conta alice --saldo 100.00
python3 -m banco.cli --cluster config/cluster.json criar-conta bob --saldo 50.00
python3 -m banco.cli --cluster config/cluster.json transferir alice bob 25.00
```

Três coisas que não se podem esquecer, e que se manifestam de formas confusas:

- **`--porta` por nó.** Não se deduz do `cluster.json`; sem ela, os três tentam
  a 8001 e dois morrem a dizer que o endereço está ocupado.
- **`--dados` por nó.** Sem isso os três escrevem no mesmo log e corrompem-no.
- **`--cluster` vem antes do subcomando** no CLI, não depois.

`--armazem ficheiro` guarda o log em JSONL e não precisa de instalar nada. O
armazém principal é o PostgreSQL: ver `requisitos.txt` e
`scripts/preparar_postgres.sh`, e passar `--bd` com uma base **por nó**.

### Em três laptops na rede local

Um nó por máquina, um por integrante do grupo. O passo a passo, a *firewall*, a
verificação prévia e a tabela de sintoma → causa estão em [`REDE.md`](REDE.md).

### Demonstrar o failover

```bash
C="python3 -m banco.cli --cluster config/cluster.json"

$C estado          # quem é o primário?
$C auditoria       # anotar o total

kill -9 <pid do primário>

$C estado          # outro nó assumiu, com um epoch maior;
                   # o morto aparece "sem contacto"
$C transferir bob alice 10.00      # as escritas continuam
$C auditoria                       # o total é o mesmo
```

E, ao voltar a levantar o nó morto com o mesmo comando de arranque, ele recupera
o log do disco e apanha o resto junto do primário (RF-12).

---

## Divisão do trabalho

| Pessoa | Responsabilidade nesta etapa |
|---|---|
| **Cristhian Jesus Maylle Briceño** | **Núcleo distribuído.** Log de replicação e correspondência de log, `POST /interno/replicar` a servir de replicação e de *heartbeat*, confirmação por maioria, modo somente leitura, *timeout* de eleição sorteado com semente derivada por nó, máquina de estados da eleição, pedido de voto com as três condições, *fencing* por `epoch` e entrada `noop` ao assumir. |
| **Jefferson Daniel Flores Montenegro** | **Réplica e durabilidade.** Aplicação do log na réplica até ao `indice_commit`, arranque sempre como réplica, recuperação por *replay* seguida de sincronização com o primário, reintegração do nó reiniciado, sincronização da réplica muito atrasada. Testes de invariante do dinheiro sob falha. |
| **Paulo Sebastian Rojo Pinedo** | **Cluster e ensaio.** Formato e validação de `config/cluster.json`, cliente HTTP entre nós, `GET /interno/estado`, descoberta do primário no CLI e retentativa com o mesmo `op_id`. Guia de rede e condução do ensaio nos laptops. |

Os testes de failover são escritos em conjunto pelo **Cristhian** e pelo
**Jefferson**, por atravessarem replicação e persistência. O dono desta etapa é o
**Cristhian**.

---

## O que mudou face à etapa anterior

O Protótipo 1 é um banco correto **num nó**: valida, aplica e responde. Aqui o nó
deixa de decidir sozinho.

| Protótipo 1 | Protótipo 2 |
|---|---|
| Aceita escritas sempre | Só o primário aceita; a réplica devolve `409 nao_sou_primario` com o primário provável |
| Aplica e responde | Grava no log, **espera pela maioria**, e só então aplica e responde |
| Não tem papel nem `epoch` | Réplica, candidato ou primário, com `epoch` durável e *fencing* |
| Morre e o banco vai abaixo | Morre e outro assume; ao voltar, recupera e reintegra-se |
| O estado é o que está em memória | O estado é o *replay* do log, igual em todos os nós |

O domínio — dinheiro, contas, operações, a invariante — **não mudou uma linha**.
É a propriedade que tornou esta etapa possível: a mesma sequência de operações
produz sempre o mesmo estado, e é isso que permite replicar por log em vez de
replicar saldos.

---

## Modos de falha conhecidos (RNF-10)

| Situação | O que acontece | Porquê |
|---|---|---|
| O primário morre a meio de uma transferência | Ou a operação foi confirmada pela maioria e sobrevive, ou não foi e não aconteceu | Só se responde ao cliente depois de a entrada estar em disco na maioria |
| O primário morre e o cliente não sabe o desfecho | Repete com o mesmo `op_id` e o dinheiro move-se uma vez só | Deduplicação por `op_id` (RF-13) |
| **Dois dos três nós em baixo** | O que sobra recusa escritas com `503 sem_quorum`, e passado um *timeout* de eleição entra em `503 somente_leitura`. As leituras continuam | Um nó não é maioria. É o comportamento correto: aceitar escritas aqui seria arriscar perder dinheiro confirmado |
| Uma porta fechada **num só sentido** | Eleições sem fim e `epoch` a subir sozinho | Parece um erro de protocolo e não é. `scripts/verificar_rede.sh` responde em cinco segundos |
| Dois nós apontados à mesma base | O segundo recusa arrancar | `no_id` é chave primária em `estado_do_no`, de propósito |
| Um nó muito atrasado a reintegrar-se | Apanha o log por lotes de 500 entradas via `/interno/replicar` | `GET /interno/log?desde=N` existe na API mas **nenhum nó a chama** — é rota morta |
| Log a crescer sem limite | Cresce mesmo | **Não há snapshots.** O arranque faz *replay* completo. Com centenas de entradas demora milissegundos; com milhões não |

**Dois buracos conhecidos, e nenhum deles se resolve sozinho:**

1. **Não há teste de partição simétrica.** O mecanismo existe (`banco.cli falha
   isolar`) e há um teste a tirar um nó do quórum, mas o cenário dos dois lados
   sem maioria não está escrito.
2. **`SomenteLeitura` não tem nenhum teste que o dispare.** O caminho de código
   existe e está raciocinado, mas é a parte menos exercitada do desenho.

---

## Resultados

| | |
|---|---|
| `banco/` | 4 192 linhas em 37 ficheiros |
| `tests/` | 3 348 linhas, 256 métodos de teste (**305 casos**, os contratos correm por implementação) |
| `frontend/` | 1 072 linhas |
| Suite completa | ~18 s, sem instalar nada |
| Módulos acima das 250 linhas | `dominio/operacoes.py` (273) e `cluster/no.py` (261) — os dois estão assinalados e por dividir |

**Failover verificado à mão**, com três nós e `--armazem ficheiro`: matou-se o
primário com `kill -9`, o `epoch` subiu de 2 para 4, outro nó assumiu, o morto
apareceu como "sem contacto", as escritas continuaram e a auditoria deu
**R$ 150,00 antes e R$ 150,00 depois**. Ao voltar, o nó recuperou 2 contas e o
índice 4 do seu próprio log e apanhou o resto junto do primário.

O que **não** está medido: a vazão (RNF-04) e o p99 (RNF-05). Sabe-se que o
`lock` de estado serializa tudo, incluindo a espera pela maioria, mas não se põe
um número onde não houve medição.
