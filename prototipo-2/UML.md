# Diagramas do banco

Em Mermaid, para renderizarem sozinhos no GitHub sem instalar nada — a mesma
razão por que o projeto não tem dependências.

Os diagramas mostram **o que existe no código**, não uma versão idealizada dele.
Quando divergirem, o código é que está certo e o diagrama é que está velho.

---

## 1. Domínio: cliente, conta e operações

O núcleo do banco, e a única parte que não sabe nada de rede nem de disco.

```mermaid
classDiagram
    class Livro {
        +dict~str,Conta~ contas
        +criar(id, saldo_centavos, instante) Conta
        +obter(id) Conta
        +creditar(id, centavos, ...) Conta
        +debitar(id, centavos, ...) Conta
        +extrato(id) list~Movimento~
        +total_centavos() int
    }

    class Conta {
        +str id
        +int saldo_centavos
        +float criada_em
        +list~Movimento~ movimentos
    }

    class Movimento {
        +int indice
        +str tipo
        +int valor_centavos
        +str contraparte
        +int saldo_depois_centavos
        +float instante
    }

    class Operacao {
        <<interface>>
        +str tipo
        +contas_tocadas() tuple
        +validar(livro)
        +aplicar(livro, indice, instante) dict
        +para_dados() dict
    }

    class CriarConta {
        +str conta
        +int saldo_inicial_centavos
    }
    class Deposito {
        +str conta
        +int valor_centavos
    }
    class Saque {
        +str conta
        +int valor_centavos
    }
    class Transferencia {
        +str de
        +str para
        +int valor_centavos
    }
    class Noop {
        <<sem dados>>
    }

    Livro "1" *-- "muitas" Conta
    Conta "1" *-- "muitos" Movimento
    Operacao <|.. CriarConta
    Operacao <|.. Deposito
    Operacao <|.. Saque
    Operacao <|.. Transferencia
    Operacao <|.. Noop
    Operacao ..> Livro : aplica-se sobre
```

**O que o diagrama esconde e vale a pena dizer:** não há classe `Cliente`. Uma
conta é identificada por um `id` e mais nada — sem nome, sem documento, sem dono.
Não é esquecimento: autenticação está fora do âmbito por decisão da proposta, e
uma tabela de clientes sem autenticação seria decoração que ninguém usa.

**`Transferencia` é uma operação só.** Débito e crédito acontecem na mesma
chamada a `aplicar`, e é daí que vem a atomicidade de RF-05. Não existe instante
nenhum em que o dinheiro tenha saído de uma conta e ainda não tenha entrado na
outra.

---

## 2. Persistência e cluster

Como uma operação passa de objeto a linha durável, e quem a replica.

```mermaid
classDiagram
    class No {
        +str id
        +Livro livro
        +LogDeReplicacao log
        +Eleicao eleicao
        +Replicador replicador
        +executar(op_id, operacao) dict
        +replicar(epoch, id_lider, ...) dict
        +votar(pedido) dict
        +auditoria() dict
    }

    class ArmazemDeLog {
        <<interface>>
        +acrescentar(entrada)
        +ler_desde(indice) list
        +epoch_em(indice) int
        +truncar_a_partir_de(indice)
        +ler_estado() EstadoDoNo
        +gravar_commit(indice)
    }

    class ArmazemPostgres {
        <<principal>>
    }
    class ArmazemEmFicheiro {
        <<JSONL, emergência>>
    }
    class ArmazemEmMemoria {
        <<testes>>
    }

    class EntradaDeLog {
        +int indice
        +int epoch
        +str op_id
        +str tipo
        +dict dados
        +float instante
        +operacao() Operacao
    }

    class LogDeReplicacao {
        +int ultimo_indice
        +int ultimo_epoch
        +int indice_commit
        +corresponde(indice, epoch) bool
        +truncar_divergentes(desde)
        +confirmar_ate(indice)
    }

    class Eleicao {
        +str papel
        +int epoch
        +str votou_em
        +candidatar(indice, epoch) PedidoDeVoto
        +conceder_voto(pedido, ...) tuple
        +ver_epoch(epoch) bool
    }

    class Replicador {
        +replicar(entrada, prazo) bool
        +bater_coracao()
        +vejo_a_maioria() bool
    }

    class RegistoDeLocks {
        +adquirir(ids) context
    }

    class InjetorDeFalhas {
        +atraso(ms)
        +isolar(ids)
        +derrubar()
        +fala_com(id) bool
    }

    class TrancaDeEnsaio {
        +str dono
        +tomar(dono, duracao) str
        +verificar(fixacao)
        +para_replicas() dict
    }

    No "1" *-- "1" LogDeReplicacao
    No "1" *-- "1" Eleicao
    No "1" *-- "1" Replicador
    No "1" *-- "1" RegistoDeLocks
    No "1" *-- "1" InjetorDeFalhas
    No "1" *-- "1" TrancaDeEnsaio
    No "1" o-- "1" ArmazemDeLog
    LogDeReplicacao ..> ArmazemDeLog : guarda em
    ArmazemDeLog <|.. ArmazemPostgres
    ArmazemDeLog <|.. ArmazemEmFicheiro
    ArmazemDeLog <|.. ArmazemEmMemoria
    ArmazemDeLog ..> EntradaDeLog : guarda
    EntradaDeLog ..> Operacao : reconstrói
```

O `ArmazemDeLog` é uma interface por uma razão prática, não por gosto de
abstrair: os 305 testes correm numa máquina sem PostgreSQL instalado, e a
demonstração tem uma saída de emergência se a base não arrancar no dia.

**O `No` está partido em dois ficheiros**, e a divisão é por audiência:
`cluster/no.py` é o **banco** — aceita operações de clientes e responde a
leituras; `cluster/protocolo.py` é o **participante do protocolo** — atende os
pares em `/interno/replicar` e `/interno/votar`. Vem como *mixin* e não como
objeto à parte por honestidade: esses métodos mexem no mesmo livro e no mesmo log,
e fingir que são um colaborador independente esconderia o acoplamento em vez de o
resolver.

`cluster/vista.py` é um terceiro caminho, e está separado por uma razão de
correção: o frontend pergunta pelo cluster uma vez por segundo, e se essas chamadas
partilhassem o `ThreadPoolExecutor` de dois lugares que envia os *heartbeats*, uma
página aberta podia atrasar o batimento — e um *heartbeat* atrasado derruba um
primário saudável.

---

## 3. Uma transferência confirmada por maioria

A ordem dos passos é a da secção 5 do [`SPECS.md`](../docs/SPECS.md) e não pode
mudar.

```mermaid
sequenceDiagram
    actor Cliente
    participant P as nó A (primário)
    participant R1 as nó B (réplica)
    participant R2 as nó C (réplica)

    Cliente->>P: POST /transferencias<br/>{de, para, valor, op_id}
    Note over P: 1 op_id já aplicado? não
    Note over P: 2 locks de alice e bob,<br/>por ordem crescente de id
    Note over P: 3 validar: contas existem,<br/>saldo chega
    P->>P: 4 INSERT + commit síncrono<br/>(equivale ao fsync)

    par replicar em paralelo
        P->>R1: POST /interno/replicar
        R1->>R1: grava e confirma
        R1-->>P: ok, indice 143
    and
        P->>R2: POST /interno/replicar
        R2-->>P: ok, indice 143
    end

    Note over P: 5 maioria alcançada (2 de 3,<br/>o primário conta-se a si próprio)
    Note over P: 5b ainda sou primário? sim
    P->>P: 5c gravar indice_commit = 143
    Note over P: 6 aplicar ao livro,<br/>guardar a resposta do op_id
    P-->>Cliente: 200 {saldos}

    Note over Cliente,R2: a resposta só sai depois da maioria.<br/>É isto, e só isto, que faz a operação<br/>sobreviver à queda imediata do primário.
```

---

## 4. Failover com fencing por `epoch`

O que acontece quando o primário morre a meio.

```mermaid
sequenceDiagram
    participant A as nó A (primário, epoch 7)
    participant B as nó B (réplica)
    participant C as nó C (réplica)

    A-xA: SIGKILL
    Note over B,C: passa o timeout sorteado.<br/>B sorteou 120 ms, C sorteou 190 ms —<br/>sementes diferentes, e é por isso<br/>que a eleição converge.

    B->>B: epoch 7 → 8, vota em si
    B->>C: POST /interno/votar<br/>{epoch 8, ultimo_indice 143, ultimo_epoch 7}
    Note over C: as três condições:<br/>epoch maior ✓<br/>ainda não votou no 8 ✓<br/>log dele ≥ o meu ✓
    C->>C: grava epoch 8 e votou_em=B<br/>ANTES de responder
    C-->>B: concedido

    Note over B: 2 votos de 3 — maioria
    B->>B: assume o epoch 8
    B->>B: grava a entrada noop do epoch 8
    B->>C: heartbeat imediato (cala candidatos)

    Note over A: A volta a si
    A->>B: POST /interno/replicar {epoch 7}
    B-->>A: ok:false, epoch 8
    A->>A: vê um epoch maior:<br/>despromove-se a réplica
    Note over A,C: A nunca chegou a confirmar nada.<br/>Nunca houve dois primários no mesmo epoch.
```

**Por que é que a `noop` existe.** Uma entrada herdada do primário anterior, mesmo
presente na maioria dos nós, não pode ser confirmada por contagem de réplicas: há
um cenário conhecido em que acaba sobrescrita por um líder seguinte, e uma
operação já dada como confirmada desapareceria. Confirmando primeiro a `noop` do
`epoch` atual, tudo o que vem antes fica confirmado por arrasto.

---

## 4.1 Como o frontend vê o cluster

O túnel HTTPS aponta a **um** nó, mas o ecrã mostra os três.

```mermaid
sequenceDiagram
    actor Navegador
    participant T as nó A (atrás do túnel)
    participant B as nó B
    participant C as nó C (primário)

    Navegador->>T: GET /interno/cluster
    par pergunta aos pares em paralelo
        T->>B: GET /interno/estado
        B-->>T: papel, epoch, índices
    and
        T->>C: GET /interno/estado
        C-->>T: papel, epoch, índices
    end
    T-->>Navegador: {eu: "A", maioria: 2, nos: [A, B, C]}

    Note over Navegador: um par calado volta com vivo:false<br/>em vez de desaparecer da lista

    Navegador->>T: POST /transferencias
    Note over T: não sou primário, mas<br/>--encaminhar-escritas está ligado
    T->>C: POST /transferencias (o mesmo corpo, o mesmo op_id)
    C-->>T: 200 {saldos}
    T-->>Navegador: 200 {saldos}

    Note over Navegador,C: sem o reencaminhamento, o 409 traria um<br/>primario_provavel que é um endereço de LAN,<br/>inalcançável do navegador — e o failover<br/>partiria a página no momento que ela<br/>existe para mostrar.
```

O nó que reencaminha é um **cliente puro**: não grava nada, não toca no seu log, e
por isso a ordem da secção 5 do SPECS continua intacta. O `op_id` vem no corpo
original, o que torna o reenvio seguro de repetir.

---

## 5. Os papéis de um nó

```mermaid
stateDiagram-v2
    [*] --> Replica : arranca sempre como réplica,<br/>mesmo tendo sido primário
    Replica --> Candidato : sem heartbeat durante<br/>o timeout sorteado
    Candidato --> Primario : maioria dos votos
    Candidato --> Replica : perdeu, ou viu um epoch maior
    Candidato --> Candidato : empate — novo epoch,<br/>novo timeout
    Primario --> Replica : recebeu um epoch maior<br/>(fencing)

    note right of Replica
        Responde a leituras.
        Recusa escritas com
        409 nao_sou_primario.
    end note

    note right of Primario
        Único que escreve.
        Sem maioria à vista,
        passa a somente leitura.
    end note
```

---

## 6. As camadas, e o que cada uma pode importar

```mermaid
flowchart TD
    I["interface/<br/>servidor HTTP, rotas, CLI, frontend"]
    C["cluster/<br/>replicação, eleição, concorrência, falhas"]
    D["dominio/<br/>contas, dinheiro, operações"]
    P["persistencia/<br/>armazém do log, entradas"]

    I --> C
    C --> D
    C --> P
    P --> D

    style D fill:#E8EEFB,stroke:#1B4DB1
```

`dominio/` não importa nada de rede nem de disco, e isso é verificável:

```bash
grep -rn "^import\|^from" banco/dominio/*.py
```

A mesma sequência de entradas de log produz exatamente o mesmo estado em qualquer
nó, e é essa pureza que faz a replicação por log e a recuperação por *replay*
funcionarem.
