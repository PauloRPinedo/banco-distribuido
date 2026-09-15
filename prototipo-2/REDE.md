# Pôr o cluster a correr em três portáteis

Um nó por máquina, um por integrante do grupo.

```
   PC1                    PC2                    PC3
   nó A  :8001            nó B  :8001            nó C  :8001
     └──────────────────────┴──────────────────────┘
              replicação por log, HTTP

   mata-se qualquer um  ->  os outros dois são maioria  ->  o serviço continua
```

## Porquê três, e não dois

A maioria é metade mais um. Com **dois** nós a maioria continua a ser dois, por
isso a queda de qualquer um deles deixa o outro sem maioria: recusa escritas com
`503 somente_leitura`, e não há failover nenhum para demonstrar.

Com **três**, cai um e os outros dois ainda são maioria. É a única topologia em
que RF-11 — *"continuar atendendo com um servidor fora do ar"* — se cumpre sem
notas de rodapé, e é por isso que a demonstração precisa das três máquinas.

Se no dia só houver dois portáteis, dá para correr três nós com dois: PC1 corre
A, PC2 corre B e C em portas diferentes. Funciona, e matar o PC1 mostra o
failover — mas matar o PC2 leva dois nós de três e deixa o cluster em
somente-leitura. É uma saída de emergência, não o plano.

---

## 1. Descobrir os endereços

```bash
ip addr | grep 'inet 192\.\|inet 10\.'     # Linux
ipconfig getifaddr en0                     # macOS, Wi-Fi
```

As três máquinas têm de estar na **mesma rede**, e não em qualquer rede:

- **nada de VPN ligada** — o tráfego sai pelo túnel e as outras máquinas deixam
  de ser alcançáveis;
- **nada de rede de convidados** — muitas isolam os clientes uns dos outros por
  omissão, e nesse caso *nada* do que está aqui funciona;
- partilhar a ligação do telemóvel resolve quase sempre, quando a rede da
  faculdade não colabora.

O teste mais simples que existe, antes de qualquer outra coisa — de cada máquina
para as outras duas:

```bash
ping 192.168.0.12
ping 192.168.0.13
```

Se o `ping` não passa, o problema não é do banco.

## 2. O mesmo `config/cluster.json` nas três

```bash
cp config/cluster.exemplo.json config/cluster.json
```

E pôr os endereços verdadeiros:

```json
{
  "nos": [
    {"id": "A", "endereco": "192.168.0.11", "porta": 8001},
    {"id": "B", "endereco": "192.168.0.12", "porta": 8001},
    {"id": "C", "endereco": "192.168.0.13", "porta": 8001}
  ],
  "heartbeat_ms": 150,
  "timeout_eleicao_ms": [800, 1500],
  "timeout_replicacao_ms": 500,
  "semente": 42
}
```

**O ficheiro tem de ser igual, byte a byte, nas três máquinas.** Um endereço
trocado numa delas dá `não sou primário` em ciclo, sem nunca acertar — e parece
um erro de protocolo quando é um erro de cópia. O ficheiro está no `.gitignore`
de propósito, porque os endereços mudam de rede para rede.

## 3. Abrir a porta 8001

```bash
sudo ufw allow 8001/tcp                    # Linux, Ubuntu/Debian
sudo firewall-cmd --add-port=8001/tcp      # Linux, Fedora
```

No macOS a firewall pergunta ao arrancar o processo — basta responder
**Permitir**. Se ninguém perguntou e mesmo assim não passa: Definições → Rede →
Firewall → Opções, e permitir o `python3`.

## 4. Verificar antes de subir o cluster

```bash
./scripts/verificar_rede.sh config/cluster.json
```

**Este passo não se salta.** Com uma porta fechada **num só sentido**, os
sintomas são eleições sem fim e o `epoch` a subir sozinho — que se parecem
exatamente com um erro de protocolo e levam a procurar durante horas no sítio
errado. Cinco segundos de `curl` respondem à pergunta.

Ainda ninguém arrancou, por isso é normal que os três nós apareçam sem resposta.
O que interessa é correr o mesmo comando **depois** de arrancar, das três
máquinas, e ver os três a responder.

## 5. Arrancar

Em cada máquina, com o seu `--id`:

```bash
# PC1
python3 -m banco.servidor --id A --porta 8001 --config config/cluster.json --armazem ficheiro
# PC2
python3 -m banco.servidor --id B --porta 8001 --config config/cluster.json --armazem ficheiro
# PC3
python3 -m banco.servidor --id C --porta 8001 --config config/cluster.json --armazem ficheiro
```

`--armazem ficheiro` guarda o log em JSONL e não precisa de instalar nada. Para
correr sobre PostgreSQL — que é o armazém principal — ver `requisitos.txt` e
`scripts/preparar_postgres.sh`, e passar `--bd` em vez de `--armazem ficheiro`.
**Uma base por nó**: o nó recusa arrancar se a base pertencer a outro id.

Passados uns segundos, de qualquer uma das máquinas:

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

## A demonstração

```bash
C="python3 -m banco.cli --cluster config/cluster.json"

$C criar-conta alice --saldo 100.00
$C criar-conta bob --saldo 50.00
$C transferir alice bob 25.00
$C auditoria                       # total em circulação: R$ 150,00
$C estado                          # ver quem é o primário
```

Agora **matar o primário**, na máquina dele:

```bash
kill -9 <pid do nó primário>
```

E, de qualquer uma das outras:

```bash
$C estado       # outro nó é primário, com um epoch maior;
                # o morto aparece "sem contacto"
$C transferir bob alice 10.00      # as escritas continuam
$C auditoria                       # o total não mudou: R$ 150,00
```

**É este o momento que interessa.** O dinheiro não mudou com um servidor a morrer
a meio do ensaio, que é a frase que o projeto inteiro existe para poder dizer.

Depois, **voltar a levantar o nó morto** com o mesmo comando de arranque: ele
recupera o log do disco, apanha o que perdeu junto do primário e volta a aparecer
como réplica com o mesmo índice dos outros (RF-12).

---

## Sintoma → causa

| O que se vê | Causa quase certa | Como confirmar |
|---|---|---|
| Eleições sem fim, `epoch` a subir sozinho | Uma porta fechada **num só sentido** | `verificar_rede.sh` das **três** máquinas |
| Um nó nunca aparece no `estado` | Arrancou em `127.0.0.1` | Ver a linha de arranque dele |
| `não sou primário` em ciclo, sem nunca acertar | O `cluster.json` é diferente entre as máquinas | `diff` dos três ficheiros |
| Tudo funciona numa máquina, nada entre elas | Rede de convidados, ou VPN ligada | `ping` das outras duas |
| `sem_quorum` em todas as escritas | Menos de dois nós de pé | `banco.cli estado` |
| `somente_leitura` | O nó não vê a maioria há mais de um *timeout* de eleição | `banco.cli estado` das outras máquinas |
| `o ensaio está tomado` | Outro operador tem a sessão exclusiva | `banco.cli ensaio estado` |
| Um nó recusa arrancar por a base ser de outro | Dois nós no mesmo DSN | Um `--bd` por nó |

## Voltar a pôr tudo como estava

```bash
# parar os processos em cada máquina, e apagar o estado local
rm -rf dados/ config/cluster.json

# fechar as portas que se abriram
sudo ufw delete allow 8001/tcp
```

---

## Num computador só

Para ensaiar sem as três máquinas, três processos com portas diferentes e um
`cluster.json` com `127.0.0.1` nos três:

```bash
python3 -m banco.servidor --id A --porta 8101 --config config/cluster.json \
        --armazem ficheiro --dados dados/A &
python3 -m banco.servidor --id B --porta 8102 --config config/cluster.json \
        --armazem ficheiro --dados dados/B &
python3 -m banco.servidor --id C --porta 8103 --config config/cluster.json \
        --armazem ficheiro --dados dados/C &
```

**Um `--dados` por nó**: sem isso os três escrevem no mesmo log e corrompem-no.
O resto da demonstração é igual, e é assim que o failover foi verificado antes
de esta guia ser escrita.
