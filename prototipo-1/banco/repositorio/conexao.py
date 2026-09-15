"""Ligação ao PostgreSQL que os nós partilham.

Não há *pool* de propósito: uma ligação por pedido é suficiente à escala deste
trabalho, e um *pool* seria complexidade sem um problema medido que a
justifique. Contra uma base na nuvem o custo verdadeiro é o TLS de cada ligação
nova; se uma escrita passar a demorar mais de meio segundo, aí há um problema
medido e um *pool* passa a justificar-se.
"""

import os

# Vai nos parâmetros de arranque da ligação, e não num `SET` à parte, porque um
# `SET` é mais uma ida e volta em cada pedido. Contra um PostgreSQL local não se
# nota; contra um na nuvem são dezenas de milissegundos oferecidos a cada clique.
#
# A ordem total dos locks torna o deadlock impossível, por isso este limite nunca
# devia disparar. Existe para que um erro futuro apareça como um erro limpo em
# vez de uma suite de testes pendurada para sempre.
_ARRANQUE = "-c lock_timeout=5s"


def obter_conexao(dsn: str | None = None):
    """Uma ligação nova, com o commit automático desligado.

    Quem chama controla a transação, e é isso que torna uma transferência
    atómica: o débito, o crédito e o registo da operação caem todos na mesma
    transação, ou não cai nenhum.

    `BANCO_BD` aceita uma linha de ligação inteira. É o que os testes usam para
    apontar a uma base descartável, e é o que os dois portáteis usam para
    apontar à mesma base gerida — aí a linha traz `?sslmode=require`, que viaja
    dentro da própria URL e não precisa de mais nada aqui.

    Sem `BANCO_BD` usam-se as variáveis `PG*`, que é o caso de um portátil só
    com o seu PostgreSQL ao lado. Ficam com o nome em inglês por serem da libpq
    e não deste projeto.
    """
    import psycopg2
    import psycopg2.extras

    ligacao_pedida = dsn or os.environ.get("BANCO_BD")
    if ligacao_pedida:
        conexao = psycopg2.connect(
            ligacao_pedida, options=_ARRANQUE,
            cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        conexao = psycopg2.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5432"),
            dbname=os.environ.get("PGDATABASE", "banco"),
            user=os.environ.get("PGUSER", "banco"),
            password=os.environ.get("PGPASSWORD", "banco"),
            options=_ARRANQUE,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    conexao.autocommit = False
    return conexao
