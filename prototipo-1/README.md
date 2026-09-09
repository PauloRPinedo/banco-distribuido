# Protótipo 1 — Um banco correto num só nó

Primeira das três entregas do [Banco Distribuído](../README.md).

**Estado: concluída.** 103 testes passam, sem instalar nada.

---

## Objetivo

Um banco que funciona num só servidor e cujas contas estão sempre certas: o
dinheiro não é criado nem destruído, o saldo nunca fica negativo, operações
concorrentes não se atropelam e o estado sobrevive a um reinício.

Ainda não há rede entre servidores, replicação nem eleição.

**Porque é que esta etapa existe antes da parte distribuída:** um erro de
arredondamento no dinheiro, ou uma corrida entre duas *threads* que passe
despercebida aqui, vai manifestar-se na etapa 2 como um saldo errado depois de um
failover — e vai parecer um erro de replicação. Procurar-se-ia no protocolo
durante dias por causa de um `float`.

---

## O que ficou pronto

- Criar conta, consultar saldo, depositar, sacar, transferir, extrato
- Auditoria que **compara dois cálculos independentes**: a soma dos saldos e o
  total deduzido do log
- Dinheiro em centavos inteiros, nunca `float`
- WAL append-only com `fsync`, e recuperação do estado por *replay* no arranque
- Deduplicação por `op_id`, para a retentativa do cliente ser segura
- *Locks* por conta em ordem total, sem *deadlock*
- Servidor HTTP e cliente de linha de comando

**Requisitos cobertos:** F-01 a F-07, F-12 · RF-01 a RF-08, RF-14, RF-17 ·
RNF-01, RNF-09

As decisões tomadas pelo caminho e o seu porquê estão em
[`RELATORIO.md`](RELATORIO.md).

---

## Como executar

Não é preciso instalar nada. Só Python 3.10 ou mais recente.

```bash
cd prototipo-1

python3 -m banco.servidor --id A --porta 8001

python3 -m banco.cli criar-conta alice --saldo 100.00
python3 -m banco.cli criar-conta bob --saldo 0.00
python3 -m banco.cli transferir alice bob 25.00
python3 -m banco.cli extrato alice
python3 -m banco.cli auditoria
python3 -m banco.cli estado
```

```
$ python3 -m banco.cli extrato alice
  #  OPERAÇÃO       CONTRAPARTE      VALOR      SALDO
  1  criar_conta    —            R$ 100,00  R$ 100,00
  3  transferencia  bob          -R$ 25,00   R$ 75,00

$ python3 -m banco.cli transferir alice bob 500.00
  erro: saldo insuficiente
  alice tem R$ 75,00 e a operação pede R$ 500,00
  → consulte o saldo com: python3 -m banco.cli saldo <id>
```

### Testes

```bash
python3 -m unittest discover -s tests          # 103 testes
python3 -m unittest discover -s tests -v       # com o nome de cada um
```

Usa-se o `unittest` da biblioteca padrão precisamente para isto funcionar em
qualquer laptop sem `pip install`. Quem tiver o `pytest` pode usá-lo à mesma:
corre estes ficheiros sem alteração nenhuma.

### Verificar a durabilidade à mão

```bash
python3 -m banco.cli auditoria     # anotar o total
# matar o processo do servidor e voltar a arrancá-lo
python3 -m banco.cli auditoria     # o total tem de ser o mesmo
```

---

## Divisão do trabalho

| Pessoa | Responsabilidade nesta etapa |
|---|---|
| **Jefferson Daniel Flores Montenegro** | **Domínio e persistência.** `dominio/dinheiro.py`, `contas.py`, `operacoes.py`: centavos inteiros e formatação em reais, contas e validação de id, as quatro operações como funções puras, invariante da soma, extrato, auditoria. `persistencia/`: WAL com `fsync`, recuperação por *replay*, linha truncada, `estado.json`. |
| **Cristhian Jesus Maylle Briceño** | **Concorrência.** `cluster/concorrencia.py` e a ordem de escrita em `cluster/no.py`: *locks* por conta adquiridos em ordem crescente de id, `lock` de estado do nó, deduplicação por `op_id`. Testes de corrida, de *deadlock* cruzado e de leitura consistente. |
| **Paulo Sebastian Rojo Pinedo** | **Interface.** `interface/servidor_http.py` e `rotas.py`: servidor sobre `ThreadingHTTPServer`, as sete rotas de cliente, tradução uniforme de erros. `cli.py`, `interface/formato.py` e `cliente_http.py`: todos os comandos, formatação de tabelas e de dinheiro, cores só em terminal, códigos de saída. Fundação do repositório. |

Cada pessoa escreveu os testes do seu próprio módulo. A documentação foi revista
pelos três; o dono desta etapa é o **Jefferson**.

---

## Modos de falha conhecidos (RNF-10)

| Situação | O que acontece |
|---|---|
| Processo morto a meio de uma escrita no WAL | A última linha fica truncada. No arranque seguinte é descartada e o ficheiro é truncado nesse ponto. Como o `fsync` ainda não devolvera, essa operação nunca chegou a ser confirmada a ninguém |
| Processo morto **depois** do `fsync`, antes de responder | A operação está no log e é aplicada no arranque. O cliente, que não recebeu resposta, repete com o mesmo `op_id` e recebe o resultado guardado, sem mover o dinheiro outra vez |
| Disco cheio | O `fsync` levanta `OSError`, a operação não é aplicada e o cliente recebe `500 erro_interno` com o rasto no terminal do servidor. O saldo não muda. O CLI sai com 3 e diz **"não conseguiu atender"**, não "não respondeu" — a distinção importa, porque as soluções são diferentes |
| Linha corrompida no meio do WAL | O arranque falha com `WalCorrompido` em vez de aplicar um log com um buraco. Distingue-se de propósito da cauda truncada, que é normal |
| Pedido com corpo que não é JSON | `400 corpo_invalido`, sem tocar no estado |
| Valor monetário enviado como número JSON | `400 valor_invalido`. Um número seria descodificado como `float` |
| Duas transferências cruzadas em simultâneo | Serializam pela ordem total dos *locks*. Não há *deadlock*: testado com 100 threads, 20 execuções seguidas |
| Servidor em baixo quando o CLI corre | O CLI sai com o código 3, distinto do 1 de uma recusa por regra |

---

## Resultados

| | |
|---|---|
| Testes | **103**, todos a passar |
| Linhas de código | 1408 em `banco/` |
| Linhas de teste | 1226 em `tests/` |
| Duração da suíte | cerca de 8 segundos |
| Dependências externas | nenhuma |
| Módulos acima de 250 linhas | nenhum |

Os testes de concorrência foram corridos **20 vezes seguidas sem uma falha**,
como o ROADMAP exige.

O que **não** está feito nesta etapa, por ser de etapas seguintes: replicação,
quórum, eleição, failover, injeção de falhas, métricas, painel web e *benchmark*.
