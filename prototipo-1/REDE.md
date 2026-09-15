# Pôr o cluster a correr em dois laptops

Guia para o dia da demonstração. Lê-se de pé, ao lado das máquinas.

O resto está no [`README.md`](README.md); aqui só está a rede, que é onde as
coisas correm mal.

---

## Primeiro: três nós, mesmo com dois laptops

**PC1 corre o nó A. PC2 corre os nós B e C.**

Não é capricho. Com dois nós a maioria continua a ser dois — metade mais um — por
isso a queda de qualquer um deles deixa o outro sem maioria, em somente leitura.
Não haveria failover **com escrita** para demonstrar, que é a coisa que o trabalho
inteiro existe para mostrar.

Com três, cai um e os outros dois ainda são maioria: o serviço continua.

---

## 1. Descobrir os endereços

```bash
ip addr | grep 'inet 192\.\|inet 10\.'     # Linux
ipconfig getifaddr en0                       # macOS, Wi-Fi
```

Os dois laptops têm de estar na **mesma rede**, e não em qualquer rede:

- **nada de VPN ligada** — o tráfego sai pelo túnel e o outro laptop deixa de ser
  alcançável;
- **nada de rede de convidados** — muitas isolam os clientes uns dos outros por
  omissão, e nesse caso *nada* do que está aqui funciona;
- partilhar a ligação do telemóvel resolve quase sempre, quando a rede da
  faculdade não colabora.

Teste mais simples que existe, antes de qualquer outra coisa:

```bash
ping 192.168.0.12      # do PC1 para o PC2
```

Se o `ping` não passa, o problema não é do banco.

---

## 2. O mesmo `config/cluster.json` nos dois

O ficheiro é **igual nas duas máquinas**, byte a byte. Os endereços são os reais,
não `127.0.0.1`.

```json
{
  "nos": [
    {"id": "A", "endereco": "192.168.0.11", "porta": 8001},
    {"id": "B", "endereco": "192.168.0.12", "porta": 8001},
    {"id": "C", "endereco": "192.168.0.12", "porta": 8002}
  ],
  "heartbeat_ms": 150,
  "timeout_eleicao_ms": [800, 1500],
  "timeout_replicacao_ms": 500,
  "semente": 42
}
```

Repare que B e C partilham o endereço do PC2 e diferem na porta — é assim que dois
nós vivem na mesma máquina.

O ficheiro não está versionado (é local a cada demonstração); copia-se do exemplo:

```bash
cp config/cluster.exemplo.json config/cluster.json
```

---

## 3. Abrir as portas

```bash
sudo ufw allow 8001/tcp                    # Linux, Ubuntu/Debian
sudo firewall-cmd --add-port=8001/tcp      # Linux, Fedora
```

No PC2 são duas portas: 8001 e 8002.

No macOS a firewall pergunta ao arrancar o processo — basta responder
**Permitir**. Se ninguém perguntou e mesmo assim não passa:
Definições → Rede → Firewall → Opções, e permitir o `python3`.

---

## 4. Verificar antes de subir o cluster

```bash
./scripts/verificar_rede.sh config/cluster.json
```

**Este passo não se salta.** Com uma porta fechada, os sintomas são eleições sem
fim e o `epoch` a subir sozinho — que se parecem exatamente com um erro de
protocolo, e levam a procurar durante horas no sítio errado. Cinco segundos de
`curl` respondem à pergunta.

Ainda ninguém arrancou, por isso é normal que os três nós apareçam sem resposta.
O que interessa é correr o mesmo comando **depois** de arrancar e ver os três a
responder, de ambos os laptops.

---

## 5. Preparar a base e arrancar

```bash
pip install -r requisitos.txt
```

**No PC1:**

```bash
./scripts/preparar_postgres.sh a
python3 -m banco.servidor --id A --porta 8001 \
    --bd postgresql:///banco_a --config config/cluster.json \
    --endereco 0.0.0.0
```

**No PC2**, dois processos:

```bash
./scripts/preparar_postgres.sh b c
python3 -m banco.servidor --id B --porta 8001 \
    --bd postgresql:///banco_b --config config/cluster.json --endereco 0.0.0.0 &
python3 -m banco.servidor --id C --porta 8002 \
    --bd postgresql:///banco_c --config config/cluster.json --endereco 0.0.0.0 &
```

`--endereco 0.0.0.0` é obrigatório. Em `127.0.0.1` o nó funciona na sua própria
máquina e é invisível da outra — e o sintoma é indistinguível de uma porta
fechada.

Sem PostgreSQL à mão, `--armazem ficheiro` em todos os nós e o cluster funciona na
mesma.

Passados uns segundos, de qualquer um dos laptops:

```bash
python3 -m banco.cli --cluster config/cluster.json estado
```

```
  NÓ  PAPEL     EPOCH  ÍNDICE  COMMIT  CONTAS
  A   réplica       2       1       1       0
  B   réplica       2       1       1       0
  C   primário      2       1       1       0
```

Três nós, um primário, o mesmo `epoch`. O cluster está de pé.

---

## 6. Sintoma → causa

A tabela que poupa a tarde.

| O que se vê | Causa quase certa | Como confirmar |
|---|---|---|
| Eleições sem fim, `epoch` a subir sozinho | Uma porta fechada **num só sentido** | `verificar_rede.sh` dos **dois** laptops |
| Um nó nunca aparece no `estado` | Arrancou em `127.0.0.1` | Ver a linha de arranque dele |
| `não sou primário` em ciclo, sem nunca acertar | O `cluster.json` é diferente entre as máquinas | `diff` dos dois ficheiros |
| Tudo funciona num laptop, nada entre os dois | Rede de convidados, ou VPN ligada | `ping` do outro laptop |
| `sem_quorum` em todas as escritas | Só um nó de pé | `banco.cli estado` |
| `o ensaio está tomado` | O outro operador tem a sessão | `banco.cli ensaio estado` |
| Um nó recusa arrancar por a base ser de outro | Dois nós no mesmo DSN | Um `--bd` por nó |

---

## 7. A demonstração

```bash
python3 -m banco.cli --cluster config/cluster.json criar-conta alice --saldo 100.00
python3 -m banco.cli --cluster config/cluster.json criar-conta bob --saldo 0.00
python3 -m banco.cli --cluster config/cluster.json transferir alice bob 25.00
python3 -m banco.cli --cluster config/cluster.json auditoria     # anotar o total

# a sessão de ensaio é exclusiva: enquanto um a tem, o outro é recusado
python3 -m banco.cli --cluster config/cluster.json ensaio tomar --dono paulo
python3 -m banco.cli --cluster config/cluster.json falha derrubar --no C

python3 -m banco.cli --cluster config/cluster.json estado         # outro assumiu
python3 -m banco.cli --cluster config/cluster.json transferir alice bob 10.00
python3 -m banco.cli --cluster config/cluster.json auditoria      # o mesmo total
```

A última linha é a demonstração toda: **o total não mudou**.

### Com o frontend a ver

```bash
cloudflared tunnel --url http://localhost:8001
```

O túnel dá uma URL HTTPS nova a cada arranque. Abre-se a página com
`?api=<essa URL>` e vê-se o failover acontecer: o nó derrubado fica coral, outro
assume, e o total em circulação não se mexe.

Para isto funcionar, o nó exposto arranca com `--encaminhar-escritas`: quando
deixa de ser primário, reenvia as escritas ao primário em vez de as recusar com um
endereço de LAN que o navegador nunca alcançaria.

---

## 8. Voltar a pôr tudo como estava

```bash
python3 -m banco.cli --cluster config/cluster.json ensaio largar
# fechar o túnel e os processos dos nós
sudo ufw delete allow 8001/tcp
```

As bases `banco_a`, `banco_b` e `banco_c` ficam com o estado da demonstração. Para
recomeçar do zero: `dropdb banco_a && ./scripts/preparar_postgres.sh a`.
