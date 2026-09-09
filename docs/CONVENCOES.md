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

### 4. Sem dependências externas

Só a biblioteca padrão do Python 3.10+: `http.server`, `json`, `threading`,
`socket`, `argparse`, `dataclasses`. A única exceção é `pytest`, e só para testes.

A razão é prática: o sistema vai ser demonstrado em **2 a 3 laptops diferentes**
numa rede local. Sem dependências, pôr o projeto a correr em cada máquina é
`git clone` e executar — não há venv para criar, `pip install` para falhar nem
versão divergente entre computadores.

Acrescentar uma dependência é decisão do grupo, discutida antes, nunca resolvida
no meio de uma tarefa.

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
python3 -m pytest -q
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
