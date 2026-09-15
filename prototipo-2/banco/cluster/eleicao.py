"""Papel do nó, epoch e voto (docs/SPECS.md secção 8).

Guarda o estado de quem manda, e só isso. Não fala com a rede: quem envia pedidos
de voto é o `Replicador`. A separação existe por uma razão concreta de correção —
o pedido de voto que chega tem de poder ser respondido **enquanto** uma escrita
espera pela maioria. Se os dois partilhassem o lock do estado do banco, um
primário atascado sem quórum bloquearia a eleição que resolveria o atasco.

Daí este módulo ter o seu próprio lock, e a regra que o acompanha: nunca se toma o
lock do estado do banco tendo este. O contrário pode.
"""

import random
import threading
import time
from dataclasses import dataclass

REPLICA = "réplica"
CANDIDATO = "candidato"
PRIMARIO = "primário"


@dataclass(frozen=True)
class PedidoDeVoto:
    epoch: int
    id_candidato: str
    ultimo_indice: int
    ultimo_epoch: int


class Eleicao:

    def __init__(self, id_do_no: str, semente: int,
                 intervalo_ms: tuple[int, int], epoch_inicial: int = 1,
                 votou_em: str | None = None) -> None:
        self.id = id_do_no
        self._lock = threading.Lock()
        self._papel = REPLICA
        self._epoch = epoch_inicial
        self._votou_em = votou_em
        self._lider_conhecido: str | None = None
        self._visto_em = time.monotonic()

        # Gerador próprio, com semente própria. Não se usa o `random` global:
        # partilhá-lo faria a sequência de um nó depender de quantas vezes outro
        # código sorteou, e RNF-06 exige que a mesma semente dê a mesma execução.
        self._sorteio = random.Random(semente)
        self._intervalo_ms = intervalo_ms
        self._timeout_s = self._sortear()

    # ------------------------------------------------------------- o que sou

    @property
    def papel(self) -> str:
        with self._lock:
            return self._papel

    @property
    def epoch(self) -> int:
        with self._lock:
            return self._epoch

    @property
    def votou_em(self) -> str | None:
        with self._lock:
            return self._votou_em

    @property
    def lider_conhecido(self) -> str | None:
        with self._lock:
            return self._lider_conhecido

    def sou_primario(self) -> bool:
        with self._lock:
            return self._papel == PRIMARIO

    def timeout_expirou(self) -> bool:
        with self._lock:
            if self._papel == PRIMARIO:
                return False
            return time.monotonic() - self._visto_em >= self._timeout_s

    def silencio_ha(self) -> float:
        with self._lock:
            return time.monotonic() - self._visto_em

    # ---------------------------------------------------------- o que muda

    def vi_o_lider(self, id_do_lider: str, epoch: int) -> None:
        """Chegou um heartbeat válido: reinicia o relógio e aceita o líder."""
        with self._lock:
            self._visto_em = time.monotonic()
            self._lider_conhecido = id_do_lider
            if epoch > self._epoch:
                self._epoch = epoch
                self._votou_em = None
            if self._papel != REPLICA:
                self._papel = REPLICA
                self._timeout_s = self._sortear()

    def ver_epoch(self, epoch: int) -> bool:
        """O *fencing* da secção 8.3: um epoch maior despromove sempre.

        Devolve True se houve despromoção, para quem chama poder gravar o estado
        novo. Um primário antigo que volta de uma pausa descobre aqui que já não
        manda, e nunca chega a confirmar nada.
        """
        with self._lock:
            if epoch <= self._epoch:
                return False
            self._epoch = epoch
            self._votou_em = None
            despromovido = self._papel != REPLICA
            self._papel = REPLICA
            self._visto_em = time.monotonic()
            self._timeout_s = self._sortear()
            return despromovido

    def candidatar(self, ultimo_indice: int,
                   ultimo_epoch: int) -> PedidoDeVoto | None:
        """Sobe o epoch, vota em si e devolve o pedido a enviar aos pares.

        Recebe o estado do log em vez de o ir buscar: este módulo não conhece o
        log, e é essa ignorância que o mantém testável sem armazém nenhum.
        """
        with self._lock:
            if self._papel == PRIMARIO:
                return None
            self._epoch += 1
            self._papel = CANDIDATO
            self._votou_em = self.id
            self._visto_em = time.monotonic()
            self._timeout_s = self._sortear()
            return PedidoDeVoto(self._epoch, self.id, ultimo_indice, ultimo_epoch)

    def assumir(self, epoch: int) -> bool:
        """Ganhou a eleição nesse epoch. Falha se o epoch já mudou.

        A verificação não é paranoia: entre pedir os votos e contá-los pode ter
        chegado um epoch maior, e assumir aí criaria o segundo primário que todo
        este desenho existe para impedir.
        """
        with self._lock:
            if self._epoch != epoch or self._papel != CANDIDATO:
                return False
            self._papel = PRIMARIO
            self._lider_conhecido = self.id
            return True

    def conceder_voto(self, pedido: PedidoDeVoto, ultimo_indice: int,
                      ultimo_epoch: int) -> tuple[bool, str]:
        """As três condições da secção 8.2. Devolve também o motivo.

        O motivo não é um luxo: depurar uma eleição que não converge sem saber
        **qual** das três condições falhou é adivinhar. O CODESTYLE secção 10
        exige-o no log estruturado, e é aqui que ele nasce.
        """
        with self._lock:
            if pedido.epoch < self._epoch:
                return False, (f"epoch {pedido.epoch} menor que o meu "
                               f"{self._epoch}")

            if pedido.epoch > self._epoch:
                # Epoch novo: esqueço o voto anterior, que era de outra ronda.
                self._epoch = pedido.epoch
                self._votou_em = None
                self._papel = REPLICA

            if self._votou_em not in (None, pedido.id_candidato):
                return False, (f"já votei em {self._votou_em} no epoch "
                               f"{self._epoch}")

            # Condição 3: o log do candidato tem de estar pelo menos tão
            # atualizado quanto o meu. É isto que garante que nada confirmado se
            # perde — a demonstração está na secção 8.2 do SPECS.
            meu = (ultimo_epoch, ultimo_indice)
            dele = (pedido.ultimo_epoch, pedido.ultimo_indice)
            if dele < meu:
                return False, (f"log atrasado: ele tem {dele}, eu tenho {meu}")

            self._votou_em = pedido.id_candidato
            self._visto_em = time.monotonic()
            return True, "concedido"

    def _sortear(self) -> float:
        minimo, maximo = self._intervalo_ms
        return self._sorteio.randint(minimo, maximo) / 1000
