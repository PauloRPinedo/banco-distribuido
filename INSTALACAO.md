# Guia de instalação

Como pôr este repositório a correr, de raiz, numa máquina limpa.

---

## Primeiro: que pasta é que faz o quê

É a pergunta que mais custa a quem chega, e a resposta poupa meia hora:

| Pasta | O que é | Tem cluster? |
|---|---|---|
| **`prototipo-1/`** | Um banco **correto**, num nó só. FastAPI + PostgreSQL + painel React | **Não.** Um nó, ou dois contra a mesma base — que não é replicação |
| **`prototipo-2/`** | Um banco que **sobrevive à queda de um servidor**. O Protótipo 1 com login, moedas, câmbio, poupança, prazo fixo e transferência externa, atrás de um balanceador. FastAPI + PostgreSQL + React | **Sim.** Três nós, cada um com a sua base; eleição com `epoch`, log replicado por maioria, failover — `docker compose kill` do primário e outro assume |

---

## O que é preciso ter instalado

| Para | Precisa de |
|---|---|
| Correr os testes do domínio do Protótipo 1 | **Python 3.10+**, e mais nada |
| Correr os testes do Protótipo 2 | **Python 3.12+** |
| Correr qualquer uma das etapas inteira | **Docker** com Compose v2 (traz o Python, o PostgreSQL e o Node lá dentro) |
| Mexer nos painéis | **Node 20+** e `npm` |

```bash
git clone https://github.com/PauloRPinedo/banco-distribuido.git
cd banco-distribuido
```

---

## Protótipo 1 — o banco de um nó

### Correr os testes sem instalar nada

```bash
cd prototipo-1
python3 -m unittest discover -s tests
```

Passam 55 e saltam-se 56, **com o motivo escrito**. Os que se saltam são os que
precisam da pilha do servidor e de uma base de dados; os 55 que correm são os do
domínio, que é onde o dinheiro se move.

### Levantar tudo com um comando

```bash
cd prototipo-1
docker compose up --build
```

- Painel: <http://localhost:8080>
- API: <http://localhost:8001>

O `docker compose` levanta o PostgreSQL, espera que ele esteja **pronto a
responder** (e não só arrancado), levanta o nó, e só depois serve o painel.

Para experimentar pela linha de comando:

```bash
curl -X POST localhost:8001/contas -H 'Content-Type: application/json' \
     -d '{"conta":"alice","saldo_inicial":"100.00","op_id":"exemplo-01"}'
curl -X POST localhost:8001/contas -H 'Content-Type: application/json' \
     -d '{"conta":"bob","op_id":"exemplo-02"}'
curl -X POST localhost:8001/transferencias -H 'Content-Type: application/json' \
     -d '{"de":"alice","para":"bob","valor":"25.50","op_id":"exemplo-03"}'
curl localhost:8001/auditoria
```

> **O dinheiro viaja como texto**: `"25.50"`, nunca `25.50`. Um número JSON é
> recusado com `400 valor_invalido`, de propósito.

### Correr os 111 testes, com base de dados

```bash
cd prototipo-1
pip install -r requisitos.txt
createdb banco_teste
BANCO_BD_TESTE=postgresql:///banco_teste python3 -m unittest discover -s tests
```

A base de teste é apagada no início de cada teste, e por isso o código
**recusa-se a trabalhar numa base cujo nome não contenha `teste`**.

### Mexer no painel

```bash
cd prototipo-1/frontend
npm install
npm run dev        # servidor de desenvolvimento, com recarga
npm run build      # compila para dist/
```

Os tipos de letra estão em `public/tipos/` e são servidos pelo próprio painel —
não há pedidos a CDN nenhum, e por isso funciona sem internet.

---

## Protótipo 2 — três nós, com failover

O guia completo — variáveis de ambiente, um nó sem Docker, o painel em modo de
desenvolvimento, a API — está em [`prototipo-2/README.md`](prototipo-2/README.md).
O essencial:

### Correr os testes sem instalar nada

```bash
cd prototipo-2/backend
python3 -m unittest discover -s tests
```

Passam 165 e saltam-se 86, com o motivo escrito. Os que correm incluem o
domínio e o protocolo inteiro — eleição, replicação, failover, partição — com
três nós em memória.

### Levantar os três nós

```bash
cd prototipo-2
export SECRET_KEY=$(openssl rand -hex 32)
docker compose up --build -d --wait
```

- Painel: <http://localhost:8080> (o separador **Cluster** mostra os três nós)
- Balanceador: <http://localhost:8000> — é com ele que o cliente fala
- Nós A, B e C, diretamente: `:8001`, `:8002`, `:8003`

A `SECRET_KEY` assina os tokens de sessão e tem de ser igual nos três nós; sem
ela, o compose recusa-se a arrancar.

### Ver o failover

```bash
curl -s localhost:8000/interno/estado     # quem é o primário
docker compose kill no-c                  # mata-o (troca c pelo que for)
curl -s localhost:8000/interno/estado     # outro nó, com epoch maior
docker compose start no-c                 # volta como réplica e põe-se em dia
docker compose down -v                    # no fim: para tudo e apaga as bases
```

### Correr os 251 testes, com base de dados

```bash
cd prototipo-2
python3 -m venv .venv
.venv/bin/pip install -r backend/requisitos.txt -r balanceador/requisitos.txt
docker run -d --name banco-teste -p 55432:5432 -e POSTGRES_DB=banco_teste \
  -e POSTGRES_USER=banco -e POSTGRES_PASSWORD=banco postgres:16-alpine
(cd backend && BANCO_BD_TESTE=postgresql://banco:banco@localhost:55432/banco_teste \
  ../.venv/bin/python -m unittest discover -s tests)
(cd balanceador && ../.venv/bin/python -m unittest discover -s tests)
docker rm -f banco-teste
```

Entre os 251 estão sete que arrancam três processos reais, cada um com a sua
base, e matam o primário com `kill -9`.
