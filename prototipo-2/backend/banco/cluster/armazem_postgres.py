"""O log replicado e o estado de eleição, na base PostgreSQL do próprio nó.

Uma só ligação, em *autocommit*, protegida por um lock. Em *autocommit* cada
`INSERT` é uma transação, e o `COMMIT` só devolve depois de o registo estar em
disco (`synchronous_commit` ligado, que é o valor por omissão): é isso que faz o
passo "gravar de forma durável" de uma escrita significar alguma coisa.

O `psycopg2` importa-se no construtor, e não no topo, para que os testes sem
base possam importar o pacote `cluster` numa máquina sem nada instalado.
"""

import json
import threading

from banco.cluster.armazem import EstadoDoNo
from banco.cluster.entrada import EntradaDeLog
from banco.cluster.erros import ArmazemIndisponivel


class ArmazemPostgres:

    def __init__(self, no_id: str, conexao) -> None:
        import psycopg2

        self._erro_da_base = psycopg2.Error
        self.no_id = no_id
        # Reentrante: há métodos que tomam o lock e chamam consultas que também
        # o tomam.
        self._lock = threading.RLock()
        self._conexao = conexao
        self._conexao.autocommit = True
        try:
            self._reclamar_a_base()
        except Exception:
            self._conexao.close()
            raise

    # ------------------------------------------------------------------- log

    def acrescentar(self, entrada: EntradaDeLog) -> None:
        with self._lock:
            self._inserir([entrada])

    def acrescentar_muitas(self, entradas: list[EntradaDeLog]) -> None:
        """O lote inteiro numa transação, ou nada: meio lote deixaria um buraco
        que a correspondência de índices da replicação não sabe reparar."""
        if not entradas:
            return
        with self._lock:
            self._conexao.autocommit = False
            try:
                self._inserir(entradas)
                self._conexao.commit()
            except Exception:
                self._conexao.rollback()
                raise
            finally:
                self._conexao.autocommit = True

    def ler_desde(self, indice: int) -> list[EntradaDeLog]:
        linhas = self._consultar(
            "SELECT indice, epoch, op_id, tipo, dados, instante "
            "FROM log_replicado WHERE indice > %s ORDER BY indice", (indice,))
        return [EntradaDeLog(indice=l[0], epoch=l[1], op_id=l[2], tipo=l[3],
                             dados=l[4], instante=l[5]) for l in linhas]

    def ultimo_indice(self) -> int:
        return self._consultar_um("SELECT COALESCE(MAX(indice), 0) FROM log_replicado")

    def ultimo_epoch(self) -> int:
        return self._consultar_um(
            "SELECT COALESCE((SELECT epoch FROM log_replicado "
            "ORDER BY indice DESC LIMIT 1), 0)")

    def epoch_em(self, indice: int) -> int | None:
        return self._consultar_um(
            "SELECT epoch FROM log_replicado WHERE indice = %s", (indice,))

    def indice_de(self, op_id: str) -> int | None:
        return self._consultar_um(
            "SELECT indice FROM log_replicado WHERE op_id = %s", (op_id,))

    def truncar_a_partir_de(self, indice: int) -> None:
        with self._lock:
            self._executar("DELETE FROM log_replicado WHERE indice >= %s", (indice,))

    # ---------------------------------------------------------------- estado

    def ler_estado(self) -> EstadoDoNo:
        linhas = self._consultar(
            "SELECT epoch, votou_em, indice_commit FROM estado_do_no "
            "WHERE no_id = %s", (self.no_id,))
        if not linhas:
            return EstadoDoNo()
        epoch, votou_em, indice_commit = linhas[0]
        return EstadoDoNo(epoch, votou_em, indice_commit)

    def gravar_estado(self, epoch: int, votou_em: str | None) -> None:
        """Durável antes de devolver: um voto esquecido é um voto repetido."""
        with self._lock:
            self._executar("UPDATE estado_do_no SET epoch = %s, votou_em = %s "
                           "WHERE no_id = %s", (epoch, votou_em, self.no_id))

    def gravar_commit(self, indice_commit: int) -> None:
        with self._lock:
            self._executar("UPDATE estado_do_no SET indice_commit = %s "
                           "WHERE no_id = %s", (indice_commit, self.no_id))

    def fechar(self) -> None:
        with self._lock:
            if not self._conexao.closed:
                self._conexao.close()

    # ---------------------------------------------------------------- dentro

    def _inserir(self, entradas: list[EntradaDeLog]) -> None:
        try:
            with self._conexao.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO log_replicado (indice, epoch, op_id, tipo, dados, instante) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    [(e.indice, e.epoch, e.op_id, e.tipo,
                      json.dumps(e.dados, ensure_ascii=False, sort_keys=True),
                      e.instante) for e in entradas])
        except self._erro_da_base as erro:
            raise ArmazemIndisponivel(f"não foi possível gravar no log: {erro}") from erro

    def _reclamar_a_base(self) -> None:
        """Marca a base como deste nó, e recusa-a se for de outro.

        Dois nós com a mesma base partilhariam log sem dar sinal: os índices
        chocariam e o sintoma pareceria um erro de eleição.
        """
        donos = [linha[0] for linha in self._consultar("SELECT no_id FROM estado_do_no")]
        alheios = [dono for dono in donos if dono != self.no_id]
        if alheios:
            raise ArmazemIndisponivel(
                f"esta base é do nó {alheios[0]!r} e não do nó {self.no_id!r}: "
                "cada nó precisa da sua própria base de dados")
        if not donos:
            self._executar("INSERT INTO estado_do_no (no_id) VALUES (%s) "
                           "ON CONFLICT (no_id) DO NOTHING", (self.no_id,))

    def _executar(self, sql: str, parametros: tuple = ()) -> None:
        try:
            with self._conexao.cursor() as cursor:
                cursor.execute(sql, parametros)
        except self._erro_da_base as erro:
            raise ArmazemIndisponivel(f"a base recusou o pedido: {erro}") from erro

    def _consultar(self, sql: str, parametros: tuple = ()) -> list[tuple]:
        with self._lock:
            try:
                # Cursor de tuplas, e não o RealDictCursor da ligação: aqui
                # lê-se por posição.
                with self._conexao.cursor(cursor_factory=None) as cursor:
                    cursor.execute(sql, parametros)
                    return [tuple(linha.values()) if isinstance(linha, dict) else linha
                            for linha in cursor.fetchall()]
            except self._erro_da_base as erro:
                raise ArmazemIndisponivel(f"a base recusou a consulta: {erro}") from erro

    def _consultar_um(self, sql: str, parametros: tuple = ()):
        linhas = self._consultar(sql, parametros)
        return linhas[0][0] if linhas else None
