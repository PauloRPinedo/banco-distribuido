# Guia da réplica com PostgreSQL

Responde a uma pergunta concreta, já longamente discutida no desenho: **a
réplica é feita pelo Postgres ou pela aplicação?** — é feita **pela
aplicação**. Este guia explica como, e porque não se usa a `streaming
replication` nativa nem nenhum serviço gerido (RDS Multi-AZ, Cloud SQL HA,
etc.).

## A decisão, numa frase

Cada nó tem **o seu próprio** Postgres, completo e independente — os 3
Postgres nunca se ligam entre si nem falam diretamente. É o módulo `cluster`
(backend) que decide que escrita replicar para os outros nós e quando a dar
por confirmada.

## Porque não `streaming replication` / RDS Multi-AZ / Cloud SQL HA

Não é uma limitação técnica — o Postgres sabe fazer replicação nativa
perfeitamente. É que, se se delega aí, **desaparece exatamente o que este
projeto avalia**: RF-09 (eleição de primário), RF-10 (confirmação por
maioria) e RF-13 (recuperação depois de uma falha) deixam de fazer sentido
se um motor de base de dados já resolve a disponibilidade por conta própria.

Além disso, na prática: um serviço de replicação gerido tem a alta
disponibilidade paga no escalão gratuito de qualquer grande fornecedor — não
é uma opção "grátis" real para este projeto.

## Como fica na prática: replicação por máquina de estados

Em vez de copiar bytes de um disco para outro (o que faz a `streaming
replication`), copia-se o **comando**:

1. O cliente envia uma escrita ao primário (ex. uma transferência).
2. O primário valida-a contra as suas tabelas e grava uma entrada no seu log
   (`log_replicado`), com a operação, o instante e o `epoch`.
3. Envia essa mesma entrada, por HTTP, aos outros 2 nós
   (`POST /interno/replicar`, em `banco/cluster/replicacao.py`), que a gravam
   nos seus logs.
4. Com a maioria (2 de 3, contando consigo) a entrada fica **confirmada**; só
   então o primário a aplica às suas tabelas e responde ao cliente.
5. O heartbeat seguinte leva o índice confirmado às réplicas, e cada uma aplica
   a entrada ao **seu próprio** Postgres, com SQL normal (`INSERT`/`UPDATE`) e
   exatamente o mesmo código (`banco/servico/aplicador.py`) — não há nenhuma
   instrução SQL "especial" de replicação.

O resultado: as 3 bases acabam com o mesmo conteúdo, não porque o Postgres
as sincronizou, mas porque as 3 correram a mesma sequência determinista de
comandos. É o mesmo princípio que `dominio/` já usa desde o Protótipo 1
(funções puras, o mesmo resultado com o mesmo log) — aqui estende-se de "um
processo, um WAL" para "três processos, três Postgres".

## Instalação do Postgres por nó

Com Docker (recomendado, ver [`GUIA-IMPLANTACAO.md`](GUIA-IMPLANTACAO.md)):
cada nó sobe o seu próprio contentor `postgres:16-alpine`, com o esquema de
[`backend/db/esquema.sql`](../backend/db/esquema.sql) carregado automaticamente ao arrancar
(`docker-entrypoint-initdb.d`).

**Nota honesta sobre "Docker vs. nativo" para o Postgres**, porque não é uma
escolha sem nuances: a imagem oficial do Postgres no Docker Hub pensa-se para
prova de conceito, desenvolvimento e aprendizagem — a nível profissional, um
banco real em produção não correria `docker run postgres` tal e qual. Os
caminhos sérios em produção real são (a) um motor gerido (RDS/Cloud SQL —
descartado aqui de propósito, ver acima), ou (b) Postgres em contentores mas
com um operador especializado (CloudNativePG, Crunchy Postgres, o operador
da Zalando) sobre Kubernetes, ou (c) instalação nativa + ferramentas
dedicadas de cópia de segurança (`pgBackRest`/`barman`) + algo como o
Patroni para alta disponibilidade.

Para este projeto, o Docker simples continua a ser a escolha certa — porque
é exatamente o caso de uso que essa mesma literatura dá como válido
(aprendizagem/demonstração, não uma base com dinheiro real), e porque usar a
mesma imagem no `docker compose` local e no EC2 evita que a versão do
Postgres divirja entre "como se testa" e "como se implanta". Os `docker run`
de `GUIA-IMPLANTACAO.md` já incluem `--restart unless-stopped` e um limite
de memória — o mínimo que essa mesma fonte pede para não depender da
configuração por omissão do contentor.

**O que falta, e fica fora do âmbito de propósito:** nenhuma estratégia de
cópia de segurança (arquivo do WAL, `pg_dump` agendado) nem afinação de
memória além do limite do contentor — se isto fosse gerir dinheiro real,
seria a primeira brecha a fechar, antes de qualquer outra.

Sem Docker, instalação nativa em cada instância:

```bash
sudo apt install postgresql-16
sudo -u postgres createuser banco --pwprompt
sudo -u postgres createdb banco --owner banco
psql -U banco -d banco -f backend/db/esquema.sql
```

Em ambos os casos: **nada** de `pg_hba.conf` a aceitar ligações de outros
nós, **nada** de `wal_level = replica`, **nada** de `primary_conninfo` —
essas são justamente as configurações de `streaming replication` que este
projeto não usa. O único que se liga ao Postgres de um nó é o backend
**desse mesmo** nó — backend e Postgres vivem em instâncias separadas, por
isso essa ligação cruza a rede privada da VPC, mas a porta 5432 abre-se
apenas para o IP do backend desse nó, nunca para a internet nem para o resto
da VPC.

## Como verificar à mão que as 2-3 bases ficam iguais


```bash
# depois de uma transferência confirmada, comparar os saldos em cada Postgres
docker exec prototipo-2-postgres-a-1 psql -U banco -d banco -c "SELECT id, saldo_centavos FROM conta ORDER BY id;"
docker exec prototipo-2-postgres-b-1 psql -U banco -d banco -c "SELECT id, saldo_centavos FROM conta ORDER BY id;"
docker exec prototipo-2-postgres-c-1 psql -U banco -d banco -c "SELECT id, saldo_centavos FROM conta ORDER BY id;"
```

As três consultas devolvem **exatamente** as mesmas linhas — uma réplica pode
ir um heartbeat (150 ms) atrás do primário. A comparação completa, com contagens
e `md5` das contas e das operações, é a que o script
`provas/scripts/operacoes_api.py` faz antes e depois de matar o primário.

## Taxas de câmbio e outros dados "que se preenchem sozinhos"

O mesmo mecanismo aplica-se a tudo o que muda o estado, e não só ao dinheiro:
registar um utilizador (`registar_usuario`) e registar uma taxa de câmbio
(`registar_taxa`) são entradas do log como as outras, e cada nó aplica-as ao
seu próprio Postgres — não há uma tabela "partilhada" em sítio nenhum. O que
não é determinista (o instante, o id do utilizador, o sal do hash da senha)
decide-se no primário e vai dentro da entrada, para que os três nós guardem
exatamente o mesmo.
