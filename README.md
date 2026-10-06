# Banco Distribuído

**Um banco que não perde dinheiro.** Três servidores mantêm uma única cópia
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
| Protótipo 2 | [`prototipo-2/`](prototipo-2/) | Sobrevive à queda de um servidor | **feito**, 251 testes e provas com failover |
| Etapa final | — | Implanta na AWS, mede e demonstra | próxima |

O Protótipo 1 foi entregue em setembro de 2026 com um banco correto num nó só, e
reaberto logo a seguir para receber o PostgreSQL, a replicação, a injeção de falhas
e um frontend. O efeito foi que o trabalho das etapas 2 e 3 passou a viver na pasta
da etapa 1, e deixou de haver uma pasta a mostrar o banco de um nó só isolado — que
é a razão de ser desta divisão.

A decisão foi desfeita. O Protótipo 1 é hoje o banco de um nó só: FastAPI e
PostgreSQL, sem replicação nem autenticação.

A replicação, a eleição e o failover que tinham ficado dentro do Protótipo 1
foram recuperados para `prototipo-2/`, que é onde a etapa 2 sempre devia ter
estado — primeiro sobre a biblioteca padrão, e depois sobre a mesma pilha do
Protótipo 1 (FastAPI, PostgreSQL, React), com um balanceador, login, moedas e
produtos. Matar o primário a meio de transferências elege outro em menos de 2 s
e o dinheiro não muda; as provas estão em `prototipo-2/provas/`. O que mudou de
uma etapa para a outra está em
[`prototipo-2/MUDANCAS-DESDE-PROTOTIPO-1.md`](prototipo-2/MUDANCAS-DESDE-PROTOTIPO-1.md).

| Quero ver | Comando |
|---|---|
| A etapa 1 como foi entregue | `git show 7b430e6` |
| A etapa 1 reaberta, com replicação e failover | `git show 3683a0f` |
| A etapa 2 sobre a biblioteca padrão, com failover | `git show 0307715:prototipo-2/README.md` |

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
| [`prototipo-2/README.md`](prototipo-2/README.md) | O cluster: instalação, uso, como funciona, o que funciona e o que falta |
| [`prototipo-2/MUDANCAS-DESDE-PROTOTIPO-1.md`](prototipo-2/MUDANCAS-DESDE-PROTOTIPO-1.md) | O que mudou do Protótipo 1 para o Protótipo 2 |
| [`prototipo-2/docs/GUIA-IMPLANTACAO.md`](prototipo-2/docs/GUIA-IMPLANTACAO.md) | Os serviços, localmente e na AWS, e o CI/CD |
| [`prototipo-2/docs/PROPOSTA-ARQUITETURA-AWS.md`](prototipo-2/docs/PROPOSTA-ARQUITETURA-AWS.md) | A arquitetura objetivo e o plano por fases |
