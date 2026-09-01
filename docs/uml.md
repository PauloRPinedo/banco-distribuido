# Diagramas UML

Os mesmos cinco diagramas em dois formatos:

- **Mermaid**, nesta pagina -- o GitHub renderiza sozinho, e so abrir o arquivo.
- **PlantUML**, em [`docs/uml/`](uml/) -- notacao mais ortodoxa (visibilidade,
  multiplicidade, estereotipos, notas), para exportar em SVG/PNG e anexar ao relatorio.

Para exportar os `.puml`:

```bash
# com o plantuml instalado
plantuml -tsvg docs/uml/*.puml

# ou sem instalar nada, baixando o jar
curl -sLo /tmp/plantuml.jar https://github.com/plantuml/plantuml/releases/download/v1.2024.7/plantuml-1.2024.7.jar
java -jar /tmp/plantuml.jar -tsvg -o ./saida docs/uml/*.puml
```

O desenho por tras destes diagramas esta descrito em [`arquitetura.md`](arquitetura.md).

---

## 1. Classes -- dominio e persistencia

Camada pura: nao conhece rede nem disco. E o determinismo do `AccountStore` que
permite replicar por log e recuperar por replay.

```mermaid
classDiagram
    class OpType {
        <<enumeration>>
        CREATE_ACCOUNT
        DEPOSIT
        WITHDRAW
        TRANSFER
        NOOP
    }

    class Operation {
        +str op_id
        +OpType type
        +str account_id
        +str from_account
        +str to_account
        +int amount_cents
        +touched_accounts() tuple
        +validate() void
        +to_payload() dict
    }

    class LogEntry {
        +int idx
        +int epoch
        +Operation operation
        +float ts
        +to_json() dict
        +from_json(dict)$ LogEntry
    }

    class Account {
        +str id
        +int balance_cents
    }

    class OperationResult {
        +str op_id
        +int applied_idx
        +dict balances
    }

    class AccountStore {
        +dict~str,Account~ accounts
        +list~LogEntry~ history
        +dict~str,OperationResult~ applied
        +int last_applied_idx
        +get_balance(id) int
        +total_cents() int
        +statement(id, limit) list
        +check(Operation) void
        +apply(LogEntry) OperationResult
    }

    class WriteAheadLog {
        -Path path
        -str fsync_mode
        +append(LogEntry) void
        +append_buffered(entries) int
        +wait_durable(target) void
        +truncate_from(idx) void
        +read_from(idx, limit) list
        +entry_at(idx) LogEntry
        +last_idx int
        +last_epoch int
    }

    class RecoveredState {
        +AccountStore store
        +WriteAheadLog wal
        +int last_idx
        +int commit_index
    }

    class BankError {
        <<exception>>
        +str code
        +int http_status
    }
    class InsufficientFunds { <<exception>> }
    class UnknownAccount { <<exception>> }
    class NotPrimary {
        <<exception>>
        +str primary_hint
    }
    class NoQuorum { <<exception>> }
    class ReadOnlyMode { <<exception>> }

    AccountStore "1" *-- "0..*" Account : contem
    AccountStore "1" o-- "0..*" LogEntry : history
    AccountStore "1" o-- "0..*" OperationResult : dedupe por op_id
    LogEntry "1" *-- "1" Operation
    Operation --> OpType
    AccountStore ..> InsufficientFunds : levanta
    AccountStore ..> UnknownAccount : levanta
    BankError <|-- InsufficientFunds
    BankError <|-- UnknownAccount
    BankError <|-- NotPrimary
    BankError <|-- NoQuorum
    BankError <|-- ReadOnlyMode
    WriteAheadLog "1" o-- "0..*" LogEntry : persiste
    RecoveredState --> AccountStore
    RecoveredState --> WriteAheadLog
```

Tres decisoes que este diagrama codifica:

- **`op_id`** e gerado pelo cliente e mantido em toda retentativa. E a chave de
  idempotencia que torna seguro repetir uma transferencia quando o primario cai (RF-13).
- **`touched_accounts()`** devolve as contas **ordenadas**. Como os locks sao sempre
  tomados nessa ordem, duas transferencias cruzadas nunca dao deadlock.
- **Uma transferencia e uma unica `LogEntry`**, aplicada por uma unica chamada de
  `apply`. E dai que vem a atomicidade de RF-05, sem protocolo de duas fases.

## 2. Classes -- replicacao e eleicao

```mermaid
classDiagram
    class ReplicatedLog {
        -WriteAheadLog wal
        -int commit_index
        +dict match_idx
        +dict next_idx
        +append_local_buffered(op, epoch) LogEntry
        +record_match(node, idx) void
        +advance_commit(epoch) int
        +next_batch_for(node) tuple
        +back_off(node, hint) void
        +matches(prev_idx, prev_epoch) bool
        +append_from_leader(prev_idx, entries) int
        +set_commit(leader_commit) int
    }

    class PrimaryReplicator {
        -int quorum
        -RLock store_lock
        -Lock _append_lock
        +submit(Operation) OperationResult
        +replicate(up_to_idx, timeout) bool
        +commit_noop() void
        +apply_committed() int
        +has_write_quorum() bool
        +ensure_writable() void
    }

    class ReplicaApplier {
        -RLock store_lock
        +handle_append_entries(msg) AppendAck
        +apply_committed() int
    }

    class AppendEntries {
        +int epoch
        +str leader_id
        +int prev_idx
        +int prev_epoch
        +list entries
        +int leader_commit
    }
    class AppendAck {
        +int epoch
        +bool success
        +int match_idx
        +str node_id
    }
    class RequestVote {
        +int epoch
        +str candidate_id
        +int last_idx
        +int last_epoch
    }
    class VoteReply {
        +int epoch
        +bool granted
        +str reason
    }

    class NodeRole {
        <<enumeration>>
        REPLICA
        CANDIDATE
        PRIMARY
    }

    class NodeState {
        +str node_id
        -NodeRole role
        -int epoch
        -str voted_for
        +observe_epoch(epoch, leader) bool
        +start_candidacy() int
        +grant_vote(epoch, candidate) bool
        +become_primary() void
        +step_down(epoch) void
    }

    class ElectionManager {
        -int quorum
        +start_election() ElectionOutcome
        +handle_request_vote(msg) VoteReply
    }

    class HeartbeatSender {
        +start() void
        +notify_activity(node) void
        +alive_peers(janela) dict
    }

    class ElectionTimer {
        -float min_timeout_s
        -float max_timeout_s
        +reset() void
        +start() void
    }

    class AccountLockManager {
        -dict locks
        +acquire(ids, timeout) contexto
        +held_count() int
    }

    class PeerClient {
        <<interface>>
        +append_entries(node, msg, timeout) AppendAck
        +request_vote(node, msg, timeout) VoteReply
    }
    class HttpPeerClient
    class InMemoryPeerClient

    PeerClient <|.. HttpPeerClient
    PeerClient <|.. InMemoryPeerClient
    PrimaryReplicator --> ReplicatedLog
    PrimaryReplicator --> NodeState
    PrimaryReplicator --> AccountLockManager
    PrimaryReplicator --> PeerClient : envia
    PrimaryReplicator --> HeartbeatSender
    PrimaryReplicator ..> AppendEntries : cria
    ReplicaApplier --> ReplicatedLog
    ReplicaApplier --> NodeState
    ReplicaApplier --> ElectionTimer : reset
    ReplicaApplier ..> AppendAck : responde
    ElectionManager --> NodeState
    ElectionManager --> PeerClient
    ElectionManager ..> RequestVote : cria
    ElectionManager ..> VoteReply : responde
    ElectionTimer ..> ElectionManager : dispara eleicao
    NodeState --> NodeRole
```

Os pontos delicados, todos verificados por teste:

- **`advance_commit`** so confirma por contagem entradas do **epoch corrente**. Uma
  entrada herdada do primario anterior e confirmada por arraste, junto com o NOOP da
  promocao. Confirma-la por contagem permitiria reverte-la depois.
- **`NodeState`** grava `epoch` e `voted_for` com fsync **antes** de responder. Votar,
  cair e esquecer o voto elegeria dois primarios no mesmo epoch.
- **`ElectionTimer`** sorteia o timeout com uma semente **derivada por no**. Com a
  semente global pura, os tres sorteiam o mesmo valor, viram candidatos juntos e
  dividem os votos indefinidamente -- exatamente o que a aleatoriedade evita.

## 3. Sequencia -- transferencia confirmada por maioria

```mermaid
sequenceDiagram
    actor Cliente
    participant CLI as CLI banco_cli
    participant API as API client_routes
    participant P as PrimaryReplicator (A, epoch 7)
    participant LOG as ReplicatedLog + WAL
    participant B as Replica B
    participant C as Replica C
    participant ST as AccountStore

    Cliente->>CLI: transferir alice bob 25.00
    Note over CLI: gera op_id UMA vez,<br/>reutiliza em toda retentativa
    CLI->>API: POST /transfers {op_id, alice->bob, 2500}
    API->>P: ensure_writable()
    Note right of P: recusa se nao for primario<br/>ou se faltar maioria viva
    API->>P: submit(operation)
    P->>ST: applied[op_id] ja existe?
    Note right of ST: se sim, devolve o resultado guardado<br/>SEM mover dinheiro (RF-13)
    P->>P: locks(alice, bob) em ordem crescente
    P->>ST: check(): conta existe? saldo suficiente?
    Note right of ST: validar ANTES de replicar
    P->>LOG: append_local_buffered() -> idx 42
    P->>LOG: wait_durable(42)
    Note right of LOG: fsync FORA do lock de ordenacao:<br/>escritas concorrentes dividem um fsync
    par replicacao em paralelo
        P->>B: AppendEntries(epoch 7, prev 41, [42])
        B->>B: epoch ok, log matching ok, grava + fsync
        B-->>P: AppendAck(success, match_idx 42)
    and
        P->>C: AppendEntries(epoch 7, prev 41, [42])
        C-->>P: AppendAck(success, match_idx 42)
    end
    P->>LOG: advance_commit(7) -> maioria A+B de 3
    P->>ST: apply(entry 42)
    Note right of ST: debito e credito na MESMA chamada:<br/>nao existe estado intermediario
    P->>P: solta os locks
    P-->>API: OperationResult(idx 42, saldos)
    API-->>CLI: 200 OK
    CLI-->>Cliente: confirmada | alice=75.00 bob=25.00
```

Se a maioria nao responder dentro de `replication_timeout_ms`, a resposta e **503
`no_quorum`**: a entrada fica gravada porem **nao confirmada**. O cliente repete com o
mesmo `op_id` e o dinheiro se move exatamente uma vez.

## 4. Sequencia -- failover e fencing por epoch

```mermaid
sequenceDiagram
    participant A as A PRIMARIO epoch 7
    participant B as B replica epoch 7
    participant C as C replica epoch 7
    actor Cliente

    A->>B: AppendEntries (heartbeat, 150 ms)
    A->>C: AppendEntries (heartbeat)

    Note over A: A para de responder<br/>(queda ou lentidao)

    B->>B: sem heartbeat por 800-1500 ms
    Note right of B: timeout sorteado por no,<br/>para B e C nao concorrerem juntos
    B->>B: epoch = 8, vota em si, persiste com fsync
    B->>C: RequestVote(epoch 8, last_idx 41, last_epoch 7)
    C->>C: epoch 8 > 7, adota
    C->>C: ainda nao votei em 8
    C->>C: log do candidato esta em dia?
    Note right of C: so vota se last_epoch/last_idx do candidato<br/>forem >= os seus -- garante que o novo<br/>primario tenha TODAS as operacoes confirmadas
    C->>C: persiste voted_for=B antes de responder
    C-->>B: VoteReply(granted)
    B->>B: 2 votos de 3 = maioria -> PRIMARIO epoch 8
    B->>C: heartbeat imediato
    B->>B: grava e confirma NOOP no epoch 8
    Note right of B: sem o NOOP, entradas herdadas do epoch 7<br/>seriam confirmadas por contagem<br/>e poderiam ser revertidas
    Cliente->>B: POST /transfers
    B-->>Cliente: 200 OK
    Note over Cliente: escritas continuam com 1 de 3 caido (RF-11)

    Note over A: A volta a si (so estava lento)
    A->>C: AppendEntries(epoch 7)
    C-->>A: AppendAck(success=false, epoch=8)
    A->>A: 8 > 7 -> step_down(), vira replica
    Note right of A: FENCING: o primario antigo nao confirma nada.<br/>E assim que o split-brain e impedido.
    B->>A: AppendEntries(epoch 8) -> A alcanca o log
```

## 5. Estados -- papeis de um no

```mermaid
stateDiagram-v2
    [*] --> REPLICA: boot (snapshot + replay do WAL)
    REPLICA --> CANDIDATE: sem heartbeat por 800-1500 ms
    CANDIDATE --> PRIMARY: maioria dos votos, depois NOOP do epoch
    CANDIDATE --> REPLICA: perdeu, ou viu epoch maior
    CANDIDATE --> CANDIDATE: empate -- novo epoch e novo timeout
    PRIMARY --> REPLICA: recebeu epoch maior (fencing)

    state PRIMARY {
        [*] --> ComQuorum
        ComQuorum --> SomenteLeitura: maioria inalcancavel
        SomenteLeitura --> ComQuorum: maioria volta
    }
```

Um no **sempre** sobe como replica, mesmo que fosse primario antes de cair: quem manda
e decidido pela eleicao, nunca pelo que o no lembra de si mesmo.

Dentro de `PRIMARY` ha o modo degradado **somente leitura**: sem maioria viva, o
primario recusa escritas com 503 em vez de aceitar operacoes que nunca serao
confirmadas, mas continua respondendo saldo, extrato e auditoria.
