"""O log de escrita antecipada: append-only, uma entrada por linha.

Escrever significa `write` + `flush` + `os.fsync`. Só depois do fsync é que a
entrada conta como durável; confirmar ao cliente uma operação que ainda está na
cache do sistema operativo quebra RNF-02 exatamente no cenário que a etapa 2 vai
exercitar com um SIGKILL.

Escolheu-se JSONL em vez de um formato binário por ser legível: quando o
failover se portar de forma estranha na demonstração, abrir os WAL dos três nós
com `tail` responde à pergunta em segundos.
"""

import json
import os
from pathlib import Path

from banco.persistencia.entrada import EntradaDeLog


class WalCorrompido(Exception):
    """Uma linha no meio do ficheiro não é JSON válido.

    Distingue-se de uma linha final truncada: essa é normal depois de uma queda
    e descarta-se em silêncio. Uma linha corrompida no meio significa que o
    ficheiro foi mexido por fora, e continuar seria aplicar um log com um buraco.
    """


class Wal:

    def __init__(self, caminho: Path) -> None:
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.touch(exist_ok=True)
        self._ficheiro = open(self.caminho, "a", encoding="utf-8")

    def acrescentar(self, entrada: EntradaDeLog) -> None:
        """Grava e só devolve depois de a entrada estar em disco."""
        self._ficheiro.write(entrada.para_linha() + "\n")
        self._ficheiro.flush()
        os.fsync(self._ficheiro.fileno())

    def ler_tudo(self) -> list[EntradaDeLog]:
        """Lê o log inteiro, descartando uma última linha incompleta.

        Uma linha incompleta é o rasto normal de um processo morto a meio de uma
        escrita. Como o fsync ainda não tinha devolvido, essa operação nunca foi
        confirmada a ninguém: descartá-la não perde nada que alguém julgue ter.
        O ficheiro é truncado nesse ponto para o próximo append não produzir uma
        linha colada à anterior.
        """
        bruto = self.caminho.read_bytes()
        if not bruto:
            return []

        linhas = bruto.split(b"\n")
        cauda = linhas.pop()
        completas = linhas

        if cauda:
            # Ficou texto sem terminador: a escrita foi cortada a meio.
            self._truncar(len(bruto) - len(cauda))

        entradas = []
        for numero, linha in enumerate(completas, 1):
            if not linha.strip():
                continue
            try:
                entradas.append(EntradaDeLog.de_linha(linha.decode("utf-8")))
            except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as erro:
                raise WalCorrompido(
                    f"{self.caminho}: linha {numero} ilegível ({erro})") from erro
        return entradas

    def ultimo_indice(self) -> int:
        entradas = self.ler_tudo()
        return entradas[-1].indice if entradas else 0

    def fechar(self) -> None:
        if not self._ficheiro.closed:
            self._ficheiro.close()

    def _truncar(self, tamanho: int) -> None:
        self._ficheiro.close()
        with open(self.caminho, "r+b") as ficheiro:
            ficheiro.truncate(tamanho)
            ficheiro.flush()
            os.fsync(ficheiro.fileno())
        self._ficheiro = open(self.caminho, "a", encoding="utf-8")
