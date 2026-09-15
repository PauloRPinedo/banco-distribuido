# CODESTYLE — Estilo de código e de interface

Duas partes: como se escreve o código (secções 1 a 6) e como o sistema se
apresenta a quem o usa (secções 7 a 9).

---

# Parte I — Código

## 1. Idioma

Português em nomes, comentários, mensagens de erro e documentação.

Ficam em inglês as siglas técnicas consagradas, porque traduzi-las esconde a
referência à literatura: `epoch`, `commit`, `log`, `WAL`, `quorum`, `heartbeat`,
`timeout`, `snapshot`.

**Identificadores não levam acentos.** O Python aceita `transferência`, mas isso
quebra o `grep`, obriga a teclado configurado e torna a demonstração em três
laptops diferentes um problema desnecessário. Escreve-se `transferencia` no
código e "transferência" em todo o texto visível: docstrings, mensagens, log, CLI
e painel.

```python
def aplicar_transferencia(de: str, para: str, valor_centavos: int) -> None:
    """Move o valor entre as duas contas numa única operação atómica."""
```

## 2. Nomes

| Elemento | Forma | Exemplo |
|---|---|---|
| Módulo e ficheiro | `snake_case` | `replicacao.py` |
| Função e variável | `snake_case` | `indice_commit` |
| Classe | `PascalCase` | `EntradaDeLog` |
| Constante | `MAIUSCULAS` | `HEARTBEAT_MS` |
| Teste | `teste_` + o que deve acontecer | `teste_saque_maior_que_saldo_e_recusado()` |

Valores monetários trazem sempre a unidade no nome: `valor_centavos`,
`saldo_centavos`. Nunca `valor` sozinho. Quem lê `if valor > 100` não sabe se são
cem reais ou um real, e é assim que se perde uma tarde.

## 3. Estrutura

```
prototipo-N/
├── banco/
│   ├── dominio/         contas, dinheiro, operações   <- sem rede, sem disco
│   ├── persistencia/    WAL, recuperação
│   ├── cluster/         replicação, eleição, concorrência
│   ├── interface/       servidor HTTP, rotas, painel
│   ├── servidor.py      arranque do nó
│   └── cli.py           cliente de linha de comando
├── tests/
├── config/
└── README.md
```

**A regra de dependência é uma só e não se negoceia:** `dominio/` não importa nada
de rede nem de disco. As setas apontam sempre para dentro —
`interface → cluster → dominio` e `cluster → persistencia → dominio`.

É essa pureza que faz a replicação funcionar: a mesma sequência de entradas produz
o mesmo estado em qualquer nó. No dia em que o domínio abrir um ficheiro, deixa de
ser verdade e o sistema deixa de ter garantia nenhuma.

Um módulo que passe de ~250 linhas está a fazer duas coisas. Divide-se.

## 4. Formatação

- 4 espaços. Nunca tabulações.
- Linhas até 90 colunas.
- *Type hints* em toda função pública.
- `@dataclass` para estruturas de dados; nada de dicionários soltos a atravessar
  camadas.
- Importações em três blocos: biblioteca padrão, depois módulos do projeto.
  Não há terceiro bloco — o projeto não tem dependências externas.

**Docstrings explicam o porquê, não o quê.** A assinatura já diz o quê.

```python
# inútil — repete a assinatura
def gravar(entrada: EntradaDeLog) -> None:
    """Grava a entrada."""

# útil — diz o que não se vê no código
def gravar(entrada: EntradaDeLog) -> None:
    """Grava e faz fsync antes de devolver.

    O fsync tem de acontecer antes do ACK: confirmar ao cliente uma operação
    que ainda está na cache do sistema operativo quebra RNF-02 exatamente no
    cenário que os testes exercitam.
    """
```

Comentário só onde o código surpreende. Se um comentário explica *o que* a linha
faz, a linha precisa de um nome melhor, não de um comentário.

## 5. Erros

Uma hierarquia com raiz única, para que as rotas HTTP traduzam tudo num sítio só.

```python
class ErroDoBanco(Exception):
    codigo: str = "erro_interno"
    estado_http: int = 500

class SaldoInsuficiente(ErroDoBanco):
    codigo = "saldo_insuficiente"
    estado_http = 422
```

- **Nunca** `except Exception: pass`. Um erro engolido durante a replicação passa a
  dinheiro desaparecido três passos à frente, e a origem já não está no rasto.
- Apanhar a exceção mais específica que existir.
- Validar cedo, na fronteira. O domínio recebe dados já válidos.
- A mensagem descreve o estado concreto, com os números: `"alice tem R$ 120,00 e a
  transferência pede R$ 500,00"`, não `"operação inválida"`.

## 6. Testes

`tests/unitarios/` para lógica pura, sem rede nem disco — devem correr em
milissegundos. `tests/integracao/` para processos reais a falar por HTTP.

- Um teste verifica **uma** afirmação. O nome diz qual.
- Três blocos separados por linha em branco: preparar, executar, verificar.
- Sem `sleep` de valor arbitrário. Espera-se por uma condição com um limite de
  tempo — `sleep(2)` passa na máquina de quem escreveu e falha na do colega.
- Nada de aleatoriedade sem semente, por RNF-06.

O teste que não pode faltar em nenhuma etapa: sortear milhares de operações,
aplicá-las, e verificar que a soma dos saldos não mudou.

---

# Parte II — Interface

```
Quem      Alguém de pé à frente de 2 ou 3 laptops, a projetar o ecrã durante a
          defesa. Acabou de matar o primário.
O que     Provar, ao vivo, que um servidor caiu e o dinheiro não se perdeu.
Sensação  Extrato de banco e instrumento de bordo ao mesmo tempo: sóbrio,
          espaçado, com um número que não se mexe.
```

**O painel é observado, não usado.** Ninguém clica, ninguém passa o rato por cima,
ninguém o lê sentado. É lido do fundo de uma sala, de relance, enquanto a pessoa
fala. Todas as decisões abaixo saem daí.

## 7. Princípios

### 7.1 Cor significa desvio

Um cluster saudável é **azul e branco**, sem mais cor nenhuma. Verde, âmbar e coral
só aparecem quando algo saiu do normal.

A tentação é o semáforo: uma luz verde por nó quando está tudo bem. Rejeita-se
porque, num ecrã projetado, uma mancha de cor é o que chama o olho — e se o verde
estiver sempre lá, o instante em que um nó cai perde-se no ruído. Um ecrã calmo faz
a falha gritar sozinha.

O verde tem uma única utilização em todo o sistema: o carimbo de **confirmado** ao
lado de uma operação que já passou pela maioria. É o comprovativo, não o estado.

### 7.2 O número que não se mexe

O total em circulação ocupa o topo do painel sozinho, em corpo muito maior do que
tudo o resto, e é **o único elemento da página que nunca anima**. Os nós trocam de
papel, o `epoch` incrementa, os índices sobem — o total fica quieto.

Ao lado dele, um cronómetro: `inalterado há 4 min 12 s`. Continua a contar através
do failover. Se o total alguma vez mudar, o cronómetro vai a zero e o cartão passa
a coral.

É a tese do projeto transformada em elemento de interface: o indicador de falha é
construído a partir da **ausência** de mudança. Nenhum outro produto precisaria
deste componente.

### 7.3 Faixa de mandatos

Uma banda horizontal com os `epoch` por que o cluster passou e quem mandou em cada
um — como uma tira de mandatos:

```
  epoch 5      epoch 6      epoch 7
  ├── A ──────┼── B ───────┼── B ─────▶
     4m 12s      0,8s         agora
```

Durante a demonstração, o failover aparece como um segmento novo. A evidência do
failover é apresentada como **história**, não como uma luz de estado — porque o que
interessa provar é que houve uma sucessão ordenada, não que agora está tudo bem.

### 7.4 Sem navegação

Não há barra lateral nem menu. Não há para onde ir: é um ecrã só, e todo o espaço
vertical é conteúdo. Uma barra lateral aqui seria mobília a ocupar um terço do
projetor sem levar ninguém a lado nenhum.

## 8. Painel web

Um só ficheiro HTML com CSS embutido, servido pelo próprio nó em `/painel`. Sem
framework, sem *build*, sem Node, sem tipos de letra externos — coerente com a
regra de não haver dependências. Atualiza por `fetch` a `/admin/metricas` a cada
segundo; sem JavaScript, mostra na mesma o estado do momento em que foi carregado.

**Modo claro apenas.** Fundo escuro projeta-se mal numa sala com luz acesa, e a
referência do Nubank é uma aplicação clara. Não há alternador de tema.

### 8.1 Cores

Os nomes das variáveis vêm do mundo do produto, não de uma escala genérica.

```css
:root {
  --marca:         #1B4DB1;   /* identidade */
  --marca-tenue:   #E8EEFB;   /* fundo do cartão do total */
  --papel:         #FFFFFF;   /* superfície dos cartões */
  --papel-fundo:   #F4F6FB;   /* chão da página, com o mesmo matiz da marca */
  --tinta:         #191919;   /* texto principal */
  --tinta-media:   #5C5C66;   /* texto de apoio */
  --tinta-fraca:   #8E8E99;   /* metadados, unidades, legendas */
  --fio:           rgba(25, 25, 25, 0.08);   /* separação */
  --fio-forte:     rgba(25, 25, 25, 0.14);   /* ênfase */

  --carimbo:       #00875A;   /* só no comprovativo de confirmado */
  --atencao:       #8A5300;   /* réplica atrasada — texto */
  --atencao-tenue: #FDF3E0;   /* réplica atrasada — fundo */
  --fora-do-ar:    #C4314B;   /* nó inacessível — texto */
  --fora-tenue:    #FDECEF;   /* nó inacessível — fundo */
}
```

Um só matiz estrutura a página: o chão, os cartões e o fundo do total são o mesmo
azul em lightness diferente. As superfícies não mudam de cor, mudam de claridade.

**Porquê azul, e não o roxo da referência.** A linguagem visual é a do Nubank; a cor
não pode ser, ou é a marca de outra empresa num trabalho que não é dela. Dos matizes
disponíveis, o azul é o único que sobra limpo: o verde já é `--carimbo`, o âmbar é
`--atencao` e o coral é `--fora-do-ar`. Uma marca verde-azulada competiria com o
carimbo de confirmado justamente no ecrã em que ele importa. `--marca` sobre
`--papel` dá 7,1:1, bem acima do 4.5:1 exigido.

Os tons de estado existem em par — texto escuro sobre fundo muito claro — porque o
âmbar e o coral saturados falham o contraste AA sobre branco. Todo o texto cumpre
4.5:1.

### 8.2 Tipografia

```css
font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
font-variant-numeric: tabular-nums;
```

Tipo de letra do sistema, sem descarregar nada.

`tabular-nums` em **todos** os números, sem exceção. A página atualiza a cada
segundo; sem largura fixa de dígito, o total treme a cada refrescamento e a
quietude — que é o ponto — desfaz-se.

| Papel | Tamanho | Peso | Espaçamento |
|---|---|---|---|
| Total em circulação | 72 px | 300 | −0,03em |
| Título de secção | 20 px | 600 | −0,01em |
| Valor num cartão de nó | 28 px | 400 | normal |
| Texto corrente | 15 px | 400 | normal |
| Rótulo e metadado | 13 px | 500 | 0,01em |

O total é grande **e leve**. Peso 300 a 72 px lê-se do fundo da sala sem gritar; a
mesma dimensão a 700 seria uma barra preta a atravessar o ecrã.

### 8.3 Espaço, forma e profundidade

- Base 4 px. Escala: 4, 8, 16, 24, 40, 64. Nada fora dela.
- Raio: 12 px em elementos pequenos, 16 px em cartões, 999 px em pastilhas.
- **Profundidade por sombra suave, e só por sombra.** Não se misturam estratégias:
  os cartões não levam contorno.

```css
--sombra-cartao: 0 1px 2px rgba(25, 25, 25, .04),
                 0 4px 16px rgba(25, 25, 25, .04);
```

Sombras a esta intensidade não se veem isoladas; sente-se que o cartão está
pousado no papel. Se a sombra se nota, está forte de mais.

O padding é simétrico: 24 px nos cartões, 40 px na margem da página.

### 8.4 Cartão de nó

Cada nó é um **cartão de extrato**, não um ponto colorido. Diz o papel por palavras
e mostra o atraso em entradas, que é a informação de que alguém precisa a meio de
uma falha:

```
┌──────────────────────────────────────┐
│  nó B                    192.168.0.12│
│                                      │
│  primário                            │
│  desde o epoch 7 · há 12 s           │
│                                      │
│  índice 142     commit 142           │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│  nó C                    192.168.0.12│   fundo --atencao-tenue
│                                      │
│  réplica · 2 entradas atrás          │
│  último contacto há 0,4 s            │
│                                      │
│  índice 140     commit 140           │
└──────────────────────────────────────┘
```

"2 entradas atrás" diz o tamanho do problema. Uma luz amarela só diz que existe um.

### 8.5 Estados

Nenhum ecrã de dados está completo sem eles:

- **A carregar** — o esqueleto dos cartões em `--papel-fundo`, sem texto. Nunca um
  *spinner*: ele mexe-se, e a página inteira foi desenhada à volta de quase nada
  se mexer.
- **Sem quórum** — uma barra no topo, `--fora-tenue`: `sem maioria — o cluster
  está em somente leitura`. O total continua visível, porque continua correto.
- **Painel sem contacto com o nó** — o total esbate-se para `--tinta-fraca` e
  aparece `última leitura há 8 s`. Nunca se mostra um número velho como se fosse
  atual.

## 9. Linha de comando

Mesma pessoa, mesma sala, mesmo princípio: **cor significa desvio**. A saída normal
não tem cor nenhuma.

### 9.1 Dinheiro

Sempre `R$ 1.234,56` — ponto nos milhares, vírgula nos decimais, como em português.
Nas tabelas, alinhado à direita, para as ordens de grandeza se compararem à vista.

### 9.2 Tabelas

Duas colunas de espaço entre campos, cabeçalho em maiúsculas discretas, sem
molduras ASCII. Uma moldura ocupa metade da largura a desenhar caixas.

```
$ python3 -m banco.cli estado

  NÓ   PAPEL      EPOCH   ÍNDICE   COMMIT
  A    réplica        7      142      142
  B    primário       7      142      142
  C    réplica        7      140      140   2 atrás

  total em circulação   R$ 12.400,00
```

### 9.3 Cor

Só através de ANSI, e **só quando `sys.stdout.isatty()`**. Redirecionar para um
ficheiro tem de dar texto limpo — os registos da demonstração vão para o relatório,
e sequências de escape tornam-nos ilegíveis.

| Uso | Cor |
|---|---|
| Erro | vermelho |
| Aviso, atraso | amarelo |
| Confirmado | verde |
| Tudo o resto | sem cor |

### 9.4 Erros

Três linhas: o que aconteceu, com os números concretos, e o que fazer a seguir.

```
$ python3 -m banco.cli transferir alice bob 500.00

  erro: saldo insuficiente
  alice tem R$ 120,00 e a transferência pede R$ 500,00
  → tente um valor até R$ 120,00
```

```
$ python3 -m banco.cli transferir alice bob 25.00

  erro: sem maioria no cluster
  só o nó A respondeu; são precisos 2 dos 3
  → confirme que B e C estão a correr: python3 -m banco.cli estado
```

A terceira linha é obrigatória. Um erro que não diz o passo seguinte deixa quem o
lê exatamente onde estava.

### 9.5 Códigos de saída

| Código | Significado |
|---|---|
| 0 | Correu bem |
| 1 | O banco recusou por regra — saldo insuficiente, conta inexistente |
| 2 | Uso incorreto do comando |
| 3 | O cluster não respondeu |

O 1 e o 3 têm de ser distintos: os testes precisam de separar "o banco disse não,
e bem" de "o banco está em baixo". Colapsá-los faz um teste de falha passar por
motivo errado.

### 9.6 Sem barras de progresso

Nada de *spinners* nem de percentagens. Enchem a saída redirecionada de lixo e não
informam: as operações ou demoram milissegundos, ou falharam.

## 10. Log estruturado

Uma linha JSON por evento, em `dados/<id>/servidor.log`. Vocabulário fechado — um
evento novo acrescenta-se a esta tabela, não se inventa no ponto de uso, senão o
`grep` deixa de servir para alguma coisa.

```json
{"instante": 1756742400.12, "no": "A", "epoch": 7, "evento": "entrada_confirmada",
 "indice": 142, "op_id": "3f1c8a2e", "duracao_ms": 11.4}
```

| Evento | Quando |
|---|---|
| `no_iniciado` | Fim da recuperação, o nó entra no cluster |
| `entrada_gravada` | Escrita no WAL com `fsync` feito |
| `entrada_confirmada` | A maioria confirmou |
| `sem_quorum` | A maioria não respondeu a tempo |
| `heartbeat_perdido` | Passou o *timeout* sem contacto do primário |
| `eleicao_iniciada` | O nó candidatou-se, com o novo `epoch` |
| `voto_concedido` / `voto_negado` | Resposta a um pedido de voto, com o motivo |
| `primario_assumido` | Ganhou a eleição |
| `primario_despromovido` | Viu um `epoch` maior |
| `replica_sincronizada` | Uma réplica atrasada pôs-se em dia |
| `falha_injetada` | Alguém chamou `/admin/falha` |

`voto_negado` traz sempre o motivo — qual das três condições da secção 8.2 do
[`SPECS.md`](SPECS.md) falhou. Sem isso, depurar uma eleição que não converge é
adivinhar.

---

## 11. Commits e ramos

- Mensagem em português, no imperativo: `Adiciona confirmação por maioria`.
- Assunto até 72 caracteres, sem ponto final.
- O corpo explica **porquê**; o *diff* já mostra o quê.
- Sem *trailers*, sem assinaturas, sem emoji.
- Um commit por ideia.
- Ramos: `etapa/prototipo-2`, `modulo/replicacao`, `correcao/eleicao-sem-convergir`.
