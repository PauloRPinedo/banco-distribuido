# Banco Distribuido Tolerante a Falhas

Um banco com 2 ou 3 servidores que mantem **uma unica copia logica** das contas e que,
mesmo com um servidor caindo no meio de uma transferencia, **nunca cria nem destroi dinheiro**.

Projeto da disciplina de Sistemas Distribuidos / Computacao Distribuida
Universidade de Sao Paulo -- ICMC, campus Sao Carlos

| Numero USP | Nome | Componentes |
|---|---|---|
| 18404636 | Jefferson Daniel Flores Montenegro | `domain/`, `storage/` |
| 18514632 | Cristhian Jesus Maylle Briceno | `replication/`, `election/`, `concurrency/` |
| 17819748 | Paulo Sebastian Rojo Pinedo | `api/`, `cli/`, `observability/`, `faults.py` |

## Documentacao

- **[`docs/arquitetura.md`](docs/arquitetura.md)** -- documento principal: desenho do sistema,
  protocolo de replicacao, eleicao de primario, decisoes e rastreabilidade dos requisitos.
- [`docs/proposta_banco_distribuido_simples.md`](docs/proposta_banco_distribuido_simples.md)
  -- proposta original entregue.

## Em uma linha

Replicacao por log com confirmacao por **maioria** e **fencing por epoch**: o primario so
responde ao cliente depois que a operacao esta gravada de forma duravel na maioria dos nos, e
um primario antigo que volta a si e rejeitado por ter epoch menor. Uma transferencia e **uma
unica entrada de log**, entao a atomicidade nao precisa de commit em duas fases.

## Como executar

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# sobe 3 servidores locais
./scripts/run_cluster.sh --clean

# quem e o primario?
python cli/banco_cli.py status

python cli/banco_cli.py criar-conta alice --saldo 100.00
python cli/banco_cli.py criar-conta bob --saldo 0.00
python cli/banco_cli.py transferir alice bob 25.00
python cli/banco_cli.py auditoria

# derruba o primario e confere que outro assume
./scripts/kill_primary.sh

python cli/banco_cli.py transferir alice bob 10.00   # continua funcionando
python cli/banco_cli.py auditoria                    # total inalterado

pytest -q
```

## Estado da implementacao

| Fase | Escopo | Situacao |
|---|---|---|
| 1 | Arquitetura, estrutura de modulos, interfaces | **concluida** |
| 2 | No unico: dominio, WAL, API de cliente, CLI | pendente |
| 3 | Replicacao com quorum, idempotencia | pendente |
| 4 | Heartbeat, eleicao, failover, reintegracao | pendente |
| 5 | Injecao de falhas, metricas, benchmark, suite completa | pendente |

Na fase 1 os modulos existem com tipos, assinaturas e docstrings; os corpos de logica
levantam `NotImplementedError` e os testes ficam marcados com `skip` indicando a fase em que
serao implementados. `pytest -q` deve reportar **48 testes, todos skipped**.
