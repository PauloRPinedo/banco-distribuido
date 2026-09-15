"""O log em JSONL: append-only, uma entrada por linha.

Foi o armazém principal do Protótipo 1 até setembro de 2026, quando o PostgreSQL
o substituiu (docs/SPECS.md 11.4). Continua aqui por duas razões concretas, e não
por nostalgia:

- **é a saída de emergência da demonstração** — `--armazem ficheiro` faz o cluster
  funcionar num laptop onde o PostgreSQL não arranque;
- **é o único que tem o modo de falha "linha truncada"**, que os testes exercitam.
  Com uma base de dados esse caso deixa de existir: uma transação ou está
  confirmada ou não está.

Escrever significa `write` + `flush` + `os.fsync`. Só depois do fsync é que a
entrada conta como durável; confirmar ao cliente uma operação que ainda está na
cache do sistema operativo quebra RNF-02 exatamente no cenário do SIGKILL.

Escolheu-se JSONL em vez de um formato binário por ser legível: com o failover a
portar-se de forma estranha, abrir os log dos três nós com `tail` responde à
pergunta em segundos.
"""

import json
import os
import threading
from pathlib import Path

from banco.dominio.erros import ArmazemIndisponivel
from banco.persistencia.armazem import EstadoDoNo, LogCorrompido
from banco.persistencia.entrada import EntradaDeLog


class ArmazemEmFicheiro:

    def __init__(self, diretorio: Path) -> None:
        self.diretorio = Path(diretorio)
        self.diretorio.mkdir(parents=True, exist_ok=True)
        self.caminho = self.diretorio / "wal.jsonl"
        self.caminho_do_estado = self.diretorio / "estado.json"

        self._lock = threading.Lock()
        self.caminho.touch(exist_ok=True)
        # O log inteiro fica em memória depois do arranque. É a mesma escolha do
        # armazém em PostgreSQL, e o que torna `epoch_em` e `indice_de` baratos:
        # SPECS 7 chama-os uma vez por replicação, e reler o ficheiro de cada vez
        # seria quadrático no tamanho do log.
        self._entradas = self._ler_do_disco()
        self._ficheiro = open(self.caminho, "a", encoding="utf-8")
        self._estado = self._carregar_estado()

    # ------------------------------------------------------------------- log

    def acrescentar(self, entrada: EntradaDeLog) -> None:
        with self._lock:
            self._escrever([entrada])
            self._entradas.append(entrada)

    def acrescentar_muitas(self, entradas: list[EntradaDeLog]) -> None:
        if not entradas:
            return
        with self._lock:
            self._escrever(entradas)
            self._entradas.extend(entradas)

    def ler_desde(self, indice: int) -> list[EntradaDeLog]:
        with self._lock:
            return [e for e in self._entradas if e.indice > indice]

    def ultimo_indice(self) -> int:
        with self._lock:
            return self._entradas[-1].indice if self._entradas else 0

    def ultimo_epoch(self) -> int:
        with self._lock:
            return self._entradas[-1].epoch if self._entradas else 0

    def epoch_em(self, indice: int) -> int | None:
        with self._lock:
            for entrada in self._entradas:
                if entrada.indice == indice:
                    return entrada.epoch
            return None

    def indice_de(self, op_id: str) -> int | None:
        with self._lock:
            for entrada in self._entradas:
                if entrada.op_id == op_id:
                    return entrada.indice
            return None

    def truncar_a_partir_de(self, indice: int) -> None:
        """Reescreve o ficheiro sem as entradas a partir de `indice`.

        Reescrever um ficheiro append-only é feio, e é assumido: truncar é raro
        (só acontece quando um nó volta com log divergente) e nunca está no
        caminho de uma escrita normal.
        """
        with self._lock:
            ficam = [e for e in self._entradas if e.indice < indice]
            if len(ficam) == len(self._entradas):
                return
            self._ficheiro.close()
            temporario = self.caminho.with_suffix(".tmp")
            with open(temporario, "w", encoding="utf-8") as novo:
                for entrada in ficam:
                    novo.write(entrada.para_linha() + "\n")
                novo.flush()
                os.fsync(novo.fileno())
            os.replace(temporario, self.caminho)
            self._entradas = ficam
            self._ficheiro = open(self.caminho, "a", encoding="utf-8")

    # ---------------------------------------------------------------- estado

    def ler_estado(self) -> EstadoDoNo:
        with self._lock:
            return EstadoDoNo(self._estado.epoch, self._estado.votou_em,
                              self._estado.indice_commit)

    def gravar_estado(self, epoch: int, votou_em: str | None) -> None:
        with self._lock:
            self._estado.epoch = epoch
            self._estado.votou_em = votou_em
            self._gravar_estado_no_disco()

    def gravar_commit(self, indice_commit: int) -> None:
        with self._lock:
            self._estado.indice_commit = indice_commit
            self._gravar_estado_no_disco()

    def fechar(self) -> None:
        with self._lock:
            if not self._ficheiro.closed:
                self._ficheiro.close()

    # ----------------------------------------------------------------- disco

    def _escrever(self, entradas: list[EntradaDeLog]) -> None:
        try:
            for entrada in entradas:
                self._ficheiro.write(entrada.para_linha() + "\n")
            self._ficheiro.flush()
            os.fsync(self._ficheiro.fileno())
        except OSError as erro:
            raise ArmazemIndisponivel(
                f"não foi possível gravar no log: {erro}") from erro

    def _gravar_estado_no_disco(self) -> None:
        """Escreve num temporário e substitui, para nunca ficar truncado.

        Sem isto, uma queda a meio da escrita deixaria um `estado.json` cortado e
        o nó não voltaria a arrancar por não conseguir ler o próprio epoch.
        """
        temporario = self.caminho_do_estado.with_suffix(".tmp")
        conteudo = json.dumps({"epoch": self._estado.epoch,
                               "votou_em": self._estado.votou_em,
                               "indice_commit": self._estado.indice_commit},
                              ensure_ascii=False, sort_keys=True)
        try:
            with open(temporario, "w", encoding="utf-8") as ficheiro:
                ficheiro.write(conteudo)
                ficheiro.flush()
                os.fsync(ficheiro.fileno())
            os.replace(temporario, self.caminho_do_estado)
        except OSError as erro:
            raise ArmazemIndisponivel(
                f"não foi possível gravar o estado do nó: {erro}") from erro

    def _carregar_estado(self) -> EstadoDoNo:
        if not self.caminho_do_estado.exists():
            return EstadoDoNo()
        bruto = json.loads(self.caminho_do_estado.read_text(encoding="utf-8"))
        return EstadoDoNo(bruto["epoch"], bruto["votou_em"],
                          # Os estados gravados antes de o commit existir não têm
                          # o campo. Lê-se 0, que é o valor correto: sem
                          # replicação, nada estava confirmado por maioria.
                          bruto.get("indice_commit", 0))

    def _ler_do_disco(self) -> list[EntradaDeLog]:
        """Lê o log, descartando uma última linha incompleta.

        Uma linha incompleta é o rasto normal de um processo morto a meio de uma
        escrita. Como o fsync ainda não tinha devolvido, essa operação nunca foi
        confirmada a ninguém: descartá-la não perde nada que alguém julgue ter.
        O ficheiro é truncado nesse ponto para o append seguinte não produzir uma
        linha colada à anterior.
        """
        bruto = self.caminho.read_bytes()
        if not bruto:
            return []

        linhas = bruto.split(b"\n")
        cauda = linhas.pop()
        if cauda:
            self._truncar_ficheiro(len(bruto) - len(cauda))

        entradas = []
        for numero, linha in enumerate(linhas, 1):
            if not linha.strip():
                continue
            try:
                entradas.append(EntradaDeLog.de_linha(linha.decode("utf-8")))
            except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as erro:
                raise LogCorrompido(
                    f"{self.caminho}: linha {numero} ilegível ({erro})") from erro
        return entradas

    def _truncar_ficheiro(self, tamanho: int) -> None:
        with open(self.caminho, "r+b") as ficheiro:
            ficheiro.truncate(tamanho)
            ficheiro.flush()
            os.fsync(ficheiro.fileno())
