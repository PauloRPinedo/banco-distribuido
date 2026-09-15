"""Escolhe o armazém a partir do nome, e é o único sítio que conhece o psycopg.

O `import psycopg` está **dentro** da função, não no topo do módulo. Não é
manha: é o que mantém verdadeira a promessa da secção 4 de docs/CONVENCOES.md de
que a suíte de testes corre numa máquina sem nada instalado. A consequência
verifica-se num comando:

    python3 -c "import banco.cluster.no"     # não toca em psycopg
"""

from pathlib import Path

from banco.persistencia.armazem import ArmazemDeLog

NOMES = ("postgres", "ficheiro", "memoria")


def criar_armazem(tipo: str, *, no_id: str = "A", diretorio: Path | None = None,
                  dsn: str | None = None) -> ArmazemDeLog:
    if tipo == "memoria":
        from banco.persistencia.armazem_memoria import ArmazemEmMemoria
        return ArmazemEmMemoria()

    if tipo == "ficheiro":
        if diretorio is None:
            raise ValueError("o armazém em ficheiro precisa de um diretório")
        from banco.persistencia.armazem_ficheiro import ArmazemEmFicheiro
        return ArmazemEmFicheiro(diretorio)

    if tipo == "postgres":
        if not dsn:
            raise ValueError(
                "o armazém em PostgreSQL precisa de um DSN: use --bd ou a "
                "variável BANCO_BD, por exemplo "
                "postgresql://banco@localhost/banco_a")
        from banco.persistencia.armazem_postgres import ArmazemPostgres
        return ArmazemPostgres(dsn, no_id)

    raise ValueError(f"armazém desconhecido: {tipo!r}; use um de {NOMES}")
