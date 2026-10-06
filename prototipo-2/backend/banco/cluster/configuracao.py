"""O ficheiro do cluster, lido e validado.

Valida à entrada, e não no ponto de uso, por uma razão prática: um `heartbeat_ms`
demasiado próximo do *timeout* de eleição não dá erro nenhum — dá um cluster que
troca de primário sem parar, e o sintoma parece um erro de protocolo. Custa três
linhas apanhá-lo aqui e custa uma tarde apanhá-lo na demonstração.

A semente é derivada por nó, e isso não é um detalhe: com a mesma semente nos
três, todos sorteiam o mesmo *timeout*, candidatam-se ao mesmo tempo, dividem os
votos e a eleição nunca converge. É o erro mais caro desta etapa.
"""

import json
import zlib
from dataclasses import dataclass
from pathlib import Path

# Quantas vezes o timeout de eleição mais curto tem de caber no heartbeat. Com
# 150 ms e [800, 1500] a folga real é de 5,3×; abaixo de 4 uma lentidão
# momentânea do primário chega para derrubar um primário saudável.
FOLGA_MINIMA = 4


class ConfiguracaoInvalida(Exception):
    """O ficheiro existe mas descreve um cluster que não pode funcionar."""


@dataclass(frozen=True)
class NoDoCluster:
    id: str
    endereco: str
    porta: int

    @property
    def url(self) -> str:
        return f"http://{self.endereco}:{self.porta}"


@dataclass(frozen=True)
class ConfiguracaoDoCluster:
    nos: tuple[NoDoCluster, ...]
    heartbeat_ms: int
    timeout_eleicao_ms: tuple[int, int]
    timeout_replicacao_ms: int
    semente: int

    @property
    def maioria(self) -> int:
        """Metade mais um. Com 3 nós são 2; com 2 nós são 2.

        Com 2 nós a maioria continua a ser 2, e é por isso que se correm
        3 nós mesmo com 2 laptops: a queda de um deixaria o outro sem
        maioria, em somente leitura, e não haveria failover para demonstrar.
        """
        return len(self.nos) // 2 + 1

    def obter(self, id_do_no: str) -> NoDoCluster:
        for no in self.nos:
            if no.id == id_do_no:
                return no
        conhecidos = ", ".join(no.id for no in self.nos)
        raise ConfiguracaoInvalida(
            f"o nó {id_do_no!r} não está no cluster; conhecidos: {conhecidos}")

    def pares_de(self, id_do_no: str) -> tuple[NoDoCluster, ...]:
        """Os outros nós. Quem chama nunca se replica a si próprio."""
        return tuple(no for no in self.nos if no.id != id_do_no)

    def semente_do_no(self, id_do_no: str) -> int:
        """Semente própria de cada nó, derivada da global.

        `crc32` do id é determinístico entre máquinas e entre execuções — ao
        contrário de `hash()`, que em Python muda a cada arranque e deitaria
        fora a reprodutibilidade que RNF-06 exige.
        """
        return self.semente + zlib.crc32(id_do_no.encode("utf-8"))

    @staticmethod
    def de_ficheiro(caminho: Path) -> "ConfiguracaoDoCluster":
        caminho = Path(caminho)
        if not caminho.exists():
            raise ConfiguracaoInvalida(
                f"não existe {caminho}; copie o exemplo: "
                f"cp config/cluster.exemplo.json {caminho}")
        try:
            bruto = json.loads(caminho.read_text(encoding="utf-8"))
        except json.JSONDecodeError as erro:
            raise ConfiguracaoInvalida(
                f"{caminho} não é JSON válido: {erro}") from erro
        return ConfiguracaoDoCluster.de_dados(bruto)

    @staticmethod
    def de_dados(bruto: dict) -> "ConfiguracaoDoCluster":
        nos = tuple(_ler_no(item) for item in _exigir(bruto, "nos", list))
        if not nos:
            raise ConfiguracaoInvalida("o cluster não tem nós nenhuns")

        ids = [no.id for no in nos]
        repetidos = {id_ for id_ in ids if ids.count(id_) > 1}
        if repetidos:
            raise ConfiguracaoInvalida(
                f"ids repetidos no cluster: {', '.join(sorted(repetidos))}")

        enderecos = [(no.endereco, no.porta) for no in nos]
        if len(set(enderecos)) != len(enderecos):
            raise ConfiguracaoInvalida(
                "dois nós no mesmo endereço e porta: em dois laptops, o segundo "
                "nó da mesma máquina precisa de outra porta")

        heartbeat = _exigir(bruto, "heartbeat_ms", int)
        eleicao = _exigir(bruto, "timeout_eleicao_ms", list)
        if len(eleicao) != 2 or not all(isinstance(v, int) for v in eleicao):
            raise ConfiguracaoInvalida(
                "timeout_eleicao_ms tem de ser [minimo, maximo] em inteiros")
        minimo, maximo = eleicao
        if minimo >= maximo:
            raise ConfiguracaoInvalida(
                f"timeout_eleicao_ms: o mínimo ({minimo}) tem de ser menor que "
                f"o máximo ({maximo}), senão não há sorteio nenhum")
        if heartbeat <= 0:
            raise ConfiguracaoInvalida("heartbeat_ms tem de ser positivo")
        if heartbeat * FOLGA_MINIMA > minimo:
            raise ConfiguracaoInvalida(
                f"heartbeat_ms ({heartbeat}) está demasiado perto do timeout de "
                f"eleição mais curto ({minimo}): um atraso momentâneo derrubaria "
                f"um primário saudável. Use no máximo {minimo // FOLGA_MINIMA} ms")

        return ConfiguracaoDoCluster(
            nos=nos,
            heartbeat_ms=heartbeat,
            timeout_eleicao_ms=(minimo, maximo),
            timeout_replicacao_ms=_exigir(bruto, "timeout_replicacao_ms", int),
            semente=_exigir(bruto, "semente", int))


def _ler_no(item) -> NoDoCluster:
    if not isinstance(item, dict):
        raise ConfiguracaoInvalida(f"cada nó tem de ser um objeto, veio {item!r}")
    return NoDoCluster(id=_exigir(item, "id", str),
                       endereco=_exigir(item, "endereco", str),
                       porta=_exigir(item, "porta", int))


def _exigir(bruto: dict, campo: str, tipo: type):
    if campo not in bruto:
        raise ConfiguracaoInvalida(f"falta o campo {campo!r} na configuração")
    valor = bruto[campo]
    # bool é subclasse de int em Python: sem esta linha, "porta": true passaria.
    if isinstance(valor, bool) or not isinstance(valor, tipo):
        raise ConfiguracaoInvalida(
            f"o campo {campo!r} tem de ser {tipo.__name__}, veio {valor!r}")
    return valor
