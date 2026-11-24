"""O nó do cluster: junta a eleição, o log replicado e o aplicador.

Uma regra organiza tudo: **o estado de um nó (as tabelas `conta`, `operacao`,
`usuario`, `taxa_cambio`) é o resultado de aplicar, por ordem de índice, as
entradas confirmadas do log.** O primário e as réplicas aplicam com a mesma
função (`Aplicador.aplicar`), por isso três nós com o mesmo log confirmado têm
as mesmas tabelas.

Sem configuração de cluster, o nó é um banco de um nó só: manda sempre, e uma
entrada durável está confirmada no instante em que é gravada. Com configuração,
arranca **sempre como réplica** e só escreve depois de ganhar uma eleição.

**As escritas no primário, em grupo.** Cada escrita diz que chaves toca (as
contas, o número da conta nova, o email, o op_id). Antes de validar, reserva-as;
se estão reservadas por outra, ou numa entrada ainda por aplicar, espera. Assim
valida-se sempre contra o estado que as escritas anteriores deixam, e escritas
de contas diferentes validam ao mesmo tempo. Só gravar no log é um de cada vez
(é o que dá o índice). Replicar também não: as escritas que chegam juntas vão
na mesma ronda, e a maioria confirma-as todas de uma vez (`_confirmar`), e
aplicam-se numa só transação.

**As réplicas** respondem ao primário logo que gravaram as entradas no log, e
aplicam-nas às tabelas noutra thread. Aplicar antes de responder punha o tempo
de aplicar o lote anterior em todas as escritas.

**Os locks.** A ordem é sempre esta: `_lock_escrita` → `_lock_estado` → `_cond`.

- `_lock_escrita` serializa a gravação no log, para os índices nunca chocarem.
- `_lock_estado` protege o "aplicar até ao commit", que tanto o primário como
  o RPC de replicação chamam.
- `_cond` protege as entradas por aplicar e a ronda de replicação em curso.
- o lock da `Eleicao` é dela; `votar` não toma nenhum dos dois de cima, porque
  um pedido de voto tem de ser respondido **enquanto** uma escrita espera pela
  maioria — é precisamente nessa situação que a eleição faz falta.
"""

import logging
import threading
import time

from banco.cluster.configuracao import ConfiguracaoDoCluster
from banco.cluster.eleicao import Eleicao, PedidoDeVoto
from banco.cluster.entrada import EntradaDeLog
from banco.cluster.erros import (NaoSouPrimario, ParticaoSimulada, SemQuorum,
                                 SomenteLeitura)
from banco.cluster.falhas import InjetorDeFalhas
from banco.cluster.log_de_replicacao import LogDeReplicacao
from banco.cluster.operacoes_de_sistema import Noop
from banco.cluster.replicacao import Replicador
from banco.cluster.vista import ver_cluster
from banco.dominio.erros import ErroDoBanco
from banco.dominio.operacoes import Operacao

registo = logging.getLogger("banco.cluster")

# Quantas entradas se aplicam numa só transação, no máximo.
LOTE_A_APLICAR = 256


def _chocam(umas, outras) -> bool:
    """Duas escritas com estas chaves têm de ser uma depois da outra?

    `None` são as escritas que não dizem o que tocam: chocam com todas.
    """
    return umas is None or outras is None or bool(umas & outras)


class No:

    def __init__(self, identificador: str, armazem, aplicador,
                 configuracao: ConfiguracaoDoCluster | None = None) -> None:
        self.id = identificador
        self.armazem = armazem
        self.aplicador = aplicador
        self.configuracao = configuracao
        self.falhas = InjetorDeFalhas()

        self._lock_escrita = threading.Lock()
        self._lock_estado = threading.RLock()
        self._cond = threading.Condition()
        # A thread que aplica, nas réplicas, o que chega do primário.
        self._aplicadora: threading.Thread | None = None
        self._ha_para_aplicar = threading.Event()
        self._fechado = threading.Event()
        self._construir()

    def _construir(self) -> None:
        """Lê o que está no armazém e monta o log, a eleição e o replicador."""
        self.log = LogDeReplicacao(self.armazem)
        self._ultimo_aplicado = self.aplicador.ultimo_aplicado()
        # (epoch, índice) da `noop` que este nó gravou ao ganhar a última
        # eleição. Está pronto quando ela está confirmada e aplicada — e com
        # ela tudo o que o primário anterior confirmou. Antes disso, uma
        # leitura a este nó podia não ver uma escrita já prometida a um cliente.
        self._noop_do_mandato: tuple[int, int] | None = None
        # As entradas deste primário ainda por aplicar, com as chaves que tocam.
        self._pendentes: dict[int, frozenset | None] = {}
        # As chaves das escritas que estão a validar, ainda sem índice.
        self._reservas: dict[object, frozenset | None] = {}
        # A ronda de replicação em curso; só há uma de cada vez.
        self._ronda: _Ronda | None = None
        # As respostas das entradas aplicadas, para as escritas que esperam por elas.
        self._aguardados: set[str] = set()
        self._respostas: dict[str, dict] = {}
        if self.configuracao is None:
            self.eleicao = None
            self.replicador = None
            # Sozinho, não há maioria por quem esperar: o que está no log está
            # confirmado.
            self.log.confirmar_ate(self.log.ultimo_indice)
        else:
            estado = self.armazem.ler_estado()
            self.eleicao = Eleicao(self.id,
                                   self.configuracao.semente_do_no(self.id),
                                   self.configuracao.timeout_eleicao_ms,
                                   estado.epoch, estado.votou_em)
            self.replicador = Replicador(self.id, self.configuracao, self.log,
                                         self.eleicao, self._assumir_mandato,
                                         self.falhas, ao_bater=self._tentar_ficar_pronto)
        # Recuperação (RF-12): o que ficou confirmado e por aplicar quando o
        # processo caiu aplica-se agora, antes de responder a quem quer que seja.
        with self._lock_estado:
            self._aplicar_ate_ao_commit()

    def arrancar(self) -> None:
        """Começa a bater o coração e a contar o tempo. Só com cluster."""
        if self.replicador is not None:
            self.replicador.arrancar()

    def fechar(self) -> None:
        self._fechado.set()
        self._ha_para_aplicar.set()
        if self.replicador is not None:
            self.replicador.parar()
        if self._aplicadora is not None:
            self._aplicadora.join(timeout=2)
        self.armazem.fechar()

    def recarregar(self) -> None:
        """Só para os testes: volta a ler tudo do armazém depois de o esvaziarem."""
        with self._lock_escrita, self._lock_estado:
            if self.replicador is not None:
                self.replicador.parar()
            self._construir()
            self.arrancar()

    # ---------------------------------------------------------------- escrita

    def executar(self, op_id: str, operacao: Operacao, verificar=None,
                 chaves=None) -> dict:
        """A ordem de uma escrita no primário.

        `verificar(instante)` é a validação contra o estado atual (o dono das
        contas e as regras do domínio). Corre dentro do lock de escrita, depois
        de aplicadas as entradas que tocam as mesmas `chaves`: valida-se contra
        o estado certo. Sem `chaves`, a escrita espera por todas as entradas
        por aplicar — é o caso seguro, e o das operações de sistema.
        """
        chaves = None if chaves is None else frozenset(chaves) | {f"op:{op_id}"}

        # 0 e 1. Mando? Reservar as chaves, esperando por quem as tenha: uma
        # escrita a validar, ou uma entrada ainda por aplicar.
        reserva = self._reservar(chaves)
        epoch = self.eleicao.epoch if self.eleicao else 1
        try:
            # 2. Já foi aplicada? Devolve-se o guardado.
            guardada = self.aplicador.resposta_guardada(op_id)
            if guardada is not None:
                return guardada

            # 3. Validar antes do log: nunca se grava o que vai ser recusado.
            # O instante decide-se aqui, uma vez, e viaja na entrada.
            instante = time.time()
            if verificar is not None:
                verificar(instante)

            # 4. Gravar de forma durável no log deste nó.
            with self._lock_escrita:
                self._exigir_que_mando()
                if self.eleicao is not None and self.eleicao.epoch != epoch:
                    # Perdeu o mandato e ganhou outro enquanto validava: a
                    # validação foi feita contra um estado que já não é este.
                    raise SemQuorum("o mandato mudou enquanto a operação era validada; "
                                    "nada foi gravado — repetir com o mesmo op_id")
                entrada = EntradaDeLog.de_operacao(
                    self.log.ultimo_indice + 1, op_id, operacao, instante, epoch=epoch)
                self.log.acrescentar(entrada)
                with self._cond:
                    self._pendentes[entrada.indice] = chaves
                    self._aguardados.add(op_id)
        finally:
            with self._cond:
                del self._reservas[reserva]
                self._cond.notify_all()

        # 5 e 6. Replicar (com as outras escritas que chegaram entretanto),
        # esperar pela maioria, confirmar e aplicar às tabelas.
        try:
            self._confirmar(entrada.indice)
        finally:
            with self._cond:
                self._aguardados.discard(op_id)
                resposta = self._respostas.pop(op_id, None)

        # 7. Responder.
        return resposta or self.aplicador.resposta_guardada(op_id) or {}

    def _reservar(self, chaves) -> object:
        """Reserva as chaves desta escrita; devolve a reserva, para a libertar.

        Espera enquanto houver conflito: com uma escrita que está a validar,
        espera que ela grave ou desista; com uma entrada por aplicar, confirma-a
        (ou espera pela ronda que a leva). Enquanto a `noop` do mandato não
        está aplicada, espera-se por ela: antes dela podem estar entradas do
        primário anterior que ninguém aqui conhece.
        """
        while True:
            self._exigir_que_mando()
            with self._cond:
                indice = self._conflito(chaves)
                if indice is None:
                    if any(_chocam(chaves, outras) for outras in self._reservas.values()):
                        self._cond.wait(timeout=0.1)
                        continue
                    reserva = object()
                    self._reservas[reserva] = chaves
                    return reserva
            self._confirmar(indice)

    def _conflito(self, chaves) -> int | None:
        """O índice por aplicar que esta escrita tem de esperar, ou None."""
        with self._cond:
            if self._noop_do_mandato is not None and not self.pronto():
                return self._noop_do_mandato[1]
            em_conflito = [indice for indice, outras in self._pendentes.items()
                           if _chocam(chaves, outras)]
            return max(em_conflito) if em_conflito else None

    def _confirmar(self, indice: int) -> None:
        """Espera até a entrada `indice` estar confirmada e aplicada.

        Se não há uma ronda de replicação em curso, esta thread faz uma, com
        tudo o que está por confirmar; se há, espera por ela. Levanta
        `SemQuorum` se a ronda que levava esta entrada não teve maioria.
        """
        while True:
            with self._cond:
                while True:
                    if self.log.indice_commit >= indice and self._ultimo_aplicado >= indice:
                        return
                    ronda = self._ronda
                    if ronda is None:
                        break
                    self._cond.wait_for(lambda: ronda.feita)
                    if not ronda.ok and indice <= ronda.ate:
                        raise SemQuorum(ronda.motivo)
                ronda = self._ronda = _Ronda()
            try:
                self._correr_ronda(ronda)
            finally:
                with self._cond:
                    ronda.feita = True
                    self._ronda = None
                    for pendente in [i for i in self._pendentes if i <= self._ultimo_aplicado]:
                        del self._pendentes[pendente]
                    self._cond.notify_all()
            if not ronda.ok and indice <= ronda.ate:
                raise SemQuorum(ronda.motivo)

    def _correr_ronda(self, ronda: "_Ronda") -> None:
        """Replica o que está por confirmar, confirma e aplica. Preenche `ronda`."""
        entradas = self.log.ler_desde(self.log.indice_commit)
        ronda.ate = entradas[-1].indice if entradas else self.log.indice_commit
        if entradas:
            if self.replicador is None:
                self.log.confirmar_ate(ronda.ate)
            else:
                prazo = self.configuracao.timeout_replicacao_ms
                if not self.replicador.replicar_lote(entradas, prazo):
                    ronda.motivo = (
                        f"a maioria não confirmou a operação a tempo ({prazo} ms); "
                        f"as entradas até {ronda.ate} ficaram gravadas por confirmar "
                        "— repetir com o mesmo op_id")
                    return
                # Fencing: durante a espera pode ter chegado um epoch maior e
                # este nó já não manda. Confirmar aqui seria confirmar sem mandato.
                if not self.eleicao.sou_primario():
                    ronda.motivo = ("deixei de ser primário enquanto esperava pela "
                                    "maioria; a operação não foi aplicada")
                    return
                self.log.confirmar_ate(ronda.ate)
        # 6. Aplicar às tabelas — este nó e, no envio seguinte, as réplicas.
        with self._lock_estado:
            respostas = self._aplicar_ate_ao_commit()
        with self._cond:
            for op_id, resposta in respostas.items():
                if op_id in self._aguardados:
                    self._respostas[op_id] = resposta
        ronda.ok = True

    def _exigir_que_mando(self) -> None:
        if self.eleicao is None:
            return
        if not self.eleicao.sou_primario():
            raise NaoSouPrimario(
                f"o nó {self.id} não é o primário deste cluster",
                self.url_do_lider())
        if not self.replicador.vejo_a_maioria():
            raise SomenteLeitura(
                f"o nó {self.id} não fala com a maioria há mais de um timeout de "
                f"eleição ({self.replicador.ms_desde_a_maioria()} ms); recusa "
                "escritas e continua a responder a leituras")

    def url_do_lider(self) -> str | None:
        lider = self.eleicao.lider_conhecido if self.eleicao else None
        if not lider or lider == self.id:
            return None
        try:
            return self.configuracao.obter(lider).url
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------- lado das réplicas

    def replicar(self, epoch: int, id_lider: str, indice_anterior: int,
                 epoch_anterior: int, entradas: list[EntradaDeLog],
                 commit_lider: int) -> dict:
        """Atende `/interno/replicar`. Com `entradas` vazio é um heartbeat."""
        if self.eleicao is None:
            return {"ok": False, "epoch": 1,
                    "motivo": "este nó não faz parte de um cluster"}

        if not self.falhas.fala_com(id_lider):
            # Isolado deste nó: a mensagem perde-se, como numa partição real.
            raise ParticaoSimulada(f"o nó {self.id} está isolado de {id_lider}")
        self.falhas.talvez_atrasar()

        if epoch < self.eleicao.epoch:
            # Líder velho. Responder com o meu epoch é o que o despromove.
            return {"ok": False, "epoch": self.eleicao.epoch,
                    "motivo": "epoch do líder é menor que o meu"}

        self.eleicao.vi_o_lider(id_lider, epoch)

        if not self.log.corresponde(indice_anterior, epoch_anterior):
            # O meu log divergiu ou tem um buraco: digo onde estou, e o líder
            # reenvia a partir daí.
            return {"ok": False, "epoch": self.eleicao.epoch,
                    "meu_ultimo_indice": min(self.log.ultimo_indice,
                                             self.log.indice_commit),
                    "motivo": "o log não corresponde"}

        with self._lock_estado:
            if entradas:
                self.log.acrescentar_do_lider(entradas)
            self.log.confirmar_ate(commit_lider)
        # Aplicar fica para a thread de aplicação: o primário só precisa de
        # saber que as entradas estão gravadas.
        self._aplicar_em_fundo()

        return {"ok": True, "epoch": self.eleicao.epoch,
                "indice_correspondente": self.log.ultimo_indice}

    def votar(self, pedido: PedidoDeVoto) -> dict:
        """Atende `/interno/votar`. Não toma os locks do nó — ver o cabeçalho."""
        if self.eleicao is None:
            return {"concedido": False, "epoch": 1,
                    "motivo": "este nó não faz parte de um cluster"}

        if not self.falhas.fala_com(pedido.id_candidato):
            raise ParticaoSimulada(
                f"o nó {self.id} está isolado de {pedido.id_candidato}")
        self.falhas.talvez_atrasar()

        concedido, motivo = self.eleicao.conceder_voto(
            pedido, self.log.ultimo_indice, self.log.ultimo_epoch)
        # O voto é durável **antes** de a resposta sair: um nó que vota, cai e
        # esquece o voto votaria outra vez no mesmo epoch.
        self.armazem.gravar_estado(self.eleicao.epoch, self.eleicao.votou_em)
        registo.info("nó %s: voto em %s no epoch %s: %s", self.id,
                     pedido.id_candidato, pedido.epoch, motivo)
        return {"concedido": concedido, "epoch": self.eleicao.epoch,
                "motivo": motivo}

    def _assumir_mandato(self) -> None:
        """Chamado pelo replicador ao ganhar uma eleição: grava a `noop` do epoch.

        Grava-a com o lock de escrita: entre ganhar e gravar a `noop` não pode
        entrar nenhuma escrita de cliente, ou os índices chocariam.
        """
        registo.info("nó %s: primário no epoch %s", self.id, self.eleicao.epoch)
        self.armazem.gravar_estado(self.eleicao.epoch, self.eleicao.votou_em)
        with self._lock_escrita:
            entrada = EntradaDeLog.de_operacao(
                self.log.ultimo_indice + 1, f"noop-{self.eleicao.epoch}-{self.id}",
                Noop(), time.time(), epoch=self.eleicao.epoch)
            self.log.acrescentar(entrada)
            with self._cond:
                # O que estava por aplicar era de um mandato anterior: fica
                # coberto pela `noop`, por quem todas as escritas esperam.
                self._pendentes.clear()
                self._noop_do_mandato = (entrada.epoch, entrada.indice)
        try:
            self._confirmar(entrada.indice)
        except ErroDoBanco:
            pass  # sem maioria ainda; `_tentar_ficar_pronto` tenta outra vez

    def _tentar_ficar_pronto(self) -> None:
        """Depois de um heartbeat: se a `noop` ainda não tem maioria, tenta outra vez.

        Sem isto, um primário cuja primeira ronda falhou só confirmaria a
        `noop` com a próxima escrita de um cliente — e, enquanto não estiver
        pronto, o balanceador não lhe manda nenhuma. Se há uma ronda em curso,
        não espera: é ela que confirma o que falta.
        """
        if self.pronto() or self._noop_do_mandato is None or self._ronda is not None:
            return
        try:
            self._confirmar(self._noop_do_mandato[1])
        except ErroDoBanco:
            pass  # sem maioria ainda; tenta-se no próximo heartbeat

    def _aplicar_ate_ao_commit(self) -> dict[str, dict]:
        """Aplica as entradas confirmadas que ainda não estão nas tabelas.

        Quem chama já tem `_lock_estado`. Aplicar só até ao commit é o que torna
        a recuperação trivialmente correta: o que está nas tabelas é exatamente
        o que foi prometido a alguém. Em lotes de até `LOTE_A_APLICAR`, cada um
        numa transação, quando o aplicador o permite.
        """
        respostas = {}
        commit = self.log.indice_commit
        confirmadas = [e for e in self.log.ler_desde(self._ultimo_aplicado)
                       if e.indice <= commit]
        aplicar_lote = getattr(self.aplicador, "aplicar_lote", None)
        for inicio in range(0, len(confirmadas), LOTE_A_APLICAR):
            lote = confirmadas[inicio:inicio + LOTE_A_APLICAR]
            if aplicar_lote is not None:
                respostas.update(aplicar_lote(lote))
            else:
                for entrada in lote:
                    respostas[entrada.op_id] = self.aplicador.aplicar(entrada)
            self._ultimo_aplicado = lote[-1].indice
        return respostas

    def _aplicar_em_fundo(self) -> None:
        """Acorda a thread que aplica o que as réplicas recebem; cria-a à primeira."""
        with self._cond:
            if self._aplicadora is None or not self._aplicadora.is_alive():
                self._aplicadora = threading.Thread(
                    target=self._aplicar_sempre, daemon=True, name=f"aplicar-{self.id}")
                self._aplicadora.start()
        self._ha_para_aplicar.set()

    def _aplicar_sempre(self) -> None:
        while not self._fechado.is_set():
            self._ha_para_aplicar.wait(timeout=1.0)
            self._ha_para_aplicar.clear()
            if self._fechado.is_set():
                return
            try:
                with self._lock_estado:
                    if self._ultimo_aplicado < self.log.indice_commit:
                        self._aplicar_ate_ao_commit()
            except Exception:  # noqa: BLE001
                # A base pode estar a reiniciar; tenta-se no próximo envio.
                registo.exception("nó %s: falhou a aplicar; tenta-se outra vez", self.id)

    # ---------------------------------------------------------------- leitura

    def e_primario(self) -> bool:
        return self.eleicao is None or self.eleicao.sou_primario()

    def pronto(self) -> bool:
        """Primário com a `noop` do seu epoch aplicada: as leituras estão em dia.

        Uma réplica não promete nada, por isso diz-se sempre pronta; quem lê
        dela já sabe que pode vir atrasada.
        """
        if self.eleicao is None or not self.eleicao.sou_primario():
            return True
        if self._noop_do_mandato is None:
            return False
        epoch, indice = self._noop_do_mandato
        return (epoch == self.eleicao.epoch and self.log.indice_commit >= indice
                and self._ultimo_aplicado >= indice)

    def estado_do_no(self) -> dict:
        return {"no": self.id,
                "papel": self.eleicao.papel if self.eleicao else "primário",
                "epoch": self.eleicao.epoch if self.eleicao else 1,
                "lider": (self.eleicao.lider_conhecido if self.eleicao else self.id),
                "ultimo_indice": self.log.ultimo_indice,
                "indice_commit": self.log.indice_commit,
                "ultimo_aplicado": self._ultimo_aplicado,
                "pronto": self.pronto(),
                "falhas": self.falhas.em_json()}

    def estado_do_cluster(self) -> dict:
        """O cluster inteiro, visto por este nó — para o painel desenhar os três."""
        return ver_cluster(self.id, self.configuracao, self.estado_do_no(),
                           self.falhas)


class _Ronda:
    """Uma ronda de replicação: até que índice levou, e se teve maioria."""

    def __init__(self) -> None:
        self.ate = 0
        self.ok = False
        self.feita = False
        self.motivo = "a ronda de replicação não terminou"
