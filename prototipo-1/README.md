# Protótipo 1 — Um banco correto num só nó

Primeira das três entregas do [Banco Distribuído](../README.md).

**Estado:** não iniciada. As caixas por marcar estão no
[`ROADMAP.md`](../docs/ROADMAP.md#etapa-1--protótipo-1).

---

## Objetivo

Um banco que funciona num só servidor e cujas contas estão sempre certas: o
dinheiro não é criado nem destruído, o saldo nunca fica negativo, operações
concorrentes não se atropelam e o estado sobrevive a um reinício.

Ainda não há rede entre servidores, replicação nem eleição.

**Porque é que esta etapa existe antes da parte distribuída:** um erro de
arredondamento no dinheiro, ou uma corrida entre duas *threads* que passe
despercebida aqui, vai manifestar-se na etapa 2 como um saldo errado depois de um
failover — e vai parecer um erro de replicação. Procurar-se-ia no protocolo durante
dias por causa de um `float`.

---

## O que fica pronto

- Criar conta, consultar saldo, depositar, sacar, transferir, extrato
- Auditoria: soma de todos os saldos
- Dinheiro em centavos inteiros, nunca `float`
- WAL append-only com `fsync`, e recuperação do estado por *replay* no arranque
- Deduplicação por `op_id`, para a retentativa do cliente ser segura
- *Locks* por conta em ordem total, sem *deadlock*
- Servidor HTTP e cliente de linha de comando

**Requisitos cobertos:** F-01 a F-07, F-12 · RF-01 a RF-08, RF-14, RF-17 ·
RNF-01, RNF-09

---

## Como executar

```bash
cd prototipo-1

python3 -m banco.servidor --id A --porta 8001

python3 -m banco.cli criar-conta alice --saldo 100.00
python3 -m banco.cli criar-conta bob --saldo 0.00
python3 -m banco.cli transferir alice bob 25.00
python3 -m banco.cli extrato alice
python3 -m banco.cli auditoria

python3 -m pytest -q
```

Sem instalação e sem dependências: só a biblioteca padrão do Python 3.10+.

Para verificar a recuperação, matar o processo do servidor, voltar a arrancá-lo e
correr `auditoria` — o total tem de ser o mesmo.

---

## Divisão do trabalho

| Pessoa | Responsabilidade nesta etapa |
|---|---|
| **Jefferson Daniel Flores Montenegro** | **Domínio e persistência.** Dinheiro em centavos e formatação em reais, contas e validação, as quatro operações como funções puras, invariante da soma, extrato, auditoria. WAL com `fsync`, recuperação por *replay*, linha truncada, deduplicação por `op_id`. |
| **Cristhian Jesus Maylle Briceño** | **Concorrência.** *Locks* por conta adquiridos em ordem crescente de id, `lock` de estado por nó, ordem obrigatória de uma escrita. Testes de corrida, de *deadlock* cruzado e de leitura consistente. |
| **Paulo Sebastian Rojo Pinedo** | **Interface.** Servidor HTTP sobre `ThreadingHTTPServer`, encaminhamento de rotas, tradução uniforme de erros para JSON. Cliente de linha de comando com todos os comandos, formatação de tabelas e de dinheiro, cores só em terminal, códigos de saída. Fundação do repositório e configuração dos testes. |

Cada pessoa escreve os testes do seu próprio módulo. O README e a documentação da
etapa são revistos pelos três; o dono desta etapa é o **Jefferson**, por ser quem
tem o domínio e a persistência, que é onde está o essencial.

---

## Modos de falha conhecidos

*A preencher durante a etapa (RNF-10): o que acontece com o disco cheio, com o
processo morto a meio de uma escrita no WAL, e com um pedido malformado.*

---

## Resultados

*A preencher no fecho da etapa: número de testes a passar e o que ficou por fazer.*
