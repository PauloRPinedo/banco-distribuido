"""Ligação ao PostgreSQL deste nó.

Não há *pool* de propósito: uma ligação por pedido é suficiente à escala deste
trabalho, e um *pool* seria complexidade sem um problema medido que a
justifique.
"""

import os


def obter_conexao(dsn: str | None = None):
    """Uma ligação nova, com o commit automático desligado.

    Quem chama controla a transação, e é isso que torna uma transferência
    atómica: o débito, o crédito e o registo da operação caem todos na mesma
    transação, ou não cai nenhum.

    `BANCO_BD` aceita uma linha de ligação inteira, que é o que os testes usam
    para apontar a uma base descartável. Sem ela usam-se as variáveis `PG*`,
    que ficam com o nome em inglês por serem da libpq e não deste projeto.
    """
    import psycopg2
    import psycopg2.extras

    ligacao_pedida = dsn or os.environ.get("BANCO_BD")
    if ligacao_pedida:
        conexao = psycopg2.connect(
            ligacao_pedida, cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        conexao = psycopg2.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5432"),
            dbname=os.environ.get("PGDATABASE", "banco"),
            user=os.environ.get("PGUSER", "banco"),
            password=os.environ.get("PGPASSWORD", "banco"),
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    conexao.autocommit = False

    # A ordem total dos locks torna o deadlock impossível, por isso este limite
    # nunca devia disparar. Existe para que um erro futuro apareça como um erro
    # limpo em vez de uma suite de testes pendurada para sempre.
    with conexao.cursor() as cursor:
        cursor.execute("SET lock_timeout = '5s'")
    return conexao
