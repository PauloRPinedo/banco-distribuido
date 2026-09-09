# Protótipo 2 — Sobrevive à queda de um servidor

Segunda das três entregas do [Banco Distribuído](../README.md).

**Estado:** não iniciada. Depende do [Protótipo 1](../prototipo-1/) estar fechado.
As caixas por marcar estão no
[`ROADMAP.md`](../docs/ROADMAP.md#etapa-2--protótipo-2).

---

## Objetivo

O coração do trabalho. De 2 a 3 servidores mantêm a mesma base de contas; o
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

A justificação completa está na secção 11.1 do [`SPECS.md`](../docs/SPECS.md).

---

## Como executar

### Num só computador, três nós

```bash
cd prototipo-2
cp config/cluster.exemplo.json config/cluster.json

python3 -m banco.servidor --id A --config config/cluster.json &
python3 -m banco.servidor --id B --config config/cluster.json &
python3 -m banco.servidor --id C --config config/cluster.json &

python3 -m banco.cli estado
python3 -m banco.cli criar-conta alice --saldo 100.00
python3 -m banco.cli transferir alice bob 25.00
```

### Em 2 ou 3 laptops na rede local

**Usar sempre 3 nós, mesmo com 2 laptops** (o PC1 corre A, o PC2 corre B e C). Com
apenas 2 nós a maioria é 2, e a queda de qualquer um deixa o outro em somente
leitura — não haveria failover com escrita para demonstrar.

1. Descobrir o IP de cada laptop (`ip addr` ou `ifconfig`) e escrevê-los em
   `config/cluster.json`, igual em todas as máquinas.
2. Abrir as portas na *firewall* de cada laptop.
3. **Testar cada endereço com `curl` antes de subir o cluster:**
   ```bash
   curl http://192.168.0.12:8001/interno/estado
   ```
   Este passo evita o modo de falha mais confuso do projeto: com uma porta
   bloqueada, os sintomas — eleições sem fim, `epoch` a subir sozinho — parecem um
   erro de protocolo e levam a procurar no sítio errado.
4. Subir os nós, cada um a ligar em `0.0.0.0` (a `127.0.0.1` não é alcançável de
   fora).

### Demonstrar o failover

```bash
python3 -m banco.cli estado          # quem é o primário?
python3 -m banco.cli auditoria       # anotar o total

# matar o processo do primário no laptop dele

python3 -m banco.cli estado          # outro nó assumiu, epoch subiu
python3 -m banco.cli transferir alice bob 10.00   # continua a funcionar
python3 -m banco.cli auditoria       # o total é o mesmo
```

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

*A preencher durante a etapa: o que foi acrescentado ao Protótipo 1 e o que teve de
ser refeito. O código do Protótipo 1 fica intacto na sua pasta.*

---

## Modos de falha conhecidos

*A preencher durante a etapa (RNF-10): partição de rede, primário lento, perda de
maioria, nó reiniciado com log divergente.*

---

## Resultados

*A preencher no fecho da etapa: tempo de failover medido (RNF-03), número de testes
a passar e o que ficou por fazer.*
