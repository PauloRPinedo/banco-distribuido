"""O contrato do armazém do log, e o estado de eleição que o acompanha.

Existe para que o nó não saiba onde o log está guardado. Há três implementações:
PostgreSQL (`armazem_postgres`, o principal desde setembro de 2026), ficheiro
JSONL (`armazem_ficheiro`, o original, hoje saída de emergência) e memória
(`armazem_memoria`, os testes).

Cada método sai de uma linha concreta de docs/SPECS.md — não há aqui nenhum
"por precaução". A lista fechada é o que impede este contrato de crescer até
deixar de ser substituível:

| Método | De onde vem |
|---|---|
| `acrescentar` | SPECS 5, passo 4 |
| `acrescentar_muitas` | SPECS 7, a réplica recebe um lote do líder |
| `ler_desde` | SPECS 4.2, recuperação; e `GET /interno/log?desde=N` |
| `ultimo_indice`, `ultimo_epoch` | SPECS 8.2, condição 3 do voto |
| `epoch_em` | SPECS 7, correspondência de log |
| `truncar_a_partir_de` | SPECS 7, entradas divergentes |
| `indice_de` | SPECS 4.3, deduplicação apoiada na base |
| `ler_estado`, `gravar_estado` | SPECS 8.2, o voto tem de ser durável |
| `gravar_commit` | SPECS 4.3, o commit é um prefixo |
"""

from dataclasses import dataclass
from typing import Protocol

from banco.persistencia.entrada import EntradaDeLog


class LogCorrompido(Exception):
    """O log não é legível de uma forma que o arranque não pode contornar.

    Não herda de `ErroDoBanco` porque nunca chega a ser uma resposta HTTP: se
    isto acontece, o nó não arranca. Distingue-se de propósito de uma cauda
    truncada, que é o rasto normal de uma queda e se descarta em silêncio.
    """


@dataclass
class EstadoDoNo:
    """O que um nó tem de se lembrar sobre si próprio ao arrancar.

    Não sabe onde é guardado: quem o grava é o armazém. Antes de setembro de
    2026 esta classe conhecia o caminho do seu `estado.json`, o que a prendia ao
    armazém em ficheiro.

    `indice_commit` é um prefixo, não um conjunto: o que está confirmado é sempre
    um troço contíguo do início do log. Guardar um sinal por entrada permitiria
    representar estados que o protocolo não consegue produzir (SPECS 4.3).
    """

    epoch: int = 1
    votou_em: str | None = None
    indice_commit: int = 0


class ArmazemDeLog(Protocol):
    """O que o nó precisa que alguém saiba fazer com o log."""

    def acrescentar(self, entrada: EntradaDeLog) -> None:
        """Só devolve depois de a entrada estar em disco.

        Levanta `ArmazemIndisponivel` se não conseguir: uma entrada que não é
        durável não pode ser aplicada nem confirmada a ninguém.
        """

    def acrescentar_muitas(self, entradas: list[EntradaDeLog]) -> None:
        """O lote inteiro com uma só espera por disco, ou nada.

        É o que faz uma réplica atrasada pôr-se em dia depressa: sem isto, cem
        entradas seriam cem esperas por `fsync`.
        """

    def ler_desde(self, indice: int) -> list[EntradaDeLog]:
        """As entradas com índice **maior** que `indice`, por ordem. 0 lê tudo."""

    def ultimo_indice(self) -> int:
        """0 se o log estiver vazio."""

    def ultimo_epoch(self) -> int:
        """O `epoch` da última entrada, 0 se o log estiver vazio."""

    def epoch_em(self, indice: int) -> int | None:
        """O `epoch` da entrada nesse índice, `None` se não existir."""

    def truncar_a_partir_de(self, indice: int) -> None:
        """Apaga as entradas com índice maior ou igual a `indice`.

        Quem chama garante que não desce abaixo do `indice_commit`: essas já
        foram confirmadas a um cliente e apagá-las perderia dinheiro.
        """

    def indice_de(self, op_id: str) -> int | None:
        """O índice da entrada com esse `op_id`, se existir."""

    def ler_estado(self) -> EstadoDoNo:
        ...

    def gravar_estado(self, epoch: int, votou_em: str | None) -> None:
        """Durável antes de devolver: um voto esquecido é um voto repetido."""

    def gravar_commit(self, indice_commit: int) -> None:
        ...

    def fechar(self) -> None:
        ...
