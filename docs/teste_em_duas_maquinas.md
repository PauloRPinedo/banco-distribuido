# Teste em duas maquinas

Guia para rodar o banco distribuido em **duas computadoras** na mesma rede local e
comprovar, na pratica, que o sistema nao perde dinheiro quando um servidor cai.

Nada aqui exige conhecimento previo do codigo. Siga na ordem.

---

## 1. Por que 3 nos em 2 maquinas, e nao 1 em cada

A tentacao e obvia: uma maquina, um servidor. Mas o sistema confirma uma escrita
somente depois que **a maioria** dos servidores gravou a operacao. Com 2 servidores a
maioria e 2, entao **basta um cair para as escritas pararem** -- e nao ha demonstracao
de failover nenhuma.

| Servidores | Maioria | Aguenta cair | Demonstra failover com escrita? |
|---|---|---|---|
| 2 | 2 | 0 | **nao** -- o sobrevivente fica somente leitura |
| 3 | 2 | 1 | **sim** |

Por isso o arranjo e assimetrico: **PC1 roda A e B, PC2 roda C**.

```
        PC1  (192.168.1.10)                PC2  (192.168.1.11)
   ┌──────────────────────────┐        ┌──────────────────────┐
   │   no A :8001             │        │   no C :8003         │
   │   no B :8002             │◄──────►│                      │
   └──────────────────────────┘  LAN   └──────────────────────┘

   maioria = 2 de 3
   matar A          -> B ou C assume, escritas seguem     OK
   desligar o PC2   -> A+B sao maioria, escritas seguem   OK
   desligar o PC1   -> C sozinho: somente leitura         esperado
```

O ultimo caso nao e um defeito: com um so no vivo nao existe em quem replicar, e o
sistema recusa a escrita em vez de aceitar uma operacao que poderia se perder. Esta
decisao esta explicada em [`arquitetura.md`](arquitetura.md), secao 2.

## 2. Antes de comecar

Nas **duas** maquinas:

```bash
git clone https://github.com/PauloRPinedo/banco-distribuido.git
cd banco-distribuido
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Requisitos: Python 3.10 ou mais novo, e as duas maquinas na mesma rede (mesmo wifi ou
mesmo cabo). Nao precisa de banco de dados, Docker nem nada instalado alem disso.

## 3. Descobrir o IP de cada maquina

Em cada uma:

```bash
hostname -I | awk '{print $1}'      # Linux
ipconfig getifaddr en0              # macOS
```

Anote os dois. Neste guia:

- **PC1** = `192.168.1.10`
- **PC2** = `192.168.1.11`

Troque pelos seus IPs reais em tudo o que vem a seguir. Nao use `127.0.0.1`: esse
endereco significa "esta mesma maquina" e a outra nunca vai alcancar.

## 4. Escrever a configuracao (identica nas duas maquinas)

```bash
cp config/cluster.lan.example.json config/cluster.lan.json
```

Edite `config/cluster.lan.json` e ponha os IPs reais:

```json
{
  "cluster_id": "banco-usp-lan",
  "nodes": [
    {"id": "A", "host": "192.168.1.10", "port": 8001},
    {"id": "B", "host": "192.168.1.10", "port": 8002},
    {"id": "C", "host": "192.168.1.11", "port": 8003}
  ],
  "timing": {
    "heartbeat_interval_ms": 200,
    "election_timeout_min_ms": 1200,
    "election_timeout_max_ms": 2400,
    "replication_timeout_ms": 1000,
    "vote_timeout_ms": 600
  },
  "storage": {"data_dir": "./data", "fsync_mode": "batch"}
}
```

> **O arquivo tem de ser identico nas duas maquinas.** E dessa lista que sai o tamanho
> da maioria. Se o PC1 achar que o cluster tem 3 nos e o PC2 achar que tem 2, os dois
> calculam maiorias diferentes e o sistema pode aceitar duas escritas conflitantes.
> Copie o arquivo, nao redigite.

Os tempos aqui sao mais folgados que os do `cluster.example.json` (que serve para tudo
na mesma maquina). Numa rede real, um pico de latencia do wifi com timeouts curtos
derruba um primario saudavel e o cluster fica trocando de lider sem parar.

## 5. Liberar os portos no firewall

No **PC1** (que hospeda A e B):

```bash
sudo ufw allow 8001:8002/tcp        # Linux com ufw
```

No **PC2** (que hospeda C):

```bash
sudo ufw allow 8003/tcp
```

Se `ufw` nao estiver ativo (`sudo ufw status` responde `inactive`), nao ha nada a
liberar. No macOS, autorize o Python quando o sistema perguntar.

## 6. Testar a rede ANTES de subir o cluster

Este passo parece dispensavel e nao e. Se o firewall bloquear a porta, os sintomas
(eleicoes sem fim, epoch subindo sozinho, "somente leitura") parecem um bug do
protocolo, e voce vai depurar o lugar errado por horas.

Suba **um** servidor no PC2:

```bash
# no PC2
python -m bank.server --config config/cluster.lan.json --id C
```

E, do **PC1**, tente alcanca-lo:

```bash
# no PC1
curl http://192.168.1.11:8003/admin/status
```

Tem de voltar um JSON com `"node_id": "C"`. Se travar ou der "connection refused":

- confira o IP (`hostname -I` no PC2);
- confira o firewall (passo 5);
- confirme que as duas maquinas estao na mesma rede (`ping 192.168.1.11`).

So siga adiante quando esse `curl` funcionar. Depois, pare o servidor com `Ctrl+C`.

## 7. Subir o cluster

**No PC1** (dois servidores, em dois terminais ou com `&`):

```bash
python -m bank.server --config config/cluster.lan.json --id A &
python -m bank.server --config config/cluster.lan.json --id B &
```

**No PC2**:

```bash
python -m bank.server --config config/cluster.lan.json --id C &
```

Os servidores escutam em `0.0.0.0` por padrao (todas as interfaces), que e o necessario
para a outra maquina alcancar. O endereco anunciado aos colegas continua sendo o `host`
da configuracao.

Defina a lista de servidores para o cliente, em **qualquer** uma das maquinas:

```bash
export BANCO_SERVERS=http://192.168.1.10:8001,http://192.168.1.10:8002,http://192.168.1.11:8003
python cli/banco_cli.py status
```

Esperado -- um `PRIMARIO` e duas `replica`, todos no mesmo epoch:

```
SERVIDOR                     ESTADO     PAPEL       EPOCH  COMMIT  APLICADO
--------------------------------------------------------------------------
http://192.168.1.10:8001     no ar      PRIMARIO        1       1         1
http://192.168.1.10:8002     no ar      replica         1       1         1
http://192.168.1.11:8003     no ar      replica         1       1         1
```

Qual dos tres vira primario e sorteado -- nao importa.

## 8. Demonstracao 1 -- replicacao

```bash
python cli/banco_cli.py criar-conta alice --saldo 100.00
python cli/banco_cli.py criar-conta bob --saldo 0.00
python cli/banco_cli.py transferir alice bob 25.00
python cli/banco_cli.py saldo alice        # 75.00
python cli/banco_cli.py saldo bob          # 25.00
```

Agora pergunte o total **a cada no separadamente**, inclusive ao que esta na outra
maquina:

```bash
for S in http://192.168.1.10:8001 http://192.168.1.10:8002 http://192.168.1.11:8003; do
  python cli/banco_cli.py --servers $S auditoria
done
```

Os tres tem de responder **100.00**. Se um divergir, ha bug de replicacao -- nao e
arredondamento, porque o dinheiro e inteiro em centavos.

Repare tambem que voce pode mandar os comandos de qualquer maquina: o cliente procura o
primario sozinho e segue a dica `primary_hint` quando fala com uma replica.

## 9. Demonstracao 2 -- failover (o ponto do projeto)

Descubra quem e o primario com `python cli/banco_cli.py status`. Anote a **porta** dele
e, na maquina onde ele roda, descubra o PID por essa porta:

```bash
ss -ltnp | grep ':8001'     # troque pela porta do primario atual
# saida: ... users:(("python",pid=12345,fd=9))
kill -9 12345               # o PID que apareceu
```

> Evite `pkill -f "bank.server"` para isso. O `-f` compara a linha de comando inteira, e
> a linha do **proprio shell** que voce digitou tambem contem esse texto -- o comando
> mata a si mesmo antes de terminar. Matar pelo PID da porta nao tem essa ambiguidade.
> (Para parar tudo de uma vez, use o `scripts/stop_cluster.sh`, que mata pelos PIDs
> registrados em `data/pids`.)

`-9` de proposito: um encerramento gentil daria ao processo a chance de terminar o que
faltasse, e o teste ficaria facil demais. A corretude tem de vir do fsync antes do ACK.

Em poucos segundos, rode de novo:

```bash
python cli/banco_cli.py status
```

Esperado: o no morto aparece `FORA DO AR`, **outro assumiu como PRIMARIO** e o **epoch
subiu**. O epoch e o numero do mandato: ele so cresce, e e o que impede o primario
antigo de voltar mandando.

Agora o que importa:

```bash
python cli/banco_cli.py transferir alice bob 10.00   # escritas CONTINUAM
python cli/banco_cli.py auditoria                    # total AINDA 100.00
```

O dinheiro nao mudou. Confirme nos dois nos que sobraram.

## 10. Demonstracao 3 -- reintegracao

Suba de novo o no que voce matou, com o **mesmo** `--data-dir`:

```bash
python -m bank.server --config config/cluster.lan.json --id A &
```

Espere alguns segundos e rode `status`. Ele volta como **replica** (nunca como
primario, mesmo tendo sido primario antes) e alcanca o log sozinho: mesmo `COMMIT` e
mesmo `APLICADO` que os outros. Sem intervencao manual -- ele recupera pelo disco,
lendo o snapshot e reproduzindo o WAL.

## 11. Demonstracao 4 -- particao de rede

Esta so e possivel com duas maquinas de verdade, e e a mais interessante.

**Desligue o wifi do PC2** (ou tire o cabo). Nao mate o processo -- o no C continua
vivo, apenas isolado.

No **PC1**, onde estao A e B (que juntos sao maioria):

```bash
python cli/banco_cli.py --servers http://192.168.1.10:8001,http://192.168.1.10:8002 transferir alice bob 5.00
python cli/banco_cli.py --servers http://192.168.1.10:8001,http://192.168.1.10:8002 auditoria
```

Funciona normalmente: 2 de 3 e maioria.

No **PC2**, o no C isolado:

```bash
curl http://127.0.0.1:8003/admin/status
```

Ele mostra `"write_available": false`. Leituras respondem, escritas sao recusadas. **C
nunca vira primario sozinho**, porque nao consegue os 2 votos que a maioria exige --
e por isso nao existem dois primarios aceitando dinheiro em paralelo.

**Religue o wifi do PC2.** Em segundos, C reconhece o epoch maior, se rebaixa a replica
e alcanca as operacoes que perdeu. Confira com `auditoria` nos tres: total identico.

## 12. Parar tudo

Se voce subiu os nos com `./scripts/run_cluster.sh`, pare com o script -- ele mata
pelos PIDs registrados em `data/pids`:

```bash
./scripts/stop_cluster.sh
```

Se subiu a mao (como nos passos acima), pare pelos PIDs das portas:

```bash
ss -ltnp | grep -E ':(8001|8002|8003)'
kill <PID> <PID>
```

Para zerar o estado e comecar do zero, apague `data/` nas duas maquinas.

## 13. Quando algo da errado

| Sintoma | Causa provavel | O que fazer |
|---|---|---|
| `address already in use` | ja ha um servidor nessa porta | ache o PID com `ss -ltnp \| grep :8001`, mate e suba de novo |
| `status` mostra tudo `FORA DO AR` | IP errado em `BANCO_SERVERS` | confira com `hostname -I` |
| Um no da outra maquina nao aparece | firewall | passo 5, e refaca o `curl` do passo 6 |
| Nenhum primario aparece | os nos nao se enxergam | passo 6 -- teste a rede antes do cluster |
| Epoch sobe sem parar, primario troca sozinho | timeouts curtos demais para a rede | aumente `election_timeout_*` em `cluster.lan.json` (nas **duas** maquinas) |
| Escritas dao 503 `read_only` | nao ha maioria viva | confira quantos nos estao no ar |
| Escritas dao 503 `no_quorum` | a rede engasgou no meio da replicacao | repita o comando: o `op_id` garante que nao duplica |
| Nos com `applied_idx` diferentes | normal por instantes | espere alguns segundos e confira de novo |

Um detalhe que confunde: `status` mostra `(somente leitura)` ao lado de **toda replica**.
Isso e esperado -- so o primario aceita escritas. O caso preocupante e o primario
aparecer como somente leitura, que significa falta de maioria.

## 14. Checklist da apresentacao

- [ ] `status` mostra 3 nos, um primario, mesmo epoch
- [ ] Transferencia confirmada e visivel nas duas maquinas
- [ ] `auditoria` da o mesmo total nos tres nos
- [ ] `SIGKILL` no primario -> outro assume e o epoch sobe
- [ ] Escritas continuam depois da queda
- [ ] Total inalterado depois do failover
- [ ] No reiniciado volta como replica e alcanca o log
- [ ] Com o PC2 isolado: PC1 escreve, C fica somente leitura
- [ ] Ao religar, C se reintegra e o total bate

## 15. Proximo passo: 3 maquinas

Com uma terceira maquina, basta mudar o `host` do no B para o IP dela em
`cluster.lan.json` (nas tres) e rodar um servidor em cada. O protocolo nao muda: a
maioria continua sendo 2 de 3, e agora a queda de qualquer **maquina** inteira, e nao
so de um processo, e tolerada.
