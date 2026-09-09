---
title: "Um banco que não perde dinheiro"
subtitle: "Transferências entre servidores distintos sem contas descasadas"
date: "Agosto de 2026"
---

# Identificação

**Universidade de São Paulo (USP)**

**Instituto de Ciências Matemáticas e de Computação (ICMC)**

Campus São Carlos, São Paulo, Brasil

Área: Computação Distribuída

## Integrantes

| Número USP | Nome completo |
|-----------------------|-----------------------------------------------------------------------------|
| 18404636 | Jefferson Daniel Flores Montenegro |
| 18514632 | Cristhian Jesus Maylle Briceño |
| 17819748 | Paulo Sebastian Rojo Pinedo |

# Descrição do projeto

O projeto implementa um sistema bancário distribuído em que as contas dos clientes ficam armazenadas em servidores diferentes, e cada servidor é replicado para sobreviver a falhas.

A regra que o sistema nunca pode violar é simples: o dinheiro não é criado nem destruído. Se um cliente transfere R$ 100 para outro, e as duas contas estão em servidores distintos, ou as duas mudam, ou nenhuma muda. Isso vale mesmo quando um servidor cai no meio da operação ou quando a rede se parte.

# Funcionalidades

| ID | Funcionalidade |
|-------|-----------------------------------------------------------------------------------------------|
| F-01 | Criar conta com identificador e saldo inicial |
| F-02 | Consultar saldo de uma conta |
| F-03 | Depositar e sacar valores em uma conta |
| F-04 | Transferir valores entre duas contas, inclusive em servidores diferentes |
| F-05 | Consultar o extrato de operações de uma conta |
| F-06 | Auditar o sistema somando todos os saldos e comparando com o total esperado |
| F-07 | Executar operações concorrentes de vários clientes ao mesmo tempo |
| F-08 | Continuar funcionando com servidores fora do ar |
| F-09 | Recuperar o estado automaticamente após reinício de um servidor |
| F-10 | Injetar falhas para teste: derrubar servidor, isolar da rede, atrasar mensagens |
| F-11 | Visualizar o estado do sistema: servidores ativos, líder de cada grupo, métricas |
| F-12 | Cliente de linha de comando para executar todas as operações |

# Requisitos funcionais

| ID | Requisito | Prioridade |
|--------|-------------------------------------------------------------------------------------|-------------|
| RF-01 | O sistema deve permitir criar contas com saldo inicial definido | Alta |
| RF-02 | O sistema deve permitir consultar o saldo de qualquer conta | Alta |
| RF-03 | O sistema deve permitir depósito e saque em uma conta | Alta |
| RF-04 | O sistema deve permitir transferência entre contas em servidores diferentes | Alta |
| RF-05 | Uma transferência deve ser atômica: ou os dois lados são aplicados, ou nenhum | Alta |
| RF-06 | O sistema deve rejeitar transferências que deixariam o saldo negativo | Alta |
| RF-07 | Uma leitura deve enxergar um estado consistente, sem misturar operações | Alta |
| RF-08 | Operações concorrentes sobre a mesma conta devem entrar em conflito e uma delas abortar | Alta |
| RF-09 | Cada grupo de servidores deve eleger um líder responsável pelas escritas | Alta |
| RF-10 | Uma escrita só é confirmada ao cliente após ser replicada na maioria das cópias | Alta |
| RF-11 | O sistema deve continuar atendendo com um servidor fora do ar por grupo | Alta |
| RF-12 | Um servidor reiniciado deve recuperar seu estado e voltar a participar do grupo | Alta |
| RF-13 | Operações interrompidas por falha do cliente devem ser resolvidas automaticamente | Alta |
| RF-14 | O sistema deve oferecer uma auditoria do total de dinheiro em circulação | Alta |
| RF-15 | O sistema deve expor métricas de desempenho e estado do cluster | Média |
| RF-16 | O sistema deve permitir injetar falhas durante a execução para fins de teste | Média |
| RF-17 | O cliente de linha de comando deve dar acesso a todas as operações | Média |
| RF-18 | O sistema deve permitir adicionar e remover servidores de um grupo | Baixa |

# Requisitos não funcionais

| ID | Requisito | Critério de aceitação |
|---------|----------------------|-----------------------------------------------------------------------|
| RNF-01 | Corretude sob falhas | O total de dinheiro nunca muda, em nenhum teste |
| RNF-02 | Durabilidade | Operação confirmada sobrevive à queda de servidores |
| RNF-03 | Disponibilidade | Novo líder eleito em menos de 2 segundos |
| RNF-04 | Desempenho | Ao menos 500 transações por segundo no ambiente local |
| RNF-05 | Latência | Transferência com p99 abaixo de 200 ms sem falhas |
| RNF-06 | Testes reproduzíveis | Mesma semente de execução produz o mesmo resultado |
| RNF-07 | Observabilidade | Log estruturado e métricas em todos os componentes |
| RNF-08 | Modularidade | Cada componente com código, testes e documentação próprios |
| RNF-09 | Portabilidade | Execução com um único comando em Linux e macOS |
| RNF-10 | Documentação | Cada componente documenta seu funcionamento e seus modos de falha |

# Restrições

- O sistema assume que os servidores podem parar ou ficar lentos, mas não se comportam de forma maliciosa.
- O consenso e o protocolo de transações são implementados do zero, sem bibliotecas prontas para essas funções.
- A distribuição das contas entre os servidores é definida na inicialização e não muda durante a execução.
- Não fazem parte do escopo: autenticação de usuários, criptografia, interface gráfica web e replicação entre regiões geográficas distintas.
