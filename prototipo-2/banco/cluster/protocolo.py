"""O nó visto pelos outros nós: replicar, votar, assumir o mandato.

Está separado de `no.py` porque são duas responsabilidades distintas, e um
módulo acima de ~250 linhas costuma estar a fazer duas coisas. A divisão é por audiência:

- `no.py` é o **banco**: aceita operações de clientes e responde a leituras;
- este ficheiro é o **participante do protocolo**: atende os pares.

Vem como mixin e não como objeto à parte por honestidade: estes métodos mexem no
livro, nas respostas guardadas e no log do mesmo nó, e fingir que são um
colaborador independente esconderia esse acoplamento em vez de o resolver. O que
a separação dá é a possibilidade de ler cada metade sem a outra.
"""

from banco.cluster.eleicao import PedidoDeVoto
from banco.dominio.erros import ParticaoSimulada
from banco.dominio.operacoes import Noop
from banco.persistencia.entrada import EntradaDeLog


class LadoDoProtocolo:
    """Os métodos que os outros nós chamam. Misturado em `No`."""

    def replicar(self, epoch: int, id_lider: str, indice_anterior: int,
                 epoch_anterior: int, entradas: list[EntradaDeLog],
                 commit_lider: int, ensaio: dict | None = None) -> dict:
        """Atende `/interno/replicar`. Também serve de heartbeat."""
        if self.eleicao is None:
            return {"ok": False, "epoch": 1,
                    "motivo": "este nó não faz parte de um cluster"}

        if not self.falhas.fala_com(id_lider):
            # Isolado deste nó: a mensagem é descartada como se a rede a tivesse
            # perdido. Responder "estou isolado" seria uma partição de mentira.
            raise ParticaoSimulada(f"o nó {self.id} está isolado de {id_lider}")
        self.falhas.talvez_atrasar()

        if epoch < self.eleicao.epoch:
            # Condição 1: líder velho. Responder com o meu epoch é o que o faz
            # despromover-se do outro lado.
            return {"ok": False, "epoch": self.eleicao.epoch,
                    "motivo": "epoch do líder é menor que o meu"}

        self.eleicao.vi_o_lider(id_lider, epoch)
        # A sessão de ensaio é do líder; esta réplica adota o que ele diz. É o
        # que lhe permite recusar um segundo operador sem perguntar a ninguém.
        self.ensaio.adotar(ensaio)

        if not self.log.corresponde(indice_anterior, epoch_anterior):
            # Condição 2: o meu log divergiu ou tem um buraco. Digo onde estou e
            # o líder reenvia daí — é a simplificação face ao Raft.
            return {"ok": False, "epoch": self.eleicao.epoch,
                    "meu_ultimo_indice": self.log.ultimo_indice,
                    "motivo": "o log não corresponde"}

        with self._lock_estado:
            if entradas:
                self.log.acrescentar_do_lider(entradas)
            self.log.confirmar_ate(commit_lider)
            self._aplicar_ate_ao_commit()

        return {"ok": True, "epoch": self.eleicao.epoch,
                "indice_correspondente": self.log.ultimo_indice}

    def votar(self, pedido: PedidoDeVoto) -> dict:
        """Atende `/interno/votar`.

        Não toma `_lock_estado` de propósito: tem de conseguir responder enquanto
        uma escrita espera pela maioria, que é precisamente a situação em que a
        eleição faz falta.
        """
        if self.eleicao is None:
            return {"concedido": False, "epoch": 1,
                    "motivo": "este nó não faz parte de um cluster"}

        if not self.falhas.fala_com(pedido.id_candidato):
            raise ParticaoSimulada(
                f"o nó {self.id} está isolado de {pedido.id_candidato}")
        self.falhas.talvez_atrasar()

        concedido, motivo = self.eleicao.conceder_voto(
            pedido, self.log.ultimo_indice, self.log.ultimo_epoch)
        # O voto tem de ser durável **antes** de a resposta sair: um nó que vota,
        # cai e esquece o voto votaria outra vez no mesmo epoch, e dois
        # candidatos diferentes poderiam somar maioria.
        self.armazem.gravar_estado(self.eleicao.epoch, self.eleicao.votou_em)
        return {"concedido": concedido, "epoch": self.eleicao.epoch,
                "motivo": motivo}

    def _assumir_mandato(self) -> None:
        """Grava a `noop` do próprio epoch ao assumir.

        Uma entrada herdada do primário anterior não pode ser confirmada por
        contagem de réplicas — há um cenário conhecido em que acaba sobrescrita, e
        uma operação já dada como confirmada desapareceria. Confirmando primeiro
        a `noop` deste epoch, tudo o que vem antes fica confirmado por arrasto.
        """
        self.armazem.gravar_estado(self.eleicao.epoch, self.eleicao.votou_em)
        with self._lock_estado:
            self._aplicar_ate_ao_commit()
            entrada = self._proxima_entrada(f"noop-{self.eleicao.epoch}", Noop())
            self.log.acrescentar(entrada)
        if self.replicador.replicar(entrada, self._prazo_ms()):
            with self._lock_estado:
                self.log.confirmar_ate(entrada.indice)
                self._aplicar_ate_ao_commit()

    def _aplicar_ate_ao_commit(self) -> None:
        """Aplica as entradas confirmadas que ainda não estão no livro.

        Quem chama já tem `_lock_estado`. Aplicar só até ao commit é o que torna
        a recuperação trivialmente correta: o que está no livro é exatamente o
        que foi prometido a alguém.
        """
        for entrada in self.log.ler_desde(self._ultimo_indice):
            if entrada.indice > self.log.indice_commit:
                break
            operacao = entrada.operacao()
            self._respostas[entrada.op_id] = operacao.aplicar(
                self.livro, entrada.indice, entrada.instante)
            self._operacoes.append(operacao)
            self._ultimo_indice = entrada.indice

