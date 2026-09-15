# Guia de instalação

Como pôr este repositório a correr, de raiz, numa máquina limpa.

---

## Primeiro: que pasta é que faz o quê

É a pergunta que mais custa a quem chega, e a resposta poupa meia hora:

| Pasta | O que é | Tem cluster? |
|---|---|---|
| **`prototipo-1/`** | Um banco **correto**, num nó só. FastAPI + PostgreSQL + painel React | **Não.** Um nó, ou dois contra a mesma base — que não é replicação |
| **`prototipo-2/`** | Um banco que **sobrevive à queda de um servidor**. Biblioteca padrão + painel em HTML | **Sim.** Três nós, replicação por log, eleição, failover |
| **`projeto-final/`** | A pilha expandida: balanceador, autenticação, Docker, CI/CD, nuvem | Não — o `cluster/` de lá ainda é um esqueleto |

---

## O que é preciso ter instalado

| Para | Precisa de |
|---|---|
| Correr os testes do domínio | **Python 3.10+**, e mais nada |
| Correr o Protótipo 2 inteiro | **Python 3.10+**, e mais nada |
| Correr o Protótipo 1 inteiro | **Docker** (traz o Python, o PostgreSQL e o Node lá dentro) |
| Mexer no painel do Protótipo 1 | **Node 20+** e `npm` |

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
