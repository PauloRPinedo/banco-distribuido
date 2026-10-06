"""O nó do cluster: junta a eleição, o log replicado e o aplicador.

Uma regra organiza tudo: **o estado de um nó (as tabelas `conta`, `operacao`,
`usuario`, `taxa_cambio`) é o resultado de aplicar, por ordem de índice, as
entradas confirmadas do log.** O primário e as réplicas aplicam com a mesma
função (`Aplicador.aplicar`), por isso três nós com o mesmo log confirmado têm
as mesmas tabelas.

Sem configuração de cluster, o nó é um banco de um nó só: manda sempre, e uma
entrada durável está confirmada no instante em que é gravada. Com configuração,
arranca **sempre como réplica** e só escreve depois de ganhar uma eleição.

**Os locks.** Há três, e a ordem é sempre esta: `_lock_escrita` → `_lock_estado`.

- `_lock_escrita` serializa as escritas do primário: uma de cada vez, da
  validação até à aplicação. É o que garante que se valida contra o estado que
  a entrada anterior deixou, e que os índices nunca chocam.
- `_lock_estado` protege o "aplicar até ao commit", que tanto o primário como
  o RPC de replicação chamam.
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
from banco.dominio.operacoes import Operacao

registo = logging.getLogger("banco.cluster")


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
        self._construir()

    def _construir(self) -> None:
        """Lê o que está no armazém e monta o log, a eleição e o replicador."""
        self.log = LogDeReplicacao(self.armazem)
        self._ultimo_aplicado = self.aplicador.ultimo_aplicado()
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
                                         self.falhas)
        # Recuperação (RF-12): o que ficou confirmado e por aplicar quando o
        # processo caiu aplica-se agora, antes de responder a quem quer que seja.
        with self._lock_estado:
            self._aplicar_ate_ao_commit()

    def arrancar(self) -> None:
        """Começa a bater o coração e a contar o tempo. Só com cluster."""
        if self.replicador is not None:
            self.replicador.arrancar()

    def fechar(self) -> None:
        if self.replicador is not None:
            self.replicador.parar()
        self.armazem.fechar()

    def recarregar(self) -> None:
        """Só para os testes: volta a ler tudo do armazém depois de o esvaziarem."""
        with self._lock_escrita, self._lock_estado:
            if self.replicador is not None:
                self.replicador.parar()
            self._construir()
            self.arrancar()

    # ---------------------------------------------------------------- escrita

    def executar(self, op_id: str, operacao: Operacao, verificar=None) -> dict:
        """A ordem de uma escrita no primário.

        `verificar(instante)` é a validação contra o estado atual (o dono das
        contas e as regras do domínio). Corre dentro do lock de escrita, depois
        de aplicada a entrada anterior: valida-se contra o estado certo.
        """
        with self._lock_escrita:
            # 0. Mando, e vejo a maioria?
            self._exigir_que_mando()

            # 1. Já foi aplicada? Devolve-se o guardado.
            guardada = self.aplicador.resposta_guardada(op_id)
            if guardada is not None:
                return guardada

            # 1b. Há entradas por confirmar (de uma escrita que não teve maioria)?
            # Confirmam-se primeiro: validar sem elas aplicadas seria validar
            # contra um estado que não é o que a nova entrada vai encontrar.
            if self.log.ultimo_indice > self.log.indice_commit:
                self._confirmar_pendentes()
                guardada = self.aplicador.resposta_guardada(op_id)
                if guardada is not None:
                    return guardada

            # 2. Validar antes do log: nunca se grava o que vai ser recusado. O
            # instante decide-se aqui, uma vez, e viaja na entrada.
            instante = time.time()
            if verificar is not None:
                verificar(instante)

            entrada = EntradaDeLog.de_operacao(
                self.log.ultimo_indice + 1, op_id, operacao, instante,
                epoch=self.eleicao.epoch if self.eleicao else 1)

            # 3. Gravar de forma durável no log deste nó.
            self.log.acrescentar(entrada)

            # 4 e 5. Replicar, esperar pela maioria, confirmar.
            self._esperar_maioria(entrada)

            # 6. Aplicar às tabelas — este nó e, no heartbeat seguinte, as réplicas.
            with self._lock_estado:
                respostas = self._aplicar_ate_ao_commit()

            # 7. Responder.
            return respostas.get(op_id) or self.aplicador.resposta_guardada(op_id) or {}

    def _esperar_maioria(self, entrada: EntradaDeLog) -> None:
        if self.replicador is None:
            self.log.confirmar_ate(entrada.indice)
            return

        prazo = self.configuracao.timeout_replicacao_ms
        if not self.replicador.replicar(entrada, prazo):
            raise SemQuorum(
                f"a maioria não confirmou a operação a tempo ({prazo} ms); a "
                f"entrada {entrada.indice} ficou gravada por confirmar — repetir "
                "com o mesmo op_id")

        # Fencing: durante a espera pode ter chegado um epoch maior e este nó
        # já não manda. Confirmar aqui seria confirmar sem mandato.
        if not self.eleicao.sou_primario():
            raise SemQuorum("deixei de ser primário enquanto esperava pela "
                            "maioria; a operação não foi aplicada")

        self.log.confirmar_ate(entrada.indice)

    def _confirmar_pendentes(self) -> None:
        """Volta a pedir a maioria para a última entrada por confirmar.

        Confirmá-la confirma tudo o que está antes dela (o commit é um prefixo).
        """
        pendentes = self.log.ler_desde(self.log.indice_commit)
        if pendentes:
            self._esperar_maioria(pendentes[-1])
            with self._lock_estado:
                self._aplicar_ate_ao_commit()

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
                "eleição; recusa escritas e continua a responder a leituras")

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
            self._aplicar_ate_ao_commit()

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

        Toma o lock de escrita: entre ganhar e gravar a `noop` não pode entrar
        nenhuma escrita de cliente, ou os índices chocariam.
        """
        registo.info("nó %s: primário no epoch %s", self.id, self.eleicao.epoch)
        self.armazem.gravar_estado(self.eleicao.epoch, self.eleicao.votou_em)
        with self._lock_escrita:
            entrada = EntradaDeLog.de_operacao(
                self.log.ultimo_indice + 1, f"noop-{self.eleicao.epoch}-{self.id}",
                Noop(), time.time(), epoch=self.eleicao.epoch)
            self.log.acrescentar(entrada)
            if self.replicador.replicar(entrada, self.configuracao.timeout_replicacao_ms):
                self.log.confirmar_ate(entrada.indice)
                with self._lock_estado:
                    self._aplicar_ate_ao_commit()

    def _aplicar_ate_ao_commit(self) -> dict[str, dict]:
        """Aplica as entradas confirmadas que ainda não estão nas tabelas.

        Quem chama já tem `_lock_estado`. Aplicar só até ao commit é o que torna
        a recuperação trivialmente correta: o que está nas tabelas é exatamente
        o que foi prometido a alguém.
        """
        respostas = {}
        for entrada in self.log.ler_desde(self._ultimo_aplicado):
            if entrada.indice > self.log.indice_commit:
                break
            respostas[entrada.op_id] = self.aplicador.aplicar(entrada)
            self._ultimo_aplicado = entrada.indice
        return respostas

    # ---------------------------------------------------------------- leitura

    def e_primario(self) -> bool:
        return self.eleicao is None or self.eleicao.sou_primario()

    def estado_do_no(self) -> dict:
        return {"no": self.id,
                "papel": self.eleicao.papel if self.eleicao else "primário",
                "epoch": self.eleicao.epoch if self.eleicao else 1,
                "lider": (self.eleicao.lider_conhecido if self.eleicao else self.id),
                "ultimo_indice": self.log.ultimo_indice,
                "indice_commit": self.log.indice_commit,
                "ultimo_aplicado": self._ultimo_aplicado,
                "falhas": self.falhas.em_json()}

    def estado_do_cluster(self) -> dict:
        """O cluster inteiro, visto por este nó — para o painel desenhar os três."""
        return ver_cluster(self.id, self.configuracao, self.estado_do_no(),
                           self.falhas)
