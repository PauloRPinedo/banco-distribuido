# Convenções de trabalho

Trabalho da disciplina de Computação Distribuída.
Universidade de São Paulo — ICMC, campus São Carlos.

| Número USP | Nome |
|---|---|
| 18404636 | Jefferson Daniel Flores Montenegro |
| 18514632 | Cristhian Jesus Maylle Briceño |
| 17819748 | Paulo Sebastian Rojo Pinedo |

O que o sistema faz, numa frase: **2 ou 3 servidores mantêm uma única cópia lógica
das contas e, mesmo com um servidor caindo no meio de uma transferência, o dinheiro
nunca é criado nem destruído.**

---

## Regras que valem para tudo

### 1. Idioma: português

Código, nomes de variáveis, comentários, mensagens de erro, saída do CLI,
documentação e mensagens de commit — tudo em português.

Ficam em inglês apenas as siglas técnicas já consagradas na literatura, porque
traduzi-las esconde a referência: `epoch`, `commit`, `log`, `WAL`, `quorum`,
`heartbeat`, `timeout`, `snapshot`.

Escreve-se `epoch`, não `época`. Escreve-se `contas`, não `accounts`.

### 2. Autoria

Os autores do projeto são os três integrantes da tabela acima, e mais ninguém.

As mensagens de commit não levam `Co-Authored-By`, assinaturas em rodapé nem
qualquer outro *trailer*. O autor de um commit é quem o escreveu.

### 3. É um trabalho de graduação, não um produto

O critério de qualidade aqui é **ser explicável na defesa**, não ser robusto em
produção. Entre duas soluções que resolvem o mesmo problema, ganha sempre a que
cabe num quadro branco.

Sinal de alarme: se justificar uma decisão de desenho leva mais de uma página,
provavelmente é a decisão errada para este projeto.

Isto não é desculpa para código incorreto. A invariante do dinheiro (RNF-01) não
se negocia — é o projeto inteiro. O que se corta é acessório: otimização,
generalidade, configurabilidade, casos extremos que nenhum teste da disciplina
exercita.

### 4. Dependências externas

A base continua a ser a biblioteca padrão do Python 3.10+: `http.server`, `json`,
`threading`, `socket`, `argparse`, `dataclasses`, `unittest`.

**Há exatamente uma dependência externa**, decidida pelo grupo em setembro de 2026:

| Dependência | Onde | Porquê |
|---|---|---|
| `psycopg[binary]>=3.1` | Só em `banco/persistencia/armazem_postgres.py` | O grupo decidiu que o PostgreSQL substitui o WAL em JSONL como armazém principal do log (ver `SPECS.md` 11.4) |

A dependência está **confinada a um único módulo**, importada dentro da função que
a usa e nunca no topo. A consequência é verificável num comando:

```bash
python3 -c "import banco.cluster.no"   # não toca em psycopg
```

**Os testes continuam a correr sem instalar nada.** `python3 -m unittest discover -s tests`
usa um armazém em memória; os testes contra a base real saltam-se sozinhos, com o
motivo escrito, se a variável `BANCO_BD_TESTE` não estiver definida. Continua a
usar-se o `unittest` da biblioteca padrão — um `pytest` obrigatório significaria um
`pip install` a mais em cada laptop, e quem o tiver instalado corre estes ficheiros
sem alteração nenhuma.

**O que se perdeu, dito sem rodeios:** pôr o *servidor* a correr numa máquina nova
já não é só `git clone` e executar. Passa a ser `git clone`, instalar o PostgreSQL,
correr `scripts/preparar_postgres.sh` e `pip install -r requisitos.txt`. Para o dia
da demonstração há duas saídas de emergência: `compose.yaml`, que sobe um
`postgres:16` com versão fixa, e `--armazem ficheiro`, que volta ao WAL em JSONL e
faz o cluster funcionar na mesma.

Acrescentar **outra** dependência é decisão do grupo, discutida antes, nunca
resolvida no meio de uma tarefa.

---

## As três etapas

O repositório tem uma pasta por entrega. Cada uma é autocontida e continua a
funcionar depois de a seguinte começar.

| Pasta | Etapa | Objetivo |
|---|---|---|
| `prototipo-1/` | Protótipo 1 | Um banco correto num só nó |
| `prototipo-2/` | Protótipo 2 | Sobrevive à queda de um servidor |
| `projeto-final/` | Projeto final | Prova, mede e mostra |

**Uma etapa entregue não se altera.** Corrigir o Protótipo 1 depois de entregue
apaga a evidência da progressão do trabalho, que é justamente o que a divisão em
etapas serve para mostrar. Erros encontrados tarde corrigem-se na etapa em curso e
registam-se na secção "o que mudou face à etapa anterior" do README dessa etapa.

> **Exceção decidida pelo grupo em setembro de 2026.** O Protótipo 1 foi reaberto
> para receber, na mesma pasta, o PostgreSQL, a replicação entre laptops, a injeção
> de falhas com sessão de ensaio exclusiva e um frontend web. Não é um erro
> corrigido tarde: é um alargamento de âmbito pedido depois da entrega. A
> justificação e o que se perde com isto estão em `SPECS.md` 11.6, e o README do
> Protótipo 1 tem a secção "o que mudou face à etapa entregue". O estado original
> continua a poder ver-se em `git show 7b430e6`.

Antes de escrever código para uma etapa, ler a secção correspondente do
[`ROADMAP.md`](ROADMAP.md).

---

## Onde está cada coisa

| Ficheiro | Para quê |
|---|---|
| [`proposta.md`](proposta.md) | A proposta entregue. Fonte dos requisitos F-xx, RF-xx e RNF-xx. **Não se edita** |
| [`SPECS.md`](SPECS.md) | Como o sistema funciona: protocolos, formatos, API, rastreabilidade de requisitos |
| [`CODESTYLE.md`](CODESTYLE.md) | Como se escreve o código e como se apresentam o CLI e o painel |
| [`ROADMAP.md`](ROADMAP.md) | O que se faz em cada etapa e subfase, e quem faz |

Quando uma decisão de desenho for tomada ou mudada, ela é registada no `SPECS.md`
**com a justificação**. Uma decisão sem o porquê é inútil na defesa e é a primeira
coisa que se esquece.

---

## Comandos

```bash
# um nó isolado (Protótipo 1)
python3 -m banco.servidor --id A --porta 8001

# um nó dentro do cluster (Protótipo 2 em diante)
python3 -m banco.servidor --id A --config config/cluster.json

# cliente
python3 -m banco.cli criar-conta alice --saldo 100.00
python3 -m banco.cli transferir alice bob 25.00
python3 -m banco.cli auditoria
python3 -m banco.cli estado

# testes
python3 -m unittest discover -s tests
```

Os comandos correm de dentro da pasta da etapa (`prototipo-1/`, `prototipo-2/`,
`projeto-final/`), não da raiz do repositório.

---

## Commits

- Mensagem em português, no imperativo: `Adiciona replicação por maioria`.
- Assunto até 72 caracteres, sem ponto final.
- Corpo a explicar **porquê**, não o quê — o *diff* já diz o quê.
- Sem *trailers*, sem assinaturas, sem emoji.
- Um commit por ideia. "Vários ajustes" não é um commit.

---

## Antes de dar uma tarefa por concluída

1. Os testes passam.
2. O que foi decidido está no `SPECS.md`, com a justificação.
3. A tarefa está marcada no `ROADMAP.md`.
4. O README da etapa reflete o estado real, incluindo o que **não** funciona.
5. Nada no que foi escrito viola as quatro regras do topo deste documento.

Sobre o ponto 4: relatar uma medição que não cumpre o requisito é melhor do que
omiti-la. A implementação é avaliada pelo que se sabe dela, não pelo que se promete.
