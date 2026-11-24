"""Ligação ao PostgreSQL deste nó — cada nó tem o seu, e nenhum é partilhado.

As ligações reaproveitam-se. Abrir uma custa ~12 ms (medido num nó do `docker
compose`), e uma escrita abria quatro ou cinco: era o maior custo de cada
operação, à frente do disco (~1 ms por commit) e da rede entre nós (~2 ms).
Quem usa uma ligação continua a chamar `close()`; em vez de a fechar, isso
desfaz o que ficou por confirmar e devolve-a para o próximo pedido.
"""

import os
import threading
import time

# Vai nos parâmetros de arranque da ligação, e não num `SET` à parte, porque um
# `SET` é mais uma ida e volta em cada pedido. Contra um PostgreSQL local não se
# nota; contra um na nuvem são dezenas de milissegundos oferecidos a cada clique.
#
# A ordem total dos locks torna o deadlock impossível, por isso este limite nunca
# devia disparar. Existe para que um erro futuro apareça como um erro limpo em
# vez de uma suite de testes pendurada para sempre.
_ARRANQUE = "-c lock_timeout=5s"


# Quantas ligações paradas se guardam por base; as que sobram fecham-se.
MAXIMO_PARADAS = 96
# Uma ligação parada há mais do que isto é testada antes de ser entregue: o
# PostgreSQL pode ter sido reiniciado entretanto.
VERIFICAR_DEPOIS_DE_S = 30.0

_lock = threading.Lock()
_paradas: dict[tuple, list[tuple[object, float]]] = {}
_classe = None


def obter_conexao(dsn: str | None = None):
    """Uma ligação pronta a usar, com o commit automático desligado.

    Quem chama controla a transação, e é isso que torna uma transferência
    atómica: o débito, o crédito e o registo da operação caem todos na mesma
    transação, ou não cai nenhum.

    `BANCO_BD` aceita uma linha de ligação inteira. É o que os testes usam para
    apontar a uma base descartável.

    Sem `BANCO_BD` usam-se as variáveis `PG*`, que é o caso de cada nó no
    `compose.yaml` e em cada instância EC2, com o seu Postgres ao lado. Ficam com o nome em inglês por serem da libpq
    e não deste projeto.
    """
    import psycopg2
    import psycopg2.extras

    ligacao_pedida = dsn or os.environ.get("BANCO_BD")
    if ligacao_pedida:
        parametros = {"dsn": ligacao_pedida}
    else:
        parametros = {
            "host": os.environ.get("PGHOST", "localhost"),
            "port": os.environ.get("PGPORT", "5432"),
            "dbname": os.environ.get("PGDATABASE", "banco"),
            "user": os.environ.get("PGUSER", "banco"),
            "password": os.environ.get("PGPASSWORD", "banco"),
        }
    chave = tuple(sorted(parametros.items()))

    reaproveitada = _tirar_parada(chave)
    if reaproveitada is not None:
        return reaproveitada

    conexao = psycopg2.connect(**parametros, options=_ARRANQUE,
                               connection_factory=_classe_da_ligacao(),
                               cursor_factory=psycopg2.extras.RealDictCursor)
    conexao.chave_do_pool = chave
    conexao.autocommit = False
    return conexao


def _tirar_parada(chave: tuple):
    """Uma ligação parada desta base, já verificada se estava parada há muito."""
    while True:
        with _lock:
            paradas = _paradas.get(chave)
            if not paradas:
                return None
            conexao, desde = paradas.pop()
        if conexao.closed:
            continue
        if time.monotonic() - desde > VERIFICAR_DEPOIS_DE_S and not _responde(conexao):
            conexao.fechar_de_vez()
            continue
        return conexao


def _responde(conexao) -> bool:
    import psycopg2

    try:
        with conexao.cursor() as cursor:
            cursor.execute("SELECT 1")
        conexao.rollback()
        return True
    except psycopg2.Error:
        return False


def _devolver(conexao) -> bool:
    """Guarda a ligação para o próximo pedido; False se não há lugar."""
    with _lock:
        paradas = _paradas.setdefault(conexao.chave_do_pool, [])
        if len(paradas) >= MAXIMO_PARADAS:
            return False
        paradas.append((conexao, time.monotonic()))
        return True


def _classe_da_ligacao():
    """A classe das ligações do pool. Criada à primeira chamada, para que
    importar este módulo não exija o psycopg2."""
    global _classe
    if _classe is not None:
        return _classe

    import psycopg2
    import psycopg2.extensions

    class LigacaoReaproveitavel(psycopg2.extensions.connection):
        """Uma ligação cujo `close()` a devolve ao pool, limpa."""

        chave_do_pool: tuple = ()

        def close(self) -> None:
            if self.closed:
                return
            try:
                # Sem transação aberta nem modo trocado: o próximo a usá-la
                # recebe-a como se fosse nova.
                self.rollback()
                self.autocommit = False
                limpa = (self.info.transaction_status
                         == psycopg2.extensions.TRANSACTION_STATUS_IDLE)
            except psycopg2.Error:
                limpa = False
            if limpa and _devolver(self):
                return
            self.fechar_de_vez()

        def fechar_de_vez(self) -> None:
            super().close()

    _classe = LigacaoReaproveitavel
    return _classe
