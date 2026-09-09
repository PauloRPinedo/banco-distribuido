"""O nó do banco: junta o livro, o log e os locks.

Na etapa 1 há um nó só. Ele aceita escritas sempre, sem papel nem eleição: o
"arrancar sempre como réplica" da secção 4.2 de docs/SPECS.md pressupõe um
cluster que ainda não existe, e uma réplica sozinha recusaria tudo.

A ordem dos passos de uma escrita é a da secção 5 do SPECS e não pode mudar.
"""

import threading
import time
from pathlib import Path

from banco.cluster.concorrencia import RegistoDeLocks
from banco.dominio.contas import Livro, Movimento
from banco.dominio.operacoes import Operacao, total_esperado
from banco.persistencia.entrada import EntradaDeLog
from banco.persistencia.estado_no import EstadoDoNo
from banco.persistencia.wal import Wal


class No:

    def __init__(self, identificador: str, diretorio: Path) -> None:
        self.id = identificador
        self.diretorio = Path(diretorio)
        self.livro = Livro()
        self.wal = Wal(self.diretorio / "wal.jsonl")
        self.estado = EstadoDoNo.carregar(self.diretorio / "estado.json")
        self.locks = RegistoDeLocks()

        # Reentrante por precaução: as leituras e a auditoria tomam este lock, e
        # um método que chame outro não deve poder bloquear-se a si próprio.
        self._lock_estado = threading.RLock()

        self._respostas: dict[str, dict] = {}
        self._operacoes: list[Operacao] = []
        self._ultimo_indice = 0

        self._recuperar()

    # ---------------------------------------------------------------- escrita

    def executar(self, op_id: str, operacao: Operacao) -> dict:
        """A ordem obrigatória de uma escrita (SPECS secção 5)."""
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

                indice = self._ultimo_indice + 1
                instante = time.time()
                entrada = EntradaDeLog.de_operacao(indice, op_id, operacao,
                                                   instante)

                # 4. Gravar e fazer fsync.
                self.wal.acrescentar(entrada)

                # 5. Na etapa 2 entra aqui a replicação e a espera pela maioria.
                #    Sem cluster, uma entrada durável já está confirmada.

                # 6. Aplicar e guardar a resposta, ainda com os locks tomados.
                resposta = operacao.aplicar(self.livro, indice, instante)
                self._ultimo_indice = indice
                self._operacoes.append(operacao)
                self._respostas[op_id] = resposta
                return resposta

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
                    "papel": "primário",
                    "epoch": self.estado.epoch,
                    "ultimo_indice": self._ultimo_indice,
                    # Sem maioria por quem esperar, uma entrada durável está
                    # confirmada no instante em que é gravada.
                    "indice_commit": self._ultimo_indice,
                    "contas": len(self.livro.contas)}

    def fechar(self) -> None:
        self.wal.fechar()

    # ------------------------------------------------------------- interno

    def _resposta_guardada(self, op_id: str) -> dict | None:
        with self._lock_estado:
            return self._respostas.get(op_id)

    def _recuperar(self) -> None:
        """Reconstrói o estado aplicando o WAL do princípio (RF-12).

        Não há snapshots: o replay é sempre completo. À escala da demonstração
        são milissegundos, e um snapshot custaria um conjunto novo de casos
        extremos para não resolver problema nenhum.
        """
        for entrada in self.wal.ler_tudo():
            operacao = entrada.operacao()
            self._respostas[entrada.op_id] = operacao.aplicar(
                self.livro, entrada.indice, entrada.instante)
            self._operacoes.append(operacao)
            self._ultimo_indice = entrada.indice


def _movimento_em_json(movimento: Movimento) -> dict:
    return {"indice": movimento.indice,
            "tipo": movimento.tipo,
            "valor_centavos": movimento.valor_centavos,
            "contraparte": movimento.contraparte,
            "saldo_depois_centavos": movimento.saldo_depois_centavos,
            "instante": movimento.instante}
