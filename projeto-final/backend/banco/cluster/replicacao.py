"""Replicação, heartbeat e condução da eleição.

Este módulo é o lado **ativo** do protocolo: o que fala com os outros nós. O lado
passivo — o que responde — está em `No.replicar` e `No.votar`, e o estado vive no
`LogDeReplicacao` e na `Eleicao`.

Um único RPC serve de replicação e de heartbeat. Não é
economia: um segundo caminho de código para o heartbeat divergiria do primeiro, e
o dia em que divergisse seria o dia em que o `epoch` ou o `commit_lider` chegariam
errados a uma réplica, sem ninguém dar por isso.
"""

import threading
import time
from concurrent.futures import (FIRST_COMPLETED, Future, ThreadPoolExecutor,
                                wait)

from banco.cluster.configuracao import ConfiguracaoDoCluster
from banco.cluster.eleicao import Eleicao
from banco.cluster.log_de_replicacao import LogDeReplicacao
from banco.cluster.cliente_interno import pedir_ao_no
from banco.cluster.entrada import EntradaDeLog

# Quantas entradas leva um envio a um par, no máximo. Um nó que esteve muito
# tempo em baixo recebe o que lhe falta em vários.
MAXIMO_POR_ENVIO = 500


class Replicador:

    def __init__(self, id_do_no: str, configuracao: ConfiguracaoDoCluster,
                 log: LogDeReplicacao, eleicao: Eleicao,
                 ao_assumir=None, falhas=None, ao_bater=None) -> None:
        self.id = id_do_no
        self.configuracao = configuracao
        self.log = log
        self.eleicao = eleicao
        # Chamada quando este nó ganha uma eleição, para gravar a `noop` do
        # próprio epoch. O `No` fornece-a; este módulo não sabe o que
        # é uma operação.
        self._ao_assumir = ao_assumir
        # Chamada depois de cada heartbeat do primário: o `No` usa-a para
        # voltar a confirmar a `noop` se a primeira ronda não teve maioria.
        self._ao_bater = ao_bater
        # Sem injetor, o nó fala com toda a gente: é o caso normal, e é o que os
        # testes que não estudam falhas querem.
        self.falhas = falhas

        self._pares = configuracao.pares_de(id_do_no)
        # Os pedidos de voto: um trabalhador por par, à parte da replicação,
        # para uma eleição nunca esperar atrás de um envio a um nó morto.
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, len(self._pares)),
            thread_name_prefix=f"votar-{id_do_no}")
        # A replicação: um canal por par, com um só trabalhador. Os envios a um
        # par saem por ordem, e um par lento só atrasa o seu próprio canal.
        self._canais = {par.id: _Canal(par, id_do_no) for par in self._pares}
        # Até onde cada par tem o log igual ao deste nó (o `matchIndex` do
        # Raft). Esquece-se a cada mandato novo.
        self._confirmados: dict[str, int] = {}
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
        for canal in self._canais.values():
            canal.fechar()

    # -------------------------------------------------------------- escrita

    def replicar(self, entrada: EntradaDeLog, prazo_ms: int) -> bool:
        """Envia a entrada aos pares e espera pela maioria.

        O primário conta-se a si próprio: com 3 nós a maioria é 2, ou seja ele e
        uma réplica. Devolve True se a maioria confirmou dentro do prazo.
        """
        return self._difundir([entrada], prazo_ms)

    def replicar_lote(self, entradas: list[EntradaDeLog], prazo_ms: int) -> bool:
        """Várias entradas seguidas numa só ronda: é o que junta as escritas
        que chegam ao mesmo tempo. A maioria confirma o lote inteiro."""
        return self._difundir(entradas, prazo_ms)

    def bater_coracao(self) -> None:
        """Um heartbeat é o mesmo RPC sem entradas."""
        self._difundir([], self.configuracao.timeout_replicacao_ms)

    def _difundir(self, entradas: list[EntradaDeLog], prazo_ms: int) -> bool:
        """Põe cada par em dia até à última de `entradas` e espera pela maioria.

        Sem entradas é um heartbeat: basta que a maioria responda que sim.
        """
        if not self._pares:
            # Nó sozinho no cluster: a maioria de 1 é ele próprio.
            self._ultimo_contacto_com_maioria = time.monotonic()
            return True

        alvo = entradas[-1].indice if entradas else 0
        futuros = [canal.enviar(lambda par: self._sincronizar(par, prazo_ms))
                   for canal in self._canais.values()]
        futuros = [futuro for futuro in futuros if futuro is not None]
        # O primário já se conta a si próprio. Responde-se logo que a maioria
        # confirma: esperar pelo par mais lento atrasaria todas as escritas
        # pelo nó mais lento do cluster, que é o contrário de ter um quórum.
        confirmacoes = 1
        prazo = time.monotonic() + prazo_ms / 1000 + 0.5
        por_ver = set(futuros)
        while confirmacoes < self.configuracao.maioria and por_ver:
            restante = prazo - time.monotonic()
            if restante <= 0:
                break
            feitos, por_ver = wait(por_ver, timeout=restante, return_when=FIRST_COMPLETED)
            for futuro in feitos:
                try:
                    confirmado = futuro.result()
                except Exception:  # noqa: BLE001
                    # Um par que falha não é um erro do primário: é um voto a
                    # menos. Deixar a exceção subir mataria a escrita por causa
                    # de um nó em baixo, que é o que o quórum existe para evitar.
                    continue
                if confirmado is not None and confirmado >= alvo:
                    confirmacoes += 1

        alcancou = confirmacoes >= self.configuracao.maioria
        if alcancou:
            self._ultimo_contacto_com_maioria = time.monotonic()
        return alcancou

    def _sincronizar(self, par, prazo_ms: int) -> int | None:
        """Manda ao par o que lhe falta; devolve até onde ele confirmou, ou None.

        Corre no canal do par, e monta a mensagem **agora**, não quando foi
        posta na fila: leva tudo o que o log tem neste instante. Por isso uma
        ronda que encontra um envio à espera junta-se a ele em vez de mandar
        outro.

        `_confirmados[par]` é até onde o par já tem o log igual ao deste nó.
        Sem esse número (acabado de ganhar a eleição), parte-se do commit; se o
        par diz que não encaixa, diz também onde está, e repete-se daí.
        """
        if self.falhas is not None and not self.falhas.fala_com(par.id):
            return None
        fim = time.monotonic() + prazo_ms / 1000
        alvo = self.log.ultimo_indice
        for _ in range(8):
            restante_ms = int((fim - time.monotonic()) * 1000)
            if restante_ms <= 0:
                return None
            anterior = self._confirmados.get(par.id)
            if anterior is None:
                anterior = self.log.indice_commit
            entradas = self.log.ler_desde(anterior, MAXIMO_POR_ENVIO)
            corpo = {"epoch": self.eleicao.epoch, "id_lider": self.id,
                     "indice_anterior": anterior,
                     "epoch_anterior": self.log.epoch_em(anterior),
                     "entradas": [_entrada_em_json(e) for e in entradas],
                     "commit_lider": self.log.indice_commit}
            resposta = pedir_ao_no(par, "/interno/replicar", corpo, restante_ms)
            if not resposta.respondeu or not resposta.corpo:
                return None
            if resposta.corpo.get("epoch", 0) > self.eleicao.epoch:
                # Fencing: vi um epoch maior, já não mando.
                self.eleicao.ver_epoch(resposta.corpo["epoch"])
                return None
            if resposta.corpo.get("ok"):
                confirmado = anterior + len(entradas)
                self._confirmados[par.id] = confirmado
                if confirmado >= alvo or not entradas:
                    return confirmado
                continue   # havia mais do que cabe num envio
            # Log divergente ou com um buraco: a réplica diz até onde tem a
            # certeza (o seu commit), e reenvia-se daí. É a simplificação face
            # ao Raft, que recua uma entrada de cada vez.
            onde_esta = resposta.corpo.get("meu_ultimo_indice")
            if onde_esta is None or onde_esta >= anterior:
                return None
            self._confirmados[par.id] = onde_esta
        return None

    # -------------------------------------------------------------- leitura

    def ms_desde_a_maioria(self) -> int:
        return int((time.monotonic() - self._ultimo_contacto_com_maioria) * 1000)

    def vejo_a_maioria(self) -> bool:
        """Falei com a maioria há menos de um timeout de eleição?

        Se não, o primário passa a somente leitura de imediato, em vez de
        acumular operações que nunca serão confirmadas.
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
                    if self._ao_bater is not None:
                        self._ao_bater()
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
            self._confirmados = {}
            if self._ao_assumir is not None:
                self._ao_assumir()
            # Heartbeat imediato, para calar candidatos concorrentes.
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


class _Canal:
    """Os envios de replicação a um par: um de cada vez, e no máximo um à espera.

    Um de cada vez porque a réplica deve receber as mensagens deste líder pela
    ordem em que ele as manda. No máximo um à espera porque a mensagem só se
    monta quando sai (`_sincronizar`): quem chega com um envio já à espera
    junta-se a ele, e esse envio leva também o que essa ronda queria mandar.
    Com um par em baixo, a fila nunca cresce.
    """

    def __init__(self, par, id_do_no: str) -> None:
        self.par = par
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix=f"replicar-{id_do_no}-{par.id}")
        self._lock = threading.Lock()
        self._a_espera: Future | None = None

    def enviar(self, funcao) -> Future | None:
        """O futuro do envio que vai levar o que está no log agora."""
        with self._lock:
            if self._a_espera is not None:
                return self._a_espera
            try:
                futuro = self._executor.submit(self._correr, funcao)
            except RuntimeError:
                # O nó está a ser desligado: este par não conta, e quem chamou
                # recebe `sem_quorum` em vez de um 500.
                return None
            self._a_espera = futuro
            return futuro

    def _correr(self, funcao):
        # A partir daqui o envio já não está à espera: quem chegar depois
        # precisa de outro, porque este pode já ter lido o log.
        with self._lock:
            self._a_espera = None
        return funcao(self.par)

    def fechar(self) -> None:
        self._executor.shutdown(wait=False)


def _entrada_em_json(entrada: EntradaDeLog) -> dict:
    return {"indice": entrada.indice, "epoch": entrada.epoch,
            "op_id": entrada.op_id, "tipo": entrada.tipo,
            "dados": entrada.dados, "instante": entrada.instante}

