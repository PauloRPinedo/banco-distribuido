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
| Protótipo 1 | [`prototipo-1/`](prototipo-1/) | Um banco correto num só nó | **entregue**, e **reaberta** |
| Protótipo 2 | [`prototipo-2/`](prototipo-2/) | Sobrevive à queda de um servidor | feita **dentro do protótipo 1** |
| Projeto final | [`projeto-final/`](projeto-final/) | Prova, mede e mostra | por iniciar |

O Protótipo 1 foi entregue em setembro de 2026 com um banco correto num nó só, e
reaberto logo a seguir por decisão do grupo para receber o PostgreSQL, a
replicação entre laptops, a injeção de falhas e um frontend web. O desvio face à
regra de que uma etapa entregue não se altera está registado em
[`docs/SPECS.md`](docs/SPECS.md) 11.6, e o estado entregue continua acessível em
`git show 7b430e6`.

Cada pasta é autocontida e tem o seu próprio README, com o que foi entregue e como
o trabalho foi repartido entre os três.

---

## Documentação

| Documento | Para quê |
|---|---|
| [`docs/proposta.md`](docs/proposta.md) | A proposta entregue. Fonte dos requisitos F-xx, RF-xx e RNF-xx |
| [`docs/SPECS.md`](docs/SPECS.md) | Como o sistema funciona: protocolos, formatos, API, rastreabilidade |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | O que se faz em cada etapa e subfase, e quem faz |
| [`docs/CODESTYLE.md`](docs/CODESTYLE.md) | Estilo do código, do CLI e do painel |
| [`docs/CONVENCOES.md`](docs/CONVENCOES.md) | Convenções de trabalho no repositório |

---

## Como executar

Python 3.10 ou mais recente. Os **testes** correm sem instalar nada; o
**servidor** precisa do PostgreSQL, ou de `--armazem ficheiro`.

```bash
git clone https://github.com/PauloRPinedo/banco-distribuido.git
cd banco-distribuido/prototipo-1

# os testes correm sem instalar nada
python3 -m unittest discover -s tests

# o servidor precisa do PostgreSQL...
pip install -r requisitos.txt
./scripts/preparar_postgres.sh a
python3 -m banco.servidor --id A --porta 8001 --bd postgresql:///banco_a

# ...ou não, se for preciso
python3 -m banco.servidor --id A --porta 8001 --armazem ficheiro

python3 -m banco.cli criar-conta alice --saldo 100.00
python3 -m banco.cli transferir alice bob 25.00
python3 -m banco.cli auditoria
```

**Os testes continuam a correr sem instalar nada**, e isso é uma decisão: a suíte
tem de funcionar em qualquer laptop, sem venv para criar nem `pip install` para
falhar. O servidor passou a exigir o PostgreSQL quando o grupo decidiu que ele
substituiria o WAL — o que se ganhou e o que se perdeu está em
[`docs/SPECS.md`](docs/SPECS.md) 11.4.

Para o cluster em várias máquinas, o failover e o frontend, ver o README do
[`prototipo-1/`](prototipo-1/).
