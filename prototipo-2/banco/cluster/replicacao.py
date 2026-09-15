"""Replicação, heartbeat e condução da eleição (docs/SPECS.md 7 e 8).

Este módulo é o lado **ativo** do protocolo: o que fala com os outros nós. O lado
passivo — o que responde — está em `interface/rotas_internas`, e o estado vive no
`LogDeReplicacao` e na `Eleicao`.

Um único RPC serve de replicação e de heartbeat, como manda a secção 7. Não é
economia: um segundo caminho de código para o heartbeat divergiria do primeiro, e
o dia em que divergisse seria o dia em que o `epoch` ou o `commit_lider` chegariam
errados a uma réplica, sem ninguém dar por isso.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from banco.cluster.configuracao import ConfiguracaoDoCluster
from banco.cluster.eleicao import Eleicao
from banco.cluster.log_de_replicacao import LogDeReplicacao
from banco.interface.cliente_interno import pedir_ao_no
from banco.persistencia.entrada import EntradaDeLog


class Replicador:

    def __init__(self, id_do_no: str, configuracao: ConfiguracaoDoCluster,
                 log: LogDeReplicacao, eleicao: Eleicao,
                 ao_assumir=None, falhas=None, ensaio=None) -> None:
        self.id = id_do_no
        self.configuracao = configuracao
        self.log = log
        self.eleicao = eleicao
        # Chamada quando este nó ganha uma eleição, para gravar a `noop` do
        # próprio epoch (SPECS 8.4). O `No` fornece-a; este módulo não sabe o que
        # é uma operação.
        self._ao_assumir = ao_assumir
        # Sem injetor, o nó fala com toda a gente: é o caso normal, e é o que os
        # testes que não estudam falhas querem.
        self.falhas = falhas
        self.ensaio = ensaio

        self._pares = configuracao.pares_de(id_do_no)
        # Um trabalhador por par: nunca são mais do que dois neste projeto, e um
        # pool sem limite deixaria um nó lento acumular threads durante uma
        # partição de rede.
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, len(self._pares)),
            thread_name_prefix=f"replicar-{id_do_no}")
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        self._ultimo_contacto_com_maioria = time.monotonic()

    # --------------------------------------------------------- ciclo de vida

    def arrancar(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._ciclo, daemon=True,
                                        name=f"cluster-{self.id}")
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        self._executor.shutdown(wait=False)

    # -------------------------------------------------------------- escrita

    def replicar(self, entrada: EntradaDeLog, prazo_ms: int) -> bool:
        """Envia a entrada aos pares e espera pela maioria.

        O primário conta-se a si próprio: com 3 nós a maioria é 2, ou seja ele e
        uma réplica. Devolve True se a maioria confirmou dentro do prazo.
        """
        return self._difundir([entrada], prazo_ms)

    def bater_coracao(self) -> None:
        """Um heartbeat é o mesmo RPC sem entradas (SPECS 7)."""
        self._difundir([], self.configuracao.timeout_replicacao_ms)

    def _difundir(self, entradas: list[EntradaDeLog], prazo_ms: int) -> bool:
        if not self._pares:
            # Nó sozinho no cluster: a maioria de 1 é ele próprio. Acontece nos
            # testes e num laptop a preparar a demonstração.
            self._ultimo_contacto_com_maioria = time.monotonic()
            return True

        indice_anterior = (entradas[0].indice - 1 if entradas
                           else self.log.ultimo_indice)
        epoch_anterior = self.log.epoch_em(indice_anterior)
        corpo = {"epoch": self.eleicao.epoch, "id_lider": self.id,
                 "indice_anterior": indice_anterior,
                 "epoch_anterior": epoch_anterior,
                 "entradas": [_entrada_em_json(e) for e in entradas],
                 "commit_lider": self.log.indice_commit,
                 # A sessão de ensaio viaja no heartbeat, e não no log: o log é a
                 # pista de auditoria do dinheiro (ver cluster/ensaio.py).
                 "ensaio": self.ensaio.para_replicas() if self.ensaio else None}

        try:
            futuros = [self._executor.submit(self._enviar, par, corpo, prazo_ms)
                       for par in self._pares]
        except RuntimeError:
            # O nó está a ser desligado a meio de uma escrita. Não há maioria
            # nenhuma a esperar, e quem chamou recebe `sem_quorum` — que é a
            # verdade. Deixar o RuntimeError subir daria um 500 "erro interno"
            # quando o que houve foi um nó a fechar ordenadamente.
            return False
        # O primário já se conta a si próprio.
        confirmacoes = 1
        for futuro in futuros:
            try:
                if futuro.result(timeout=prazo_ms / 1000 + 0.5):
                    confirmacoes += 1
            except Exception:  # noqa: BLE001
                # Um par que falha não é um erro do primário: é um voto a menos.
                # Deixar a exceção subir mataria a escrita por causa de um nó em
                # baixo, que é exatamente o que o quórum existe para evitar.
                continue

        alcancou = confirmacoes >= self.configuracao.maioria
        if alcancou:
            self._ultimo_contacto_com_maioria = time.monotonic()
        return alcancou

    def _enviar(self, par, corpo: dict, prazo_ms: int) -> bool:
        if self.falhas is not None and not self.falhas.fala_com(par.id):
            return False
        resposta = pedir_ao_no(par, "/interno/replicar", corpo, prazo_ms)
        if not resposta.respondeu or not resposta.corpo:
            return False
        if resposta.corpo.get("epoch", 0) > self.eleicao.epoch:
            # Fencing: vi um epoch maior, já não mando (SPECS 8.3).
            self.eleicao.ver_epoch(resposta.corpo["epoch"])
            return False
        if resposta.corpo.get("ok"):
            return True
        # Log divergente ou com um buraco: a réplica diz onde está, e reenvia-se
        # daí. É a simplificação face ao Raft registada na secção 7.
        em_falta = resposta.corpo.get("meu_ultimo_indice")
        if em_falta is None:
            return False
        return self._pôr_em_dia(par, em_falta, prazo_ms)

    def _pôr_em_dia(self, par, ultimo_indice_do_par: int, prazo_ms: int) -> bool:
        atrasadas = self.log.ler_desde(ultimo_indice_do_par)
        if not atrasadas:
            return False
        anterior = ultimo_indice_do_par
        corpo = {"epoch": self.eleicao.epoch, "id_lider": self.id,
                 "indice_anterior": anterior,
                 "epoch_anterior": self.log.epoch_em(anterior),
                 "entradas": [_entrada_em_json(e) for e in atrasadas],
                 "commit_lider": self.log.indice_commit}
        resposta = pedir_ao_no(par, "/interno/replicar", corpo, prazo_ms)
        return bool(resposta.respondeu and resposta.corpo
                    and resposta.corpo.get("ok"))

    # -------------------------------------------------------------- leitura

    def vejo_a_maioria(self) -> bool:
        """Falei com a maioria há menos de um timeout de eleição?

        Se não, o primário passa a somente leitura de imediato, em vez de
        acumular operações que nunca serão confirmadas (SPECS 7).
        """
        if not self._pares:
            return True
        limite = self.configuracao.timeout_eleicao_ms[0] / 1000
        return time.monotonic() - self._ultimo_contacto_com_maioria < limite

    # --------------------------------------------------------------- eleição

    def _ciclo(self) -> None:
        """Bate o coração se manda, conta o tempo se não manda."""
        intervalo = self.configuracao.heartbeat_ms / 1000
        while not self._parar.wait(intervalo):
            try:
                if self.eleicao.sou_primario():
                    self.bater_coracao()
                elif self.eleicao.timeout_expirou():
                    self._concorrer()
            except Exception:  # noqa: BLE001
                # O ciclo não pode morrer: se esta thread cai, o nó deixa de
                # bater o coração e o cluster elege outro primário sem motivo.
                continue

    def _concorrer(self) -> None:
        pedido = self.eleicao.candidatar(self.log.ultimo_indice,
                                         self.log.ultimo_epoch)
        if pedido is None:
            return

        corpo = {"epoch": pedido.epoch, "id_candidato": pedido.id_candidato,
                 "ultimo_indice": pedido.ultimo_indice,
                 "ultimo_epoch": pedido.ultimo_epoch}
        prazo = self.configuracao.timeout_replicacao_ms

        # Vota em si próprio.
        votos = 1
        try:
            futuros = [self._executor.submit(self._pedir_voto, par, corpo, prazo)
                       for par in self._pares]
        except RuntimeError:
            return
        for futuro in futuros:
            try:
                if futuro.result(timeout=prazo / 1000 + 0.5):
                    votos += 1
            except Exception:  # noqa: BLE001
                continue

        if votos >= self.configuracao.maioria and self.eleicao.assumir(pedido.epoch):
            self._ultimo_contacto_com_maioria = time.monotonic()
            if self._ao_assumir is not None:
                self._ao_assumir()
            # Heartbeat imediato, para calar candidatos concorrentes (SPECS 8.4).
            self.bater_coracao()

    def _pedir_voto(self, par, corpo: dict, prazo_ms: int) -> bool:
        if self.falhas is not None and not self.falhas.fala_com(par.id):
            return False
        resposta = pedir_ao_no(par, "/interno/votar", corpo, prazo_ms)
        if not resposta.respondeu or not resposta.corpo:
            return False
        if resposta.corpo.get("epoch", 0) > corpo["epoch"]:
            self.eleicao.ver_epoch(resposta.corpo["epoch"])
            return False
        return bool(resposta.corpo.get("concedido"))


def _entrada_em_json(entrada: EntradaDeLog) -> dict:
    return {"indice": entrada.indice, "epoch": entrada.epoch,
            "op_id": entrada.op_id, "tipo": entrada.tipo,
            "dados": entrada.dados, "instante": entrada.instante}

