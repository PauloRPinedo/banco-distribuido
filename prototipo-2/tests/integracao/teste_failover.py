"""Matar o primário e continuar sem perder dinheiro (subfases 2.5, 2.6, 2.9).

É o teste que justifica o projeto inteiro. Tudo o resto — centavos inteiros,
ordem dos locks, fsync, quórum — existe para que estas asserções passem.

Os tempos são curtos (heartbeat de 30 ms, timeout em [120, 240] ms) para a suíte
correr depressa. A relação entre eles é a mesma da demonstração, e o limite de
RNF-03 verifica-se contra os tempos configurados, não contra os 2 s absolutos —
medir 2 s com um timeout de 240 ms não diria nada sobre o protocolo.
"""

import threading
import unittest

from banco.dominio.erros import ErroDoBanco
from banco.dominio.operacoes import CriarConta, Deposito, Transferencia
from tests.ajudas import (criar_cluster_de_teste, esperar_ate,
                          esperar_por_primario)


class BaseComCluster(unittest.TestCase):

    def setUp(self):
        self.cluster = criar_cluster_de_teste(self)
        self.primario = esperar_por_primario(self, self.cluster.nos)
        self.primario.executar("c1", CriarConta("alice", 10000))
        self.primario.executar("c2", CriarConta("bob", 0))
        self.esperar_replicas_em_dia()

    def esperar_replicas_em_dia(self):
        alvo = self.primario.log.indice_commit
        pronto = esperar_ate(
            lambda: all(no.log.indice_commit >= alvo
                        for no in self.cluster.outros(self.primario)))
        self.assertTrue(pronto, "as réplicas não se puseram em dia")


class TesteFailover(BaseComCluster):

    def teste_o_cluster_elege_outro_primario(self):
        antigo = self.primario
        self.cluster.derrubar(antigo)

        novo = esperar_por_primario(self, self.cluster.outros(antigo))

        self.assertNotEqual(novo.id, antigo.id)

    def teste_o_epoch_sobe_no_failover(self):
        """Cada mandato tem o seu número, e ele só cresce (SPECS 8.3)."""
        epoch_antigo = self.primario.estado_do_no()["epoch"]
        self.cluster.derrubar(self.primario)

        novo = esperar_por_primario(self, self.cluster.outros(self.primario))

        self.assertGreater(novo.estado_do_no()["epoch"], epoch_antigo)

    def teste_o_dinheiro_sobrevive_ao_failover(self):
        """RNF-01 e RNF-02 no cenário que o projeto existe para resolver."""
        antes = self.primario.auditoria()["total_centavos"]
        self.cluster.derrubar(self.primario)

        novo = esperar_por_primario(self, self.cluster.outros(self.primario))

        self.assertEqual(novo.auditoria()["total_centavos"], antes)
        self.assertFalse(novo.auditoria()["divergente"])

    def teste_o_novo_primario_aceita_escritas(self):
        """RF-11: o serviço continua depois da queda de um servidor."""
        self.cluster.derrubar(self.primario)
        novo = esperar_por_primario(self, self.cluster.outros(self.primario))

        novo.executar("t1", Transferencia("alice", "bob", 2500))

        self.assertEqual(novo.saldo("bob")["saldo_centavos"], 2500)

    def teste_o_novo_primario_tem_tudo_o_que_estava_confirmado(self):
        """A condição 3 do voto em ação (SPECS 8.2).

        Duas maiorias intersectam-se; o nó comum só vota em quem tem o log ao
        menos tão atualizado quanto o dele. Logo o vencedor tem tudo o que foi
        confirmado — e é isto que impede uma transferência confirmada de
        desaparecer num failover.
        """
        self.primario.executar("d1", Deposito("alice", 5000))
        self.esperar_replicas_em_dia()
        commit_antigo = self.primario.log.indice_commit
        self.cluster.derrubar(self.primario)

        novo = esperar_por_primario(self, self.cluster.outros(self.primario))

        self.assertGreaterEqual(novo.log.ultimo_indice, commit_antigo)
        self.assertEqual(novo.saldo("alice")["saldo_centavos"], 15000)

    def teste_o_tempo_de_failover_cabe_no_orcamento(self):
        """RNF-03, medido contra os tempos configurados.

        O orçamento é o timeout máximo de eleição mais uma ronda de votos, com
        folga. Afirmar "menos de 2 s" com um timeout de 240 ms não provaria nada
        sobre o protocolo — só que o relógio anda.
        """
        import time
        maximo_ms = self.cluster.nos[0].configuracao.timeout_eleicao_ms[1]
        orcamento = (maximo_ms + self.cluster.nos[0].configuracao
                     .timeout_replicacao_ms) / 1000 * 3

        comeco = time.monotonic()
        self.cluster.derrubar(self.primario)
        esperar_por_primario(self, self.cluster.outros(self.primario),
                             limite=orcamento)
        demorou = time.monotonic() - comeco

        self.assertLess(demorou, orcamento,
                        f"failover demorou {demorou:.2f}s, orçamento {orcamento:.2f}s")


class TesteRetentativa(BaseComCluster):

    def teste_o_mesmo_op_id_depois_do_failover_nao_duplica(self):
        """RF-13: a deduplicação é o que torna a retentativa segura.

        Sem isto, um cliente que não recebe resposta por o primário ter morrido
        repetiria a transferência e o dinheiro moveria-se duas vezes.
        """
        self.primario.executar("t1", Transferencia("alice", "bob", 2500))
        self.esperar_replicas_em_dia()
        self.cluster.derrubar(self.primario)
        novo = esperar_por_primario(self, self.cluster.outros(self.primario))

        novo.executar("t1", Transferencia("alice", "bob", 2500))

        self.assertEqual(novo.saldo("alice")["saldo_centavos"], 7500)
        self.assertEqual(novo.auditoria()["total_centavos"], 10000)


class TesteQuedaSobCarga(BaseComCluster):

    def teste_a_soma_nao_muda_com_o_primario_a_morrer_a_meio(self):
        """O cenário do SIGKILL a meio de transferências concorrentes.

        As operações em voo podem falhar — é esperado, e o cliente repete. O que
        **não** pode acontecer é o total mudar: uma transferência aplicada a meio
        criaria ou destruiria dinheiro, e é isso que RNF-01 proíbe.
        """
        antes = self.primario.auditoria()["total_centavos"]
        parar = threading.Event()
        falhas = []

        def transferir():
            numero = 0
            while not parar.is_set():
                numero += 1
                try:
                    self.primario.executar(f"carga-{numero}",
                                           Transferencia("alice", "bob", 100))
                    self.primario.executar(f"volta-{numero}",
                                           Transferencia("bob", "alice", 100))
                except ErroDoBanco as erro:
                    # Recusas são normais a partir do momento em que o primário
                    # perde o quórum: o cliente repetiria.
                    falhas.append(type(erro).__name__)
                    return

        carga = threading.Thread(target=transferir, daemon=True)
        carga.start()
        esperar_ate(lambda: self.primario.log.ultimo_indice > 5, limite=2.0)
        self.cluster.derrubar(self.primario)
        parar.set()
        carga.join(timeout=5)

        novo = esperar_por_primario(self, self.cluster.outros(self.primario))
        depois = novo.auditoria()
        self.assertEqual(depois["total_centavos"], antes)
        self.assertFalse(depois["divergente"])


if __name__ == "__main__":
    unittest.main()
