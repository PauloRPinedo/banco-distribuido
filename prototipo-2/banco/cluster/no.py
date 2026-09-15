"""O nó do banco: junta o livro, o log, os locks e o papel no cluster.

Um `No` sem configuração de cluster é um banco de um nó só: aceita escritas
sempre, não tem papel nem eleição, e é o que os testes de domínio usam. Com
configuração, arranca **sempre como réplica** (docs/SPECS.md 4.2) e só escreve
depois de ganhar uma eleição.

A ordem dos passos de uma escrita é a da secção 5 do SPECS e não pode mudar.

**Ordem dos locks.** Há dois, e a regra é: nunca tomar `_lock_estado` tendo o lock
da eleição; o contrário pode. Existem separados por uma razão de correção — um
pedido de voto tem de poder ser respondido enquanto uma escrita espera pela
maioria. Se partilhassem o lock, um primário atascado sem quórum bloquearia
exatamente a eleição que desatava o nó.
"""

import threading
import time

from banco.cluster.concorrencia import RegistoDeLocks
from banco.cluster.configuracao import ConfiguracaoDoCluster
from banco.cluster.eleicao import Eleicao
from banco.cluster.ensaio import TrancaDeEnsaio
from banco.cluster.falhas import InjetorDeFalhas
from banco.cluster.log_de_replicacao import LogDeReplicacao
from banco.cluster.protocolo import LadoDoProtocolo
from banco.cluster.replicacao import Replicador
from banco.cluster.vista import ver_cluster
from banco.dominio.contas import Livro, Movimento
from banco.dominio.erros import NaoSouPrimario, SemQuorum, SomenteLeitura
from banco.dominio.operacoes import Operacao, total_esperado
from banco.persistencia.armazem import ArmazemDeLog
from banco.persistencia.entrada import EntradaDeLog


class No(LadoDoProtocolo):

    def __init__(self, identificador: str, armazem: ArmazemDeLog,
                 configuracao: ConfiguracaoDoCluster | None = None) -> None:
        self.id = identificador
        # Quem escolhe onde o log vive é quem constrói o nó — PostgreSQL na
        # demonstração, ficheiro na emergência, memória nos testes. O nó não
        # sabe a diferença, e é isso que permite trocar de armazém sem lhe tocar.
        self.armazem = armazem
        self.configuracao = configuracao
        self.livro = Livro()
        self.locks = RegistoDeLocks()
        self.log = LogDeReplicacao(armazem)
        self.falhas = InjetorDeFalhas()
        self.ensaio = TrancaDeEnsaio()

        # Reentrante por precaução: as leituras e a auditoria tomam este lock, e
        # um método que chame outro não deve poder bloquear-se a si próprio.
        self._lock_estado = threading.RLock()

        self._respostas: dict[str, dict] = {}
        self._operacoes: list[Operacao] = []
        self._ultimo_indice = 0

        if configuracao is None:
            self.eleicao = None
            self.replicador = None
        else:
            estado = armazem.ler_estado()
            self.eleicao = Eleicao(identificador,
                                   configuracao.semente_do_no(identificador),
                                   configuracao.timeout_eleicao_ms,
                                   estado.epoch, estado.votou_em)
            self.replicador = Replicador(identificador, configuracao, self.log,
                                         self.eleicao, self._assumir_mandato,
                                         self.falhas, self.ensaio)

        self._recuperar()

    def arrancar(self) -> None:
        """Começa a bater o coração e a contar o tempo. Só com cluster."""
        if self.replicador is not None:
            self.replicador.arrancar()

    # ---------------------------------------------------------------- escrita

    def executar(self, op_id: str, operacao: Operacao) -> dict:
        """A ordem obrigatória de uma escrita (SPECS secção 5)."""
        self._exigir_que_mando()

        guardada = self._resposta_guardada(op_id)
        if guardada is not None:
            return guardada

        # 2. Locks das contas envolvidas, por ordem crescente de id.
        with self.locks.adquirir(operacao.contas_tocadas()):
            with self._lock_estado:
                # 1 outra vez, agora protegido: duas chamadas com o mesmo op_id
                # tocam as mesmas contas, logo serializam neste ponto.
                guardada = self._respostas.get(op_id)
                if guardada is not None:
                    return guardada

                # 3. Validar antes do log: não se grava o que vai ser recusado.
                operacao.validar(self.livro)

                entrada = self._proxima_entrada(op_id, operacao)

                # 4. Gravar de forma durável.
                self.log.acrescentar(entrada)

                # 5. Replicar e esperar pela maioria.
                self._esperar_maioria(entrada)

                # 6. Aplicar e guardar a resposta, ainda com os locks tomados.
                return self._aplicar(entrada, operacao)

    def _esperar_maioria(self, entrada: EntradaDeLog) -> None:
        """O passo 5. Sem cluster não há por quem esperar."""
        if self.replicador is None:
            self.log.confirmar_ate(entrada.indice)
            return

        if not self.replicador.replicar(entrada, self._prazo_ms()):
            # A entrada fica gravada e por confirmar. Quem decide o destino dela
            # é o primário seguinte; repetir com o mesmo op_id é seguro.
            raise SemQuorum(
                f"a maioria não confirmou a operação a tempo "
                f"({self._prazo_ms()} ms); a entrada {entrada.indice} ficou "
                f"gravada por confirmar")

        # Fencing (SPECS 8.3): durante a espera pode ter chegado um epoch maior
        # e este nó já não manda. Aplicar aqui criaria uma operação confirmada
        # por alguém que deixou de ser primário a meio.
        if not self.eleicao.sou_primario():
            raise SemQuorum(
                "deixei de ser primário enquanto esperava pela maioria; a "
                "operação não foi aplicada")

        self.log.confirmar_ate(entrada.indice)

    def _proxima_entrada(self, op_id: str, operacao: Operacao) -> EntradaDeLog:
        return EntradaDeLog.de_operacao(
            self._ultimo_indice + 1, op_id, operacao, time.time(),
            epoch=self.eleicao.epoch if self.eleicao else 1)

    def _aplicar(self, entrada: EntradaDeLog, operacao: Operacao) -> dict:
        resposta = operacao.aplicar(self.livro, entrada.indice, entrada.instante)
        self._ultimo_indice = entrada.indice
        self._operacoes.append(operacao)
        self._respostas[entrada.op_id] = resposta
        return resposta

    def _exigir_que_mando(self) -> None:
        if self.eleicao is None:
            return
        if not self.eleicao.sou_primario():
            raise NaoSouPrimario(
                f"o nó {self.id} não é o primário deste cluster",
                self.endereco_do_lider())
        if not self.replicador.vejo_a_maioria():
            raise SomenteLeitura(
                f"o nó {self.id} não fala com a maioria há mais de um timeout "
                f"de eleição; recusa escritas e continua a responder a leituras")

    def endereco_do_lider(self) -> str | None:
        lider = self.eleicao.lider_conhecido
        if not lider or lider == self.id:
            return None
        try:
            no = self.configuracao.obter(lider)
        except Exception:  # noqa: BLE001
            return None
        return f"{no.endereco}:{no.porta}"

    def _prazo_ms(self) -> int:
        return self.configuracao.timeout_replicacao_ms

    # ---------------------------------------------------------------- leitura

    def saldo(self, conta: str) -> dict:
        with self._lock_estado:
            encontrada = self.livro.obter(conta)
            return {"conta": encontrada.id,
                    "saldo_centavos": encontrada.saldo_centavos,
                    "criada_em": encontrada.criada_em}

    def extrato(self, conta: str) -> dict:
        with self._lock_estado:
            movimentos = self.livro.extrato(conta)
            return {"conta": conta,
                    "movimentos": [_movimento_em_json(m) for m in movimentos]}

    def auditoria(self) -> dict:
        """Soma os saldos e compara com o total calculado a partir do log.

        Os dois lados vêm de sítios independentes: o esquerdo dos saldos das
        contas, o direito da sequência de operações. É a igualdade entre eles
        que verifica alguma coisa — somar duas vezes a mesma estrutura não
        auditaria nada (F-06, RF-14).
        """
        with self._lock_estado:
            pelos_saldos = self.livro.total_centavos()
            pelo_log = total_esperado(self._operacoes)
            return {"total_centavos": pelos_saldos,
                    "total_esperado_centavos": pelo_log,
                    "divergencia_centavos": pelos_saldos - pelo_log,
                    "divergente": pelos_saldos != pelo_log,
                    "contas": len(self.livro.contas),
                    "operacoes": len(self._operacoes)}

    def estado_do_no(self) -> dict:
        with self._lock_estado:
            return {"no": self.id,
                    "papel": self.eleicao.papel if self.eleicao else "primário",
                    "epoch": self.eleicao.epoch if self.eleicao else 1,
                    "ultimo_indice": self.log.ultimo_indice,
                    "indice_commit": self.log.indice_commit,
                    "contas": len(self.livro.contas),
                    "falhas": self.falhas.em_json(),
                    "ensaio": self.ensaio.em_json()}

    def estado_do_cluster(self) -> dict:
        """O cluster inteiro, visto por este nó (ver `cluster/vista.py`).

        Existe para o frontend poder desenhar os três cartões de nó a partir de
        um endereço só — na demonstração há um túnel, não três.
        """
        return ver_cluster(self.id, self.configuracao, self.estado_do_no(),
                           self.falhas)

    def fechar(self) -> None:
        if self.replicador is not None:
            self.replicador.parar()
        self.armazem.fechar()

    # ------------------------------------------------------------- interno

    def _resposta_guardada(self, op_id: str) -> dict | None:
        with self._lock_estado:
            return self._respostas.get(op_id)

    def _recuperar(self) -> None:
        """Reconstrói o estado aplicando o log do princípio (RF-12).

        Não há snapshots: o replay é sempre completo. À escala da demonstração
        são milissegundos, e um snapshot custaria um conjunto novo de casos
        extremos para não resolver problema nenhum.

        Com cluster, aplica-se só até ao `indice_commit`. Sem cluster não há
        maioria por quem esperar, e uma entrada durável está confirmada no
        instante em que é gravada — por isso confirma-se tudo o que lá está.
        """
        if self.eleicao is None:
            self.log.confirmar_ate(self.log.ultimo_indice)
        with self._lock_estado:
            self._aplicar_ate_ao_commit()


def _movimento_em_json(movimento: Movimento) -> dict:
    return {"indice": movimento.indice,
            "tipo": movimento.tipo,
            "valor_centavos": movimento.valor_centavos,
            "contraparte": movimento.contraparte,
            "saldo_depois_centavos": movimento.saldo_depois_centavos,
            "instante": movimento.instante}
