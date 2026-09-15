# Banco Distribuído

**Um banco que não perde dinheiro.** De 2 a 3 servidores mantêm uma única cópia
lógica das contas e, mesmo com um servidor a cair no meio de uma transferência, o
dinheiro nunca é criado nem destruído.

Trabalho da disciplina de Computação Distribuída
Universidade de São Paulo — Instituto de Ciências Matemáticas e de Computação
Campus São Carlos, São Paulo, Brasil

| Número USP | Nome |
|---|---|
| 18404636 | Jefferson Daniel Flores Montenegro |
| 18514632 | Cristhian Jesus Maylle Briceño |
| 17819748 | Paulo Sebastian Rojo Pinedo |

---

## Em duas frases

Todos os servidores guardam todas as contas, por isso uma transferência é sempre
**local ao primário** — débito e crédito na mesma máquina, na mesma entrada de log.
Não há *commit* em duas fases, e é essa simplificação que faz a atomicidade sair de
graça.

O primário só responde ao cliente depois de a operação estar gravada em disco na
**maioria** dos nós, e um primário antigo que regressa é rejeitado por ter um
`epoch` menor.

---

## As três etapas

| Etapa | Pasta | Objetivo | Estado |
|---|---|---|---|
| Protótipo 1 | [`prototipo-1/`](prototipo-1/) | Um banco correto, num ou em dois nós | **reconstruído**, 111 testes |
| Protótipo 2 | [`prototipo-2/`](prototipo-2/) | Sobrevive à queda de um servidor | **feita**, 305 testes |
| Projeto final | [`projeto-final/`](projeto-final/) | Prova, mede e mostra | em curso |

O Protótipo 1 foi entregue em setembro de 2026 com um banco correto num nó só, e
reaberto logo a seguir para receber o PostgreSQL, a replicação, a injeção de falhas
e um frontend. O efeito foi que o trabalho das etapas 2 e 3 passou a viver na pasta
da etapa 1, e deixou de haver uma pasta a mostrar o banco de um nó só isolado — que
é a razão de ser desta divisão.

A decisão foi desfeita. O Protótipo 1 é hoje uma versão básica do projeto final:
as mesmas camadas e a mesma pilha, sem replicação nem autenticação. O porquê, e os
quatro desvios que isto custa, estão no README dessa pasta.

A replicação, a eleição e o failover que tinham ficado dentro do Protótipo 1
foram recuperados para `prototipo-2/`, que é onde a etapa 2 sempre devia ter
estado. Corre sobre a biblioteca padrão, com três nós — um por portátil, um por
integrante do grupo.

| Quero ver | Comando |
|---|---|
| A etapa 1 como foi entregue | `git show 7b430e6` |
| A etapa 1 reaberta, com replicação e failover | `git show 3683a0f` |

Cada pasta é autocontida e tem o seu próprio README, com o que foi entregue e como
o trabalho foi repartido entre os três.

---

## Documentação

Cada etapa explica-se no seu próprio README. Não há um documento central, e é
de propósito: o que descreve uma etapa vive na pasta dessa etapa, e assim não se
pode desatualizar em relação ao código que descreve.

| Documento | Para quê |
|---|---|
| [`INSTALACAO.md`](INSTALACAO.md) | Pôr tudo a correr de raiz, etapa a etapa, e o que fazer quando não arranca |
| [`prototipo-1/README.md`](prototipo-1/README.md) | O banco de um nó: rotas, base de dados, o caminho de uma escrita |
| [`prototipo-1/REDE.md`](prototipo-1/REDE.md) | Os dois portáteis a servir contra a mesma base |
| [`prototipo-2/README.md`](prototipo-2/README.md) | O cluster: replicação por log, eleição e failover |
| [`prototipo-2/REDE.md`](prototipo-2/REDE.md) | Pôr o cluster a correr em três portáteis |
| [`prototipo-2/UML.md`](prototipo-2/UML.md) | Os diagramas do cluster, e a ordem dos passos de uma escrita |
| [`projeto-final/README.md`](projeto-final/README.md) | A pilha expandida: balanceador, autenticação, Docker, nuvem |

---

## Como executar

Python 3.10 ou mais recente. Os testes do **domínio** correm sem instalar nada; o
**servidor** precisa da pilha e de um PostgreSQL, ou de Docker.

```bash
git clone https://github.com/PauloRPinedo/banco-distribuido.git
cd banco-distribuido/prototipo-1

# tudo de uma vez: nó, base e painel
docker compose up --build
#   painel  -> http://localhost:8080
#   API     -> http://localhost:8001

# dois portáteis a servir contra a mesma base: ver prototipo-1/REDE.md

# os 55 testes do domínio, sem instalar nada
python3 -m unittest discover -s tests

# os 111, com a pilha e uma base descartável
pip install -r requisitos.txt
createdb banco_teste
BANCO_BD_TESTE=postgresql:///banco_teste python3 -m unittest discover -s tests
```

```bash
curl -X POST localhost:8001/contas -H 'Content-Type: application/json' \
     -d '{"conta":"alice","saldo_inicial":"100.00","op_id":"exemplo-01"}'
curl -X POST localhost:8001/transferencias -H 'Content-Type: application/json' \
     -d '{"de":"alice","para":"bob","valor":"25.00","op_id":"exemplo-02"}'
curl localhost:8001/auditoria
```

**Os testes do domínio continuam a correr sem instalar nada**, e isso é uma
decisão: a parte onde o dinheiro se move tem de ser verificável em qualquer
laptop, sem venv para criar nem `pip install` para falhar. Os de integração —
que falam com um servidor a sério e com uma base a sério — saltam-se sozinhos,
com o motivo escrito, quando não há pilha nem base.

Para o cluster em várias máquinas, o failover e o frontend completo, ver o README
do [`projeto-final/`](projeto-final/).
