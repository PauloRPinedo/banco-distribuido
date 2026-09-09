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
| Protótipo 1 | [`prototipo-1/`](prototipo-1/) | Um banco correto num só nó | não iniciada |
| Protótipo 2 | [`prototipo-2/`](prototipo-2/) | Sobrevive à queda de um servidor | não iniciada |
| Projeto final | [`projeto-final/`](projeto-final/) | Prova, mede e mostra | não iniciada |

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

Não é preciso instalar nada. Só Python 3.10 ou mais recente, da biblioteca padrão.

```bash
git clone https://github.com/PauloRPinedo/banco-distribuido.git
cd banco-distribuido/prototipo-1

python3 -m banco.servidor --id A --porta 8001

python3 -m banco.cli criar-conta alice --saldo 100.00
python3 -m banco.cli criar-conta bob --saldo 0.00
python3 -m banco.cli transferir alice bob 25.00
python3 -m banco.cli auditoria

python3 -m pytest -q
```

A ausência de dependências é uma decisão, não um acaso: o sistema é demonstrado em
2 ou 3 laptops diferentes numa rede local, e pôr o projeto a correr em cada máquina
tem de ser `git clone` e executar.

Para o cluster em várias máquinas, ver o README do
[`prototipo-2/`](prototipo-2/).
