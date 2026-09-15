# ADR-0001 — Persistência, replicação e implantação do cluster

**Estado:** proposta — decisão em aberto para o grupo. Registrada aqui porque
`CONVENCOES.md` pede que toda decisão de desenho fique escrita com a
justificação, e esta é a spec que faltava: nem `SPECS.md` nem o `ROADMAP.md`
falam de onde o cluster vai correr fora do laptop de cada um.

Relacionado: [`revisao_e_recomendacoes.md`](../revisao_e_recomendacoes.md),
[`entregables/05-modelo-de-datos/`](../entregables/05-modelo-de-datos/), `SPECS.md` §7–9.

---

## Contexto

O projeto final quer: frontend, backend e persistência, com o backend e a
persistência **replicados** para tolerância a falhas. A dúvida é onde implantar
isso de graça, e se dá para usar 2 bases Supabase, a camada gratuita de AWS/GCP,
ou o servidor do professor.

Duas perguntas estão misturadas e precisam de decisões separadas:

1. **Quem faz a replicação** — o grupo (protocolo próprio, é o que RF-09 a
   RF-13 avaliam) ou um serviço gerenciado (Postgres com HA, Supabase, RDS
   Multi-AZ)?
2. **Onde os processos rodam** — que é só infraestrutura, independente da 1.

`proposta.md` (Restrições) fixa: *"O consenso e o protocolo de transações são
implementados do zero, sem bibliotecas prontas para essas funções."* Isso
restringe a pergunta 1 antes de se chegar à pergunta 2.

---

## Decisão 1 — quem faz a replicação

### Opção A — manter a arquitetura já especificada (recomendada)

Cada nó continua sendo backend + persistência juntos: processo Python, WAL
próprio em disco, protocolo de quórum/eleição escrito pelo grupo (o que o
Protótipo 2 ainda vai construir). O frontend é uma camada fina por cima da API
HTTP que já existe (`SPECS.md` §6), na prática o painel web previsto em F-11 mais
os formulários que faltarem.

- **A favor:** é o que `proposta.md` pede e o que RF-09 a RF-13 avaliam.
  Reaproveita 100% do Protótipo 1. Nenhuma dependência nova.
- **Contra:** dá mais trabalho do que apontar para um Postgres gerenciado.

### Opção B — backend + BD externa com replicação do provedor

Trocar o WAL próprio por um Postgres (Supabase, RDS, Cloud SQL) e usar a
replicação/HA do provedor para tolerância a falhas.

- **A favor:** menos código de infraestrutura para manter.
- **Contra:** delega a um terceiro exatamente a parte avaliada em RF-09 a
  RF-13. Na camada gratuita de qualquer um desses provedores, além disso,
  **não existe HA de graça** — é recurso pago. E replicar entre dois projetos
  Supabase não é automático: exigiria escrever a sincronização na aplicação,
  o que é o mesmo problema do Protótipo 2 com um salto de rede a mais.

### Opção C — híbrido

Terminar o Protótipo 2 e o Projeto final com o protocolo próprio (o que conta
para a nota), e manter a ideia de BD gerenciada como uma segunda demonstração,
fora do escopo avaliado, se sobrar tempo.

### Recomendação

**Opção A**, com a Opção C como válvula de escape se o grupo quiser mostrar a
versão "de mercado" à parte. A Opção B só faz sentido se o grupo decidir
conscientemente abrir mão de RF-09 a RF-13 como estão definidos hoje — o que
seria mudar a proposta, não implementá-la.

---

## Decisão 2 — onde implantar (só depois de resolver a Decisão 1)

Requisito de rede já existe em `SPECS.md` §9: nós acessíveis por HTTP entre si,
ligados em `0.0.0.0`, portas abertas na *firewall*, testados com `curl` antes de
subir o cluster. Qualquer opção abaixo tem de cumprir isso.

| Opção | Custo | Duração | Observação |
|---|---|---|---|
| **Servidor do professor** | zero | o que o professor permitir | Replica exatamente o cenário "2-3 laptops numa rede local" que `SPECS.md` já descreve — zero fricção de rede entre provedores diferentes. Primeira escolha se o professor confirmar disponibilidade e portas. |
| **Oracle Cloud "Always Free"** | zero, sem prazo de expiração | permanente enquanto a conta existir | Até 4 VMs Ampere (ARM) ou 2 AMD *micro*, cada uma com IP público. É o único free tier dos três grandes que não tem prazo de 12 meses — dá para deixar os 2-3 nós no ar o mês inteiro sem custo. Melhor opção se o servidor do professor não for viável. |
| **AWS EC2 Free Tier** | zero até um limite | só nos primeiros 12 meses da conta | 750 h/mês, **somadas entre todas as instâncias** ligadas ao mesmo tempo — 3 nós `t2/t3.micro` rodando 24h/dia consomem isso em ~10 dias e passam a cobrar. Serve para ensaios pontuais (ligar antes da demonstração, desligar depois), não para manter no ar o mês todo. |
| **Google Cloud Free Tier** | zero, sem prazo | permanente, mas só 1 instância | Uma única `e2-micro` sempre grátis, e só em regiões dos EUA. Sozinha não cobre 2-3 nós; precisaria combinar com outro provedor. |
| **Supabase (BD, não servidor de aplicação)** | zero | camada gratuita padrão | Não hospeda o backend Python, só uma BD Postgres. Só entra na conta se a Decisão 1 for a Opção B — e mesmo assim, a camada gratuita não tem *failover* automático (ver Decisão 1). |

### Recomendação

1. Confirmar com o professor se o servidor dele está disponível e por quanto
   tempo — é a opção mais simples e mais fiel ao que `SPECS.md` já descreve.
2. Se não, **Oracle Cloud Always Free** para os 2-3 nós, um por VM, cada uma
   com IP público, seguindo à risca o guia de rede de `SPECS.md` §9 (bind em
   `0.0.0.0`, `curl` antes de subir o cluster).
3. AWS/GCP ficam como alternativa só para janelas curtas de teste ou
   demonstração ao vivo, não para manter o cluster no ar durante todo o
   desenvolvimento — o risco de cobrança ou de só ter 1 nó grátis é real.

Termos de free tier mudam com frequência; confirmar no site do provedor antes
de decidir, esta tabela é um retrato de 2026.

---

## Consequências

- Se o grupo aceitar a Opção A: o Protótipo 2 se mantém como planejado no
  `ROADMAP.md`, sem mudança de escopo. O "frontend" vira uma tarefa pequena
  (reaproveita `interface/cliente_http.py` e o painel de F-11), não um sistema
  novo.
- Se o grupo preferir a Opção B ou C: `proposta.md` e `SPECS.md` precisam de
  uma revisão explícita antes de codificar, porque RF-09 a RF-13 deixam de
  fazer sentido do jeito que estão escritos hoje.
- Em qualquer caso, a escolha de hospedagem (Decisão 2) é independente e pode
  ser adiada até a Decisão 1 estar fechada.
