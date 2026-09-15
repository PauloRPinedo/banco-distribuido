"""O armazém dos testes: listas e dicionários, sem disco nem base de dados.

Existe para que `python3 -m unittest discover -s tests` continue a correr numa
máquina onde não há PostgreSQL instalado — que é a promessa que sobrou depois
de o servidor passar a exigir uma base.

**`fechar()` não apaga nada**, e é de propósito: um teste de recuperação
constrói um `No` novo sobre a mesma instância de armazém, e é isso que faz
"reiniciar" significar alguma coisa sem tocar no disco.
"""

import threading

from banco.persistencia.armazem import EstadoDoNo
from banco.persistencia.entrada import EntradaDeLog


class ArmazemEmMemoria:

    def __init__(self) -> None:
        # O mesmo lock que as implementações reais têm. Sem ele, os testes de
        # concorrência exercitariam um armazém com garantias diferentes das do
        # que corre na demonstração, e passariam por motivo errado.
        self._lock = threading.Lock()
        self._entradas: list[EntradaDeLog] = []
        self._estado = EstadoDoNo()

    def acrescentar(self, entrada: EntradaDeLog) -> None:
        with self._lock:
            self._entradas.append(entrada)

    def acrescentar_muitas(self, entradas: list[EntradaDeLog]) -> None:
        with self._lock:
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

    def truncar_a_partir_de(self, indice: int) -> None:
        with self._lock:
            self._entradas = [e for e in self._entradas if e.indice < indice]

    def indice_de(self, op_id: str) -> int | None:
        with self._lock:
            for entrada in self._entradas:
                if entrada.op_id == op_id:
                    return entrada.indice
            return None

    def ler_estado(self) -> EstadoDoNo:
        with self._lock:
            return EstadoDoNo(self._estado.epoch, self._estado.votou_em,
                              self._estado.indice_commit)

    def gravar_estado(self, epoch: int, votou_em: str | None) -> None:
        with self._lock:
            self._estado.epoch = epoch
            self._estado.votou_em = votou_em

    def gravar_commit(self, indice_commit: int) -> None:
        with self._lock:
            self._estado.indice_commit = indice_commit

    def fechar(self) -> None:
        """Não faz nada, e é essa a graça — ver o cabeçalho do módulo."""
