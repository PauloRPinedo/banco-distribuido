"""O protocolo de replicação, com três nós no mesmo processo.

É o teste que justifica o projeto: três nós, um primário eleito, cada escrita
confirmada pela maioria e aplicada nos três, e a queda do primário — ou uma
partição de rede — sem que o dinheiro mude.

Corre sem base de dados nem rede (`tests/cluster_em_memoria.py`). O mesmo
protocolo corre contra três processos e três bases PostgreSQL em
`tests/integracao/teste_cluster.py`.
"""

import threading
import unittest

from banco.cluster.erros import NaoSouPrimario, SemQuorum, SomenteLeitura
from banco.dominio.operacoes import CriarConta, Deposito, Transferencia
from tests.cluster_em_memoria import ClusterEmMemoria


class Base(unittest.TestCase):

    def setUp(self) -> None:
        self.cluster = ClusterEmMemoria(self)
        self.primario = self.cluster.esperar_primario()
        self.primario.executar("op-alice", CriarConta("alice", 10_000))
        self.primario.executar("op-bob", CriarConta("bob", 0))

    def saldos(self, conta: str) -> dict[str, int]:
        return {no.id: self.cluster.aplicadores[no.id].saldo(conta)
                for no in self.cluster.nos
                if conta in self.cluster.aplicadores[no.id].livro.contas}

    def em_dia(self, *nos) -> bool:
        """As réplicas aplicaram tudo o que o primário confirmou?"""
        alvo = self.primario.log.indice_commit
        return self.cluster.esperar(
            lambda: all(self.cluster.aplicadores[no.id].ultimo >= alvo
                        for no in (nos or self.cluster.nos)))


class TesteEleicao(Base):

    def teste_ha_exatamente_um_primario(self):
        primarios = [no for no in self.cluster.nos if no.eleicao.sou_primario()]
        self.assertEqual(len(primarios), 1)

    def teste_as_replicas_conhecem_o_primario(self):
        self.assertTrue(self.em_dia())
        for no in self.cluster.outros(self.primario):
            self.assertEqual(no.eleicao.lider_conhecido, self.primario.id)

    def teste_uma_replica_recusa_escritas_e_diz_quem_manda(self):
        replica = self.cluster.outros(self.primario)[0]
        self.assertTrue(self.em_dia())

        with self.assertRaises(NaoSouPrimario) as recusa:
            replica.executar("op-x", Deposito("alice", 1))

        self.assertEqual(recusa.exception.para_json()["primario_provavel"],
                         f"http://no-{self.primario.id.lower()}:8001")


class TesteReplicacao(Base):

    def teste_cada_escrita_chega_aos_tres_nos(self):
        self.primario.executar("op-t1", Transferencia("alice", "bob", 2_500))

        self.assertTrue(self.em_dia())
        self.assertEqual(self.saldos("bob"), {"A": 2_500, "B": 2_500, "C": 2_500})

    def teste_os_tres_logs_sao_iguais(self):
        self.primario.executar("op-d1", Deposito("alice", 100))
        self.assertTrue(self.em_dia())

        logs = {no.id: [(e.indice, e.epoch, e.op_id) for e in no.log.ler_desde(0)]
                for no in self.cluster.nos}

        self.assertEqual(len({tuple(log) for log in logs.values()}), 1, logs)

    def teste_o_mesmo_op_id_aplica_se_uma_vez(self):
        self.primario.executar("op-rep", Deposito("alice", 500))
        self.primario.executar("op-rep", Deposito("alice", 500))

        self.assertTrue(self.em_dia())
        self.assertEqual(set(self.saldos("alice").values()), {10_500})


class TesteFailover(Base):

    def teste_cair_o_primario_elege_outro_com_epoch_maior(self):
        antigo = self.primario
        epoch = antigo.eleicao.epoch
        self.cluster.derrubar(antigo)

        novo = self.cluster.esperar_primario(self.cluster.outros(antigo))

        self.assertNotEqual(novo.id, antigo.id)
        self.assertGreater(novo.eleicao.epoch, epoch)

    def teste_nada_confirmado_se_perde_no_failover(self):
        self.primario.executar("op-t1", Transferencia("alice", "bob", 2_500))
        antigo = self.primario
        self.cluster.derrubar(antigo)

        novo = self.cluster.esperar_primario()

        self.assertTrue(self.cluster.esperar(
            lambda: self.cluster.aplicadores[novo.id].ultimo >= 3))
        self.assertEqual(self.cluster.aplicadores[novo.id].saldo("bob"), 2_500)
        self.assertEqual(self.cluster.aplicadores[novo.id].livro.total_centavos(), 10_000)

    def teste_o_novo_primario_aceita_escritas(self):
        self.cluster.derrubar(self.primario)
        novo = self.cluster.esperar_primario()

        novo.executar("op-depois", Deposito("bob", 700))

        self.assertEqual(self.cluster.aplicadores[novo.id].saldo("bob"), 700)

    def teste_repetir_o_op_id_depois_do_failover_nao_duplica(self):
        """O cliente não recebeu resposta porque o primário morreu: repete."""
        self.primario.executar("op-t1", Transferencia("alice", "bob", 2_500))
        self.cluster.derrubar(self.primario)
        novo = self.cluster.esperar_primario()

        novo.executar("op-t1", Transferencia("alice", "bob", 2_500))

        self.assertEqual(self.cluster.aplicadores[novo.id].saldo("bob"), 2_500)

    def teste_o_no_que_volta_e_replica_e_poe_se_em_dia(self):
        antigo = self.primario
        self.cluster.derrubar(antigo)
        novo = self.cluster.esperar_primario()
        novo.executar("op-sem-ele", Deposito("alice", 1_000))

        de_volta = self.cluster.reiniciar(antigo.id)

        self.assertTrue(self.cluster.esperar(
            lambda: self.cluster.aplicadores[antigo.id].saldo("alice") == 11_000))
        self.assertFalse(de_volta.eleicao.sou_primario())
        self.assertEqual(de_volta.eleicao.lider_conhecido, novo.id)

    def teste_a_soma_nao_muda_com_o_primario_a_morrer_a_meio(self):
        """Transferências em paralelo e o primário cai a meio.

        As operações em voo podem falhar — o cliente repete. O que não pode
        acontecer é o total mudar.
        """
        parar = threading.Event()

        def transferir():
            numero = 0
            while not parar.is_set():
                numero += 1
                for no in list(self.cluster.nos):
                    try:
                        no.executar(f"op-carga-{numero}",
                                    Transferencia("alice", "bob", 1))
                        break
                    except Exception:  # noqa: BLE001 — réplica, sem quórum, etc.
                        continue

        fio = threading.Thread(target=transferir)
        fio.start()
        self.cluster.esperar(lambda: False, limite=0.2)
        self.cluster.derrubar(self.primario)
        novo = self.cluster.esperar_primario()
        self.cluster.esperar(lambda: False, limite=0.3)
        parar.set()
        fio.join(5)

        self.assertTrue(self.cluster.esperar(
            lambda: all(self.cluster.aplicadores[no.id].ultimo
                        >= novo.log.indice_commit for no in self.cluster.nos)))
        for no in self.cluster.nos:
            self.assertEqual(self.cluster.aplicadores[no.id].livro.total_centavos(),
                             10_000, no.id)


class TesteSemMaioria(Base):

    def teste_com_dois_nos_em_baixo_o_que_resta_nao_escreve(self):
        sobrevivente = self.primario
        for no in self.cluster.outros(sobrevivente):
            self.cluster.derrubar(no)

        with self.assertRaises((SemQuorum, SomenteLeitura)):
            sobrevivente.executar("op-sozinho", Deposito("alice", 1))
        # E o que não foi confirmado não foi aplicado.
        self.assertEqual(self.cluster.aplicadores[sobrevivente.id].saldo("alice"), 10_000)

    def teste_a_escrita_por_confirmar_e_confirmada_quando_a_maioria_volta(self):
        sobrevivente = self.primario
        caidos = self.cluster.outros(sobrevivente)
        for no in caidos:
            self.cluster.derrubar(no)
        with self.assertRaises((SemQuorum, SomenteLeitura)):
            sobrevivente.executar("op-pendente", Deposito("alice", 1))

        self.cluster.reiniciar(caidos[0].id)
        primario = self.cluster.esperar_primario()
        self.assertTrue(self.cluster.esperar(
            lambda: primario.replicador.vejo_a_maioria()))
        primario.executar("op-pendente", Deposito("alice", 1))

        # Aplicado uma vez só, venha de onde vier.
        self.assertEqual(self.cluster.aplicadores[primario.id].saldo("alice"), 10_001)


class TesteParticao(Base):

    def teste_o_primario_isolado_e_substituido_e_nao_escreve(self):
        """Sem split-brain: do lado minoritário não se confirma nada."""
        isolado = self.primario
        outros = self.cluster.outros(isolado)
        isolado.falhas.isolar([no.id for no in outros])
        for no in outros:
            no.falhas.isolar([isolado.id])

        novo = self.cluster.esperar_primario(outros)
        with self.assertRaises((SemQuorum, SomenteLeitura, NaoSouPrimario)):
            isolado.executar("op-do-isolado", Deposito("alice", 99))
        novo.executar("op-da-maioria", Deposito("alice", 1))

        # A partição sara: o antigo primário vê o epoch maior e despromove-se.
        isolado.falhas.limpar()
        for no in outros:
            no.falhas.limpar()
        self.assertTrue(self.cluster.esperar(lambda: not isolado.eleicao.sou_primario()))
        self.assertTrue(self.cluster.esperar(
            lambda: all(self.cluster.aplicadores[no.id].livro.contas["alice"].saldo_centavos
                        == 10_001 for no in self.cluster.nos)))


if __name__ == "__main__":
    unittest.main()
