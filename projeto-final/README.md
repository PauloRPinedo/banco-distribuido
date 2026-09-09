# Projeto final — Prova, mede e mostra

Terceira e última entrega do [Banco Distribuído](../README.md).

**Estado:** não iniciada. Depende do [Protótipo 2](../prototipo-2/) estar fechado.
As caixas por marcar estão no
[`ROADMAP.md`](../docs/ROADMAP.md#etapa-3--projeto-final).

---

## Objetivo

O sistema já funciona. Esta etapa serve para o **demonstrar de forma controlada**,
para o **medir com honestidade** e para o **apresentar**.

Controlada, porque até aqui as falhas eram provocadas à mão, matando processos. Com
injeção de falhas, uma partição de rede passa a ser reproduzível num teste
automático, sempre igual.

---

## O que fica pronto

- Injeção de falhas: derrubar, isolar da rede, atrasar mensagens
- Testes de *split-brain* e de partição simétrica
- Log estruturado com vocabulário fechado, e métricas
- Painel web de monitorização, servido pelo próprio nó
- *Benchmark* com vazão e latência, e a análise do estrangulamento
- Suíte completa das três etapas, determinística por semente
- Diagramas UML e documentação final

**Requisitos cobertos:** F-10, F-11 · RF-15, RF-16 · RNF-04, RNF-05, RNF-07 a RNF-10

---

## Dois pontos de honestidade

**O painel web é um desvio à proposta.** A proposta exclui "interface gráfica web"
do âmbito. O painel acrescenta-se com dois limites que o mantêm coerente com essa
restrição: é **só de leitura** e é de **monitorização**, não de operação bancária.
Existe para cumprir F-11 de forma demonstrável, e todas as operações continuam a
passar pelo CLI.

**RNF-04 é tratado como meta de medição, não como requisito bloqueante.** Uma
implementação anterior deste mesmo desenho saturou perto de 270 transações por
segundo, e as hipóteses de estrangulamento testadas — `fsync`, contenção de
*locks*, serialização, CPU — foram todas descartadas: o tempo estava em espera, não
em trabalho. O que se entrega é o número medido e a análise. Relatar a medição real
vale mais do que ajustar o requisito para que ele pareça cumprido.

Ambos os desvios estão justificados na secção 11 do [`SPECS.md`](../docs/SPECS.md).

---

## Como executar

```bash
cd projeto-final
cp config/cluster.exemplo.json config/cluster.json

python3 -m banco.servidor --id A --config config/cluster.json &
python3 -m banco.servidor --id B --config config/cluster.json &
python3 -m banco.servidor --id C --config config/cluster.json &
```

**Painel:** abrir `http://<endereço-de-um-nó>:8001/painel`. Mostra o total em
circulação, quem é o primário, o `epoch` e o estado de cada nó. Atualiza sozinho.

**Injetar falhas:**

```bash
# atrasar todas as respostas de um nó em 300 ms
curl -X POST http://192.168.0.11:8001/admin/falha \
     -d '{"tipo": "atraso", "ms": 300}'

# isolar o nó A dos nós B e C, sem mexer na firewall
curl -X POST http://192.168.0.11:8001/admin/falha \
     -d '{"tipo": "isolar", "de": ["B", "C"]}'

curl -X POST http://192.168.0.11:8001/admin/falha -d '{"tipo": "limpar"}'
```

**Medir:**

```bash
python3 -m banco.bench --clientes 1,2,4,8,16,32
python3 -m unittest discover -s tests
```

---

## Divisão do trabalho

| Pessoa | Responsabilidade nesta etapa |
|---|---|
| **Cristhian Jesus Maylle Briceño** | **Falhas controladas.** `POST /admin/falha` com atraso, isolamento, queda e limpeza. Teste de *split-brain* — isolar o primário, deixar os outros eleger, verificar que o antigo não confirma nada ao voltar — e teste de partição simétrica em que nenhum lado tem maioria. Consolidação da suíte e determinismo por semente. |
| **Jefferson Daniel Flores Montenegro** | **Medição e prova.** *Benchmark* com concorrência crescente, vazão em TPS e latência p50/p99, investigação do estrangulamento e registo dos números reais. Teste da invariante do dinheiro a atravessar as três etapas, e auditoria sob falha. |
| **Paulo Sebastian Rojo Pinedo** | **Observabilidade e apresentação.** Log estruturado com o vocabulário fechado, `GET /admin/metricas`, painel web em `/painel` conforme o [`CODESTYLE.md`](../docs/CODESTYLE.md). Diagramas UML em Mermaid, README da raiz e documentação final. |

A documentação final é revista pelos três. O dono desta etapa é o **Paulo**, por ser
quem tem a apresentação e a documentação.

---

## O que mudou face à etapa anterior

*A preencher durante a etapa.*

---

## Resultados

*A preencher no fecho: tabela de vazão e latência por número de clientes, tempo de
failover medido, número de testes a passar, e a tabela de rastreabilidade com o
estado real de cada F-xx, RF-xx e RNF-xx.*

---

## Limitações conhecidas

*A preencher no fecho. Esta secção não se omite: a implementação é avaliada pelo
que se sabe dela, não pelo que se promete.*
