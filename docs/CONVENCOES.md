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

A base é a biblioteca padrão do Python 3.10+: `json`, `threading`, `argparse`,
`dataclasses`, `decimal`, `unittest`.

**Há quatro dependências externas, e são as mesmas em todas as etapas**, decididas
pelo grupo em setembro de 2026 (ver `SPECS.md` 11.8):

| Dependência | Porquê |
|---|---|
| `fastapi` | O servidor HTTP e a validação dos corpos |
| `uvicorn[standard]` | Quem corre o servidor |
| `psycopg2-binary` | O acesso ao PostgreSQL, que guarda o estado |
| `pydantic` | Os modelos dos corpos, que vêm com o FastAPI |

Ter a mesma pilha nas três etapas é a decisão, e é o que faz a passagem de uma para
a outra ser uma questão de acrescentar em vez de reescrever.

**A regra de dependência que continua a valer**, e que é a que interessa: o domínio
não conhece rede nem disco. É verificável num comando:

```bash
cd prototipo-1
python3 -c "import banco.dominio.operacoes"   # não toca em psycopg2 nem em fastapi
```

**Os testes do domínio continuam a correr sem instalar nada.**
`python3 -m unittest discover -s tests` corre os 55 testes do domínio numa máquina
limpa. Os 42 de integração — que falam com um servidor a sério e com uma base a
sério — saltam-se sozinhos, com o motivo escrito, se a pilha não estiver instalada
ou se `BANCO_BD_TESTE` não estiver definida.

Continua a usar-se o `unittest` da biblioteca padrão. Um `pytest` obrigatório seria
um `pip install` a mais em cada laptop, e quem o tiver instalado corre estes
ficheiros sem alteração nenhuma.

**O que se perdeu, dito sem rodeios:** pôr o *servidor* a correr numa máquina nova
já não é só `git clone` e executar. É `git clone`, um PostgreSQL, e
`pip install -r requisitos.txt`. A saída de emergência para o dia da demonstração é
o `compose.yaml`, que sobe tudo — nó, base e painel — com um comando e com as
versões fixas.

Acrescentar uma **quinta** dependência é decisão do grupo, discutida antes, nunca
resolvida no meio de uma tarefa. Foi por esta regra que os testes de integração
falam por `urllib` em vez de pelo `TestClient` do FastAPI, que arrastaria o `httpx`.

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

> **O Protótipo 1 foi reaberto e depois reconstruído (setembro de 2026).** Primeiro
> reabriu-se a etapa entregue para lhe acrescentar, na mesma pasta, o PostgreSQL, a
> replicação, a injeção de falhas e um frontend. O efeito foi que o trabalho das
> etapas 2 e 3 passou a viver dentro da pasta da etapa 1, e deixou de haver uma
> pasta a mostrar o banco de um nó só a funcionar isolado — que é a razão de ser
> desta divisão.
>
> A decisão foi desfeita. O Protótipo 1 é agora uma versão básica do projeto final:
> as mesmas camadas e a mesma pilha, sem replicação nem autenticação. A
> justificação, e os quatro desvios que isto custa, estão em `SPECS.md` 11.8, e o
> README da etapa tem a secção "o que mudou face à etapa entregue".
>
> A versão reaberta vê-se em `git show 3683a0f` e a entregue em `git show 7b430e6`.

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
# tudo de uma vez: nó, base e painel
docker compose up --build

# só o nó, contra um PostgreSQL já a correr
python3 -m banco.servidor --id A --porta 8001

# cliente: é o painel em http://localhost:8080, ou curl
curl -X POST localhost:8001/contas -H 'Content-Type: application/json' \
     -d '{"conta":"alice","saldo_inicial":"100.00","op_id":"exemplo-01"}'
curl -X POST localhost:8001/transferencias -H 'Content-Type: application/json' \
     -d '{"de":"alice","para":"bob","valor":"25.00","op_id":"exemplo-02"}'
curl localhost:8001/auditoria

# testes: os do domínio sem instalar nada, os de integração com a pilha e uma base
python3 -m unittest discover -s tests
BANCO_BD_TESTE=postgresql:///banco_teste python3 -m unittest discover -s tests
```

O dinheiro viaja como texto — `"25.00"`, nunca `25.00` — e o `op_id` é gerado pelo
cliente. As duas regras são de `SPECS.md` 6.

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
