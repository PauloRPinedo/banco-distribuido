"""A sessão de ensaio: só um operador injeta falhas de cada vez.

O problema que resolve é concreto. Na demonstração há dois laptops e três
pessoas, e todas têm o CLI. Se dois operadores derrubam nós ao mesmo tempo, o
cluster perde a maioria por uma razão que ninguém queria, e o que se vê no ecrã
deixa de ser a experiência que se estava a fazer — passa a ser um acidente que
ainda por cima parece um erro do protocolo.

**É um *lease*, não consenso.** Vive no primário, em memória, e viaja para as
réplicas montada no heartbeat. Não entra no log, e a decisão é deliberada: o log
é a pista de auditoria do dinheiro. Meter ali estado operativo faria os índices
correrem e sujaria o extrato das contas com eventos que não são operações
bancárias.

**Morre com o primário, e ainda bem.** Quem tem a sessão tomada é exatamente quem
acabou de matar o primário; voltar a tomá-la é um comando. A caducidade existe
para o outro caso, o do operador que a toma e vai almoçar.
"""

import threading
import time
import uuid
from dataclasses import dataclass

from banco.dominio.erros import ErroDoBanco

DURACAO_POR_OMISSAO_S = 300


class EnsaioTomado(ErroDoBanco):
    """Outro operador tem a sessão (409).

    Herda de `ErroDoBanco` para a camada HTTP a traduzir no mesmo sítio que todas
    as outras recusas. Traz o dono e quanto falta porque a terceira linha da
    mensagem de erro — a do passo seguinte — precisa dos dois: "espere 3 min, ou
    peça ao cristhian" é acionável; "recusado" não é.
    """

    codigo = "ensaio_tomado"
    estado_http = 409

    def __init__(self, dono: str, falta_s: float) -> None:
        falta = max(0, round(falta_s))
        super().__init__(
            f"{dono} tem a sessão de ensaio; expira dentro de {falta} s")
        self.dono = dono
        self.falta_s = falta_s

    def para_json(self) -> dict[str, str]:
        corpo = super().para_json()
        corpo["dono"] = self.dono
        corpo["falta_s"] = str(max(0, round(self.falta_s)))
        return corpo


@dataclass
class TrancaDeEnsaio:
    dono: str | None = None
    fixacao: str | None = None
    expira_em: float = 0.0

    def __post_init__(self) -> None:
        self._lock = threading.Lock()

    # ------------------------------------------------------------ operações

    def tomar(self, dono: str, duracao_s: int = DURACAO_POR_OMISSAO_S) -> str:
        """Devolve a fixação, que é a prova de posse. Levanta se já está tomada.

        Tomar de novo sendo já o dono renova: é o que acontece quando alguém
        repete o comando, e recusar aí seria dizer "não podes porque és tu".
        """
        with self._lock:
            if self._tomada_por_outro(dono):
                raise EnsaioTomado(self.dono, self.expira_em - time.time())
            self.dono = dono
            self.fixacao = uuid.uuid4().hex
            self.expira_em = time.time() + duracao_s
            return self.fixacao

    def renovar(self, fixacao: str,
                duracao_s: int = DURACAO_POR_OMISSAO_S) -> bool:
        """Empurra a caducidade. Cada falha injetada renova sozinha."""
        with self._lock:
            if not self._valida(fixacao):
                return False
            self.expira_em = time.time() + duracao_s
            return True

    def largar(self, fixacao: str) -> bool:
        with self._lock:
            if not self._valida(fixacao):
                return False
            self.dono = None
            self.fixacao = None
            self.expira_em = 0.0
            return True

    def verificar(self, fixacao: str | None) -> None:
        """Deixa passar quem tem a sessão. Levanta para todos os outros.

        Com a sessão livre, deixa passar qualquer um: exigir que se tome a
        sessão para uma única experiência seria burocracia sem ganho, e a
        exclusão só importa quando há mais do que um operador a mexer.
        """
        with self._lock:
            if self.dono is None or self._caducou():
                return
            if fixacao and fixacao == self.fixacao:
                return
            raise EnsaioTomado(self.dono, self.expira_em - time.time())

    # -------------------------------------------------------------- estado

    def em_json(self) -> dict:
        """O que se mostra a quem pergunta. Sem a fixação."""
        with self._lock:
            if self.dono is None or self._caducou():
                return {"tomado": False}
            return {"tomado": True, "dono": self.dono,
                    "falta_s": round(self.expira_em - time.time(), 1)}

    def para_replicas(self) -> dict:
        """O que viaja no heartbeat. **Com** a fixação.

        A fixação tem de chegar às réplicas, e a razão é prática: as falhas
        injetam-se num nó concreto — `falha derrubar --no C` fala com o C — e o C
        precisa de saber se quem lhe está a falar é o dono da sessão. Sem a
        fixação, uma réplica sabe que alguém tem a sessão mas não consegue
        reconhecer ninguém, e recusa toda a gente, incluindo o dono.

        Não há aqui um segredo a proteger: quem alcança `/admin/falha` já pode
        derrubar o nó, e o projeto não tem autenticação nenhuma por decisão da
        proposta. A fixação evita enganos entre colegas, não ataques.
        """
        with self._lock:
            if self.dono is None or self._caducou():
                return {"tomado": False}
            return {"tomado": True, "dono": self.dono, "fixacao": self.fixacao,
                    "falta_s": round(self.expira_em - time.time(), 1)}

    def adotar(self, estado: dict | None) -> None:
        """Aceita o estado que veio do líder no heartbeat."""
        with self._lock:
            if not estado or not estado.get("tomado"):
                self.dono = None
                self.fixacao = None
                self.expira_em = 0.0
                return
            self.dono = estado["dono"]
            self.fixacao = estado.get("fixacao")
            self.expira_em = time.time() + float(estado.get("falta_s", 0))

    # -------------------------------------------------------------- dentro

    def _tomada_por_outro(self, dono: str) -> bool:
        return (self.dono is not None and self.dono != dono
                and not self._caducou())

    def _valida(self, fixacao: str | None) -> bool:
        return (bool(fixacao) and fixacao == self.fixacao
                and not self._caducou())

    def _caducou(self) -> bool:
        return time.time() >= self.expira_em
