# Protótipo 1 — um banco correto num só nó

Trabalho de Computação Distribuída — USP/ICMC, São Carlos.

**O que esta etapa faz, numa frase:** um banco com contas, depósitos, saques,
transferências, extrato e auditoria, onde o dinheiro nunca é criado nem
destruído — nem sequer quando vinte pedidos chegam à mesma conta ao mesmo
tempo.

**Estado: 97 testes passam.** 55 correm sem instalar nada; os outros 42 pedem a
pilha do servidor e uma base de dados, e saltam-se sozinhos com o motivo
escrito quando não as há.

Não há replicação, eleição de primário nem tolerância a falhas. É deliberado: o
dinheiro tem de estar certo **antes** de ser distribuído. Uma corrida entre dois
pedidos que passe despercebida aqui vai parecer, na etapa seguinte, um erro de
replicação — e procurar-se-á no sítio errado durante dias.

---

## Como executar

### Tudo de uma vez

```bash
docker compose up --build
```

Painel em <http://localhost:8080>, API em <http://localhost:8001>.

### Os testes

```bash
# Numa máquina limpa: 55 testes do domínio, sem instalar nada.
python3 -m unittest discover -s tests

# Com a pilha e uma base descartável: os 97.
pip install -r requisitos.txt
createdb banco_teste
BANCO_BD_TESTE=postgresql:///banco_teste python3 -m unittest discover -s tests
```

A base de teste é apagada no início de cada teste, e por isso o código recusa-se
a trabalhar numa base cujo nome não contenha `teste`.

### Só o nó, contra um PostgreSQL já a correr

```bash
pip install -r requisitos.txt
createdb banco && psql banco -f db/esquema.sql
BANCO_BD=postgresql:///banco python3 -m banco.servidor --id A --porta 8001
```

### Um exemplo completo

```bash
curl -X POST localhost:8001/contas -H 'Content-Type: application/json' \
     -d '{"conta":"alice","saldo_inicial":"100.00","op_id":"exemplo-01"}'
curl -X POST localhost:8001/contas -H 'Content-Type: application/json' \
     -d '{"conta":"bob","op_id":"exemplo-02"}'
curl -X POST localhost:8001/transferencias -H 'Content-Type: application/json' \
     -d '{"de":"alice","para":"bob","valor":"25.50","op_id":"exemplo-03"}'
curl localhost:8001/auditoria
```

O dinheiro viaja como **texto**: `"25.50"`, nunca `25.50`. Um número JSON seria
descodificado como `float`, e um `float` em dinheiro é a origem do desvio de
arredondamento que RNF-01 proíbe. Um número é recusado com `400 valor_invalido`.

O `op_id` é gerado **pelo cliente**. É o que torna seguro repetir um pedido de
que não se sabe o desfecho: se a primeira tentativa chegou a ser aplicada, a
segunda devolve o resultado guardado em vez de mover o dinheiro outra vez.

---

## Rotas

| Rota | Método | O que faz |
|---|---|---|
| `/contas` | POST | Cria uma conta (RF-01) |
| `/contas/{id}` | GET | Saldo (RF-02) |
| `/contas/{id}/deposito` | POST | Depósito (RF-03) |
| `/contas/{id}/saque` | POST | Saque (RF-03, RF-06) |
| `/transferencias` | POST | Transferência (RF-04, RF-05) |
| `/contas/{id}/extrato` | GET | Extrato (F-05) |
| `/auditoria` | GET | Total em circulação (RF-14) |
| `/saude` | GET | O processo está de pé |

Os erros têm todos a mesma forma, e por isso o cliente tem um só caminho de
tratamento:

```json
{"erro": "saldo_insuficiente",
 "mensagem": "alice tem R$ 120,00 e a operação pede R$ 500,00"}
```

`valor_invalido` 400 · `conta_inexistente` 404 · `conta_duplicada` 409 ·
`saldo_insuficiente` 422.

---

## Como está organizado

```
banco/
├── dominio/       as regras, puras: sem rede e sem disco
├── repositorio/   o SQL, e só o SQL
├── servico/       a ordem obrigatória de escrita, e as leituras
├── api/           as rotas HTTP e a tradução dos erros
└── servidor.py    o arranque do nó
```

As setas apontam sempre para dentro: `api → servico → {dominio, repositorio}`.
O domínio não importa nada de rede nem de disco, e é isso que permite testá-lo
sem instalar nada.

**Toda a escrita passa por uma função**, `ServicoDeEscrita.aplicar()`. As quatro
operações são a mesma sequência de passos com um objeto diferente lá dentro, e
escrevê-la quatro vezes seria dar-lhe quatro sítios para divergir.

---

## As três decisões que sustentam a invariante

**1. Dinheiro é inteiro de centavos.** Nunca `float`, em lado nenhum. A
conversão a partir de texto acontece uma única vez, na fronteira. Somar dez mil
valores em vírgula flutuante desvia-se por arredondamento, e o teste da
invariante falharia a apontar para o sítio errado.

**2. A transferência é uma só função, sem estado intermédio.** Não existe
instante nenhum em que o dinheiro tenha saído de uma conta e ainda não tenha
entrado na outra. Não há commit em duas fases porque não é preciso: as duas
contas estão sempre no mesmo nó.

**3. As contas são bloqueadas por ordem crescente de id.** A ordem nasce em
`Operacao.contas_tocadas()`, que já devolve os ids ordenados, e quem bloqueia
percorre a tupla e pronto — não tem de se lembrar da regra, e por isso não a
pode esquecer. É o que torna impossível o impasse de `alice→bob` contra
`bob→alice`.

---

## Requisitos cobertos

| | |
|---|---|
| **Cobertos** | F-01 a F-07 · RF-01 a RF-08, RF-14 · RNF-01, RNF-08, RNF-10 |
| **Parcial** | RNF-09 (um comando, sim: `docker compose up`. Mas sem instalar nada, só os 55 testes do domínio) |
| **Fora desta etapa** | F-08 a F-11 · RF-09 a RF-13, RF-16 · RNF-02, RNF-03, RNF-06 — replicação, eleição e failover são das etapas seguintes |
| **Não cobertos em lado nenhum** | F-12 e RF-17, o cliente de linha de comando. Ver "o que mudou", abaixo |

RF-04 fala em contas "em servidores diferentes". Aqui só há um servidor, por isso
está coberto no sentido de um nó só. Por desenho, todos os nós guardam todas as
contas (SPECS 1), e é por isso que a transferência continuará a ser local ao
primário quando houver três.

---

## O que mudou face à etapa entregue

Esta pasta foi reconstruída a partir de `projeto-final/`, para voltar a ser o que
a divisão em etapas precisa que ela seja: um banco de um nó só, a funcionar
isolado. O que lá estava antes — PostgreSQL como log replicado, eleição,
failover, injeção de falhas e um painel de cluster — era trabalho das etapas 2 e
3 a viver na pasta da etapa 1.

| Antes (`git show 3683a0f`) | Agora |
|---|---|
| `http.server` da biblioteca padrão | FastAPI e uvicorn |
| WAL em JSONL, com PostgreSQL como armazém do log | PostgreSQL como estado, em duas tabelas |
| `dominio`, `persistencia`, `cluster`, `interface` | `dominio`, `repositorio`, `servico`, `api` |
| Locks em memória, por conta | `SELECT ... FOR UPDATE`, por conta |
| Replicação, eleição, failover, injeção de falhas | Nada disso: é de outra etapa |
| Cliente de linha de comando | Painel web |
| 305 testes | 97 testes |

**Quatro defeitos do projeto final que não vieram atrás**, todos encontrados a
portar o código:

1. `guardar` de contas era um *upsert*. Com o id a vir do cliente, criar a conta
   `alice` outra vez passava a ser um comando que **repõe o saldo da alice**.
2. Não havia `FOR UPDATE`. Vinte saques simultâneos de R$ 1,00 numa conta com
   R$ 10,00 passavam os vinte.
3. `para_centavos` fazia `str(texto)` antes de validar, e por isso aceitava em
   silêncio o número `25.00` que SPECS 6 manda recusar.
4. A auditoria devolvia `Decimal`, porque `SUM()` sobre `BIGINT` devolve
   `numeric` — um valor que ia acabar em vírgula flutuante ao ser serializado.

**O que se perdeu, dito sem rodeios:** o cliente de linha de comando (F-12,
RF-17) deixa de existir no repositório inteiro — `projeto-final/` também não
tem. Quem quiser vê-lo tem de ir a `git show 7b430e6`. A replicação, a eleição
e o failover, que existiam nesta pasta, também deixaram de existir em qualquer
sítio: `projeto-final/` tem o `cluster/` por escrever e `prototipo-2/` está
vazia. Estão em `git show 3683a0f`.

---

## Modos de falha conhecidos (RNF-10)

| Situação | O que acontece | Porquê |
|---|---|---|
| O nó morre a meio de uma transferência | Nada se perde e nada fica a meio | A transação do PostgreSQL ou confirma tudo ou reverte tudo |
| O nó morre | O banco fica fora do ar até voltar | Há um nó só. É a etapa 2 que resolve isto |
| O PostgreSQL fica inacessível | Todas as rotas devolvem 500 | Não há repetição automática nem modo degradado |
| Duas criações **simultâneas** da mesma conta com o mesmo `op_id` | Uma responde 409 em vez de devolver o resultado guardado | Uma conta que ainda não existe não tem linha para bloquear, por isso as duas passam a validação e a chave primária decide. O dinheiro fica correto; só a resposta é que é feia |
| Um pedido demora mais de 5 s a obter um lock | 500, em vez de ficar à espera para sempre | `lock_timeout`. Com a ordem total dos locks isto nunca devia acontecer; existe para um erro futuro aparecer como erro e não como suite pendurada |
| Uma transação é revertida | O número da operação seguinte salta | Uma sequência não volta atrás. O número serve para ordenar, não para contar |
| Dinheiro enviado como número JSON | 400 `valor_invalido` | É um modo de falha desejado: ver a decisão 1 |

**Não há cópias de segurança.** Apagar o volume do PostgreSQL apaga o banco.
`docker compose down -v` faz exatamente isso.

---

## Resultados

| | |
|---|---|
| `banco/` | 1 231 linhas em 23 ficheiros |
| `tests/` | 1 132 linhas, 97 testes |
| `frontend/src/` | 609 linhas |
| Suite completa | ~7,5 s |
| Módulo maior | `dominio/operacoes.py`, 230 linhas |

**A prova de que os testes de concorrência provam alguma coisa:** tirando a
cláusula `FOR UPDATE` de `banco/repositorio/contas.py`, seis testes falham e o
total em circulação sobe de R$ 200,00 para R$ 201,00. Foi verificado, e é o
resultado que dá sentido a todos os outros.

---

## Divisão de trabalho

| Número USP | Nome | Nesta etapa |
|---|---|---|
| 18404636 | Jefferson Daniel Flores Montenegro | Domínio: dinheiro, contas, operações e a invariante |
| 18514632 | Cristhian Jesus Maylle Briceño | Concorrência: ordem dos locks e os testes que a provam |
| 17819748 | Paulo Sebastian Rojo Pinedo | Persistência, rotas HTTP, painel web e Docker |
