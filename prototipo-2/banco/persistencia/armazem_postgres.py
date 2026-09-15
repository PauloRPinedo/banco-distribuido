"""O armazém principal: o log numa base PostgreSQL.

Este é o **único** módulo do projeto que conhece o `psycopg`, e importa-o dentro
do construtor, não no topo. É o que mantém verdadeira a promessa de que a suíte
de testes corre numa máquina onde não há nada instalado.

Duas escolhas que valem a pena defender:

**Uma só ligação, protegida por um lock.** Não há *pool* e não faz falta: as
leituras do banco — saldo, extrato, auditoria — servem-se do `Livro` em memória e
nunca tocam na base. A base só aparece no caminho de escrita, que o `_lock_estado`
do nó já serializa. Uma ligação por nó também tira da mesa a pergunta do
`max_connections` com três nós em dois laptops.

**`synchronous_commit = on` com `autocommit`.** Um `INSERT` é uma transação, e o
`COMMIT` só devolve depois de o registo estar em disco. É a equivalência exata do
`write` + `flush` + `os.fsync` do armazém em ficheiro, e é o que faz o passo 4
de uma escrita continuar a significar o mesmo.
"""

import json
import threading
from pathlib import Path

from banco.dominio.erros import ArmazemIndisponivel
from banco.persistencia.armazem import EstadoDoNo
from banco.persistencia.entrada import EntradaDeLog

CAMINHO_DO_ESQUEMA = Path(__file__).with_name("esquema.sql")


class ArmazemPostgres:

    def __init__(self, dsn: str, no_id: str) -> None:
        try:
            import psycopg
        except ImportError as erro:
            raise ArmazemIndisponivel(
                "falta o psycopg: instale com `pip install -r requisitos.txt`, "
                "ou arranque com `--armazem ficheiro`") from erro

        self._psycopg = psycopg
        self.no_id = no_id
        # Reentrante: há métodos públicos que tomam o lock e chamam consultas
        # que também o tomam. Com um Lock simples isso bloqueia o nó contra si
        # próprio, e o sintoma — o servidor a parar de responder — não aponta
        # para aqui.
        self._lock = threading.RLock()
        try:
            self._ligacao = psycopg.connect(dsn, autocommit=True,
                                            connect_timeout=5)
        except psycopg.Error as erro:
            raise ArmazemIndisponivel(
                f"não foi possível ligar à base: {erro}") from erro

        try:
            with self._lock:
                self._executar("SET synchronous_commit = on")
                self._aplicar_esquema()
                self._reclamar_a_base()
        except Exception:
            # A ligação já está aberta; se o arranque falhar daqui para a frente
            # — tipicamente por a base ser de outro nó — ninguém vai chamar
            # `fechar()`, porque não chegou a haver objeto. Fechá-la aqui é o que
            # impede o ResourceWarning e, com três nós a tentar arrancar, o
            # gasto silencioso de ligações do lado do servidor.
            self._ligacao.close()
            raise

    # --------------------------------------------------------- diagnóstico

    def descrever_durabilidade(self) -> str:
        """O que a base diz sobre si própria, para a linha de arranque.

        Imprime-se de propósito: é a resposta pronta a "e como é que sabes que
        houve fsync?". Ler a definição vale mais do que afirmá-la.
        """
        with self._lock:
            fsync = self._consultar_um("SHOW fsync")
            sincrono = self._consultar_um("SHOW synchronous_commit")
        return f"fsync={fsync} synchronous_commit={sincrono}"

    # ------------------------------------------------------------------- log

    def acrescentar(self, entrada: EntradaDeLog) -> None:
        with self._lock:
            self._inserir([entrada])

    def acrescentar_muitas(self, entradas: list[EntradaDeLog]) -> None:
        """O lote inteiro numa transação: uma espera por disco, não N.

        É o que faz uma réplica atrasada pôr-se em dia depressa. Também é
        tudo-ou-nada, o que importa: meio lote aplicado deixaria o log com um
        buraco que a correspondência de índices da replicação não sabe reparar.
        """
        if not entradas:
            return
        with self._lock:
            try:
                with self._ligacao.transaction():
                    self._inserir(entradas)
            except self._psycopg.Error as erro:
                raise ArmazemIndisponivel(
                    f"não foi possível gravar o lote no log: {erro}") from erro

    def ler_desde(self, indice: int) -> list[EntradaDeLog]:
        linhas = self._consultar(
            "SELECT indice, epoch, op_id, tipo, dados, instante "
            "FROM registo_do_log WHERE indice > %s ORDER BY indice", (indice,))
        return [EntradaDeLog(indice=linha[0], epoch=linha[1], op_id=linha[2],
                             tipo=linha[3], dados=linha[4], instante=linha[5])
                for linha in linhas]

    def ultimo_indice(self) -> int:
        return self._consultar_um(
            "SELECT COALESCE(MAX(indice), 0) FROM registo_do_log")

    def ultimo_epoch(self) -> int:
        return self._consultar_um(
            "SELECT COALESCE((SELECT epoch FROM registo_do_log "
            "ORDER BY indice DESC LIMIT 1), 0)")

    def epoch_em(self, indice: int) -> int | None:
        return self._consultar_um(
            "SELECT epoch FROM registo_do_log WHERE indice = %s", (indice,))

    def indice_de(self, op_id: str) -> int | None:
        return self._consultar_um(
            "SELECT indice FROM registo_do_log WHERE op_id = %s", (op_id,))

    def truncar_a_partir_de(self, indice: int) -> None:
        with self._lock:
            self._executar("DELETE FROM registo_do_log WHERE indice >= %s",
                           (indice,))

    # ---------------------------------------------------------------- estado

    def ler_estado(self) -> EstadoDoNo:
        linha = self._consultar(
            "SELECT epoch, votou_em, indice_commit FROM estado_do_no "
            "WHERE no_id = %s", (self.no_id,))
        if not linha:
            return EstadoDoNo()
        epoch, votou_em, indice_commit = linha[0]
        return EstadoDoNo(epoch, votou_em, indice_commit)

    def gravar_estado(self, epoch: int, votou_em: str | None) -> None:
        with self._lock:
            self._executar(
                "UPDATE estado_do_no SET epoch = %s, votou_em = %s "
                "WHERE no_id = %s", (epoch, votou_em, self.no_id))

    def gravar_commit(self, indice_commit: int) -> None:
        with self._lock:
            self._executar(
                "UPDATE estado_do_no SET indice_commit = %s WHERE no_id = %s",
                (indice_commit, self.no_id))

    def fechar(self) -> None:
        with self._lock:
            if not self._ligacao.closed:
                self._ligacao.close()

    def apagar_tudo(self) -> None:
        """Só para os testes: esvazia as duas tabelas e recomeça."""
        with self._lock:
            self._executar("DELETE FROM registo_do_log")
            self._executar("DELETE FROM estado_do_no")
            self._reclamar_a_base()

    # ---------------------------------------------------------------- dentro

    def _inserir(self, entradas: list[EntradaDeLog]) -> None:
        """Escreve as entradas. Quem chama já tem o lock."""
        try:
            with self._ligacao.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO registo_do_log "
                    "(indice, epoch, op_id, tipo, dados, instante) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    [(e.indice, e.epoch, e.op_id, e.tipo,
                      # json.dumps à mão, e não o adaptador do psycopg: é o
                      # mesmo serializador que o armazém em ficheiro usa, e os
                      # dois armazéns têm de guardar exatamente os mesmos bytes.
                      json.dumps(e.dados, ensure_ascii=False, sort_keys=True),
                      e.instante)
                     for e in entradas])
        except self._psycopg.Error as erro:
            raise ArmazemIndisponivel(
                f"não foi possível gravar no log: {erro}") from erro

    def _aplicar_esquema(self) -> None:
        self._executar(CAMINHO_DO_ESQUEMA.read_text(encoding="utf-8"))

    def _reclamar_a_base(self) -> None:
        """Marca esta base como sendo deste nó, e recusa-a se for de outro.

        Dois nós com o mesmo DSN partilhariam log sem dar sinal: os índices
        chocariam, a correspondência de índices falharia, e o sintoma pareceria
        um erro de eleição. Uma linha de SQL evita horas a procurar no protocolo.
        """
        # Ler **antes** de escrever. Inserir primeiro e verificar depois deixa a
        # linha do intruso gravada — em autocommit já não há transação para
        # desfazer — e a base fica com dois donos: a partir daí nem sequer o nó
        # legítimo consegue abri-la. O engano custou uma base de testes.
        donos = [linha[0] for linha in
                 self._consultar("SELECT no_id FROM estado_do_no")]
        alheios = [dono for dono in donos if dono != self.no_id]
        if alheios:
            raise ArmazemIndisponivel(
                f"esta base é do nó {alheios[0]!r} e não do nó {self.no_id!r}: "
                f"cada nó precisa da sua própria base de dados")
        if not donos:
            self._executar("INSERT INTO estado_do_no (no_id) VALUES (%s) "
                           "ON CONFLICT (no_id) DO NOTHING", (self.no_id,))

    def _executar(self, sql: str, parametros: tuple = ()) -> None:
        try:
            with self._ligacao.cursor() as cursor:
                cursor.execute(sql, parametros)
        except self._psycopg.Error as erro:
            raise ArmazemIndisponivel(f"a base recusou o pedido: {erro}") from erro

    def _consultar(self, sql: str, parametros: tuple = ()) -> list[tuple]:
        with self._lock:
            try:
                with self._ligacao.cursor() as cursor:
                    cursor.execute(sql, parametros)
                    return cursor.fetchall()
            except self._psycopg.Error as erro:
                raise ArmazemIndisponivel(
                    f"a base recusou a consulta: {erro}") from erro

    def _consultar_um(self, sql: str, parametros: tuple = ()):
        linhas = self._consultar(sql, parametros)
        return linhas[0][0] if linhas else None
