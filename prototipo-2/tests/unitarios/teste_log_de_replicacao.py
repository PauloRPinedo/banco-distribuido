"""Correspondência de log, truncagem e prefixo confirmado (subfase 2.2)."""

import unittest

from banco.cluster.log_de_replicacao import LogDeReplicacao
from banco.persistencia.armazem_memoria import ArmazemEmMemoria
from banco.persistencia.entrada import EntradaDeLog


def entrada(indice, epoch=1):
    return EntradaDeLog(indice=indice, epoch=epoch, op_id=f"op-{indice}",
                        tipo="deposito",
                        dados={"conta": "alice", "valor_centavos": 100},
                        instante=1756742400.0)


class BaseComLog(unittest.TestCase):

    def setUp(self):
        self.log = LogDeReplicacao(ArmazemEmMemoria())

    def encher(self, quantos, epoch=1):
        for indice in range(1, quantos + 1):
            self.log.acrescentar(entrada(indice, epoch))


class TesteCorrespondencia(BaseComLog):

    def teste_indice_zero_corresponde_sempre(self):
        """Índice 0 é "antes do princípio": não há nada com que discordar."""
        self.assertTrue(self.log.corresponde(0, 0))

    def teste_corresponde_quando_o_epoch_bate(self):
        self.encher(3)

        self.assertTrue(self.log.corresponde(3, 1))

    def teste_nao_corresponde_com_epoch_diferente(self):
        """É aqui que se apanha um log divergente sem comparar tudo.

        Se concordamos no índice e no epoch da entrada anterior, concordamos em
        tudo o que vem antes — e daí para trás não é preciso olhar.
        """
        self.encher(3)

        self.assertFalse(self.log.corresponde(3, 9))

    def teste_nao_corresponde_com_indice_que_nao_tenho(self):
        self.encher(3)

        self.assertFalse(self.log.corresponde(7, 1))


class TesteAcrescentarDoLider(BaseComLog):

    def teste_aceita_entradas_novas(self):
        self.log.acrescentar_do_lider([entrada(1), entrada(2)])

        self.assertEqual(self.log.ultimo_indice, 2)

    def teste_lote_vazio_nao_faz_nada(self):
        self.encher(2)

        self.log.acrescentar_do_lider([])

        self.assertEqual(self.log.ultimo_indice, 2)

    def teste_repetir_um_lote_ja_recebido_e_inofensivo(self):
        """O líder reenvia quando a resposta se perde; não pode duplicar nada."""
        self.log.acrescentar_do_lider([entrada(1), entrada(2)])

        self.log.acrescentar_do_lider([entrada(1), entrada(2)])

        self.assertEqual(self.log.ultimo_indice, 2)
        self.assertEqual(len(self.log.ler_desde(0)), 2)

    def teste_entradas_divergentes_sao_substituidas(self):
        """O log do líder ganha: é ele que tem o mandato."""
        self.encher(3, epoch=1)

        self.log.acrescentar_do_lider([entrada(2, epoch=5), entrada(3, epoch=5)])

        epochs = [e.epoch for e in self.log.ler_desde(0)]
        self.assertEqual(epochs, [1, 5, 5])


class TesteTruncar(BaseComLog):

    def teste_trunca_a_partir_do_indice(self):
        self.encher(5)

        self.log.truncar_divergentes(3)

        self.assertEqual([e.indice for e in self.log.ler_desde(0)], [1, 2])

    def teste_truncar_acima_do_fim_nao_faz_nada(self):
        self.encher(2)

        self.log.truncar_divergentes(9)

        self.assertEqual(self.log.ultimo_indice, 2)

    def teste_nunca_trunca_abaixo_do_commit(self):
        """A regra que não se negoceia.

        Uma entrada confirmada já foi prometida a um cliente. Apagá-la é dinheiro
        a desaparecer — a única coisa que este projeto existe para impedir. Não é
        defesa contra o protocolo, que garante que não acontece: é a rede que
        apanha um erro nosso antes de ele custar dinheiro.
        """
        self.encher(5)
        self.log.confirmar_ate(3)

        with self.assertRaises(ValueError) as capturado:
            self.log.truncar_divergentes(3)

        self.assertIn("confirmadas", str(capturado.exception))

    def teste_pode_truncar_acima_do_commit(self):
        self.encher(5)
        self.log.confirmar_ate(3)

        self.log.truncar_divergentes(4)

        self.assertEqual(self.log.ultimo_indice, 3)


class TesteCommit(BaseComLog):

    def teste_avanca(self):
        self.encher(5)

        self.log.confirmar_ate(3)

        self.assertEqual(self.log.indice_commit, 3)

    def teste_nunca_recua(self):
        self.encher(5)
        self.log.confirmar_ate(4)

        self.log.confirmar_ate(2)

        self.assertEqual(self.log.indice_commit, 4)

    def teste_nunca_passa_do_que_tenho(self):
        """O líder anuncia o commit dele, que pode estar à frente desta réplica.

        Confirmar o que ainda não se recebeu seria dizer que se guardou o que não
        se guardou — e uma réplica assim ganharia uma eleição que não merece.
        """
        self.encher(2)

        self.log.confirmar_ate(99)

        self.assertEqual(self.log.indice_commit, 2)

    def teste_sobrevive_a_reabertura_do_log(self):
        armazem = ArmazemEmMemoria()
        primeiro = LogDeReplicacao(armazem)
        primeiro.acrescentar(entrada(1))
        primeiro.confirmar_ate(1)

        segundo = LogDeReplicacao(armazem)

        self.assertEqual(segundo.indice_commit, 1)
        self.assertEqual(segundo.ultimo_indice, 1)


if __name__ == "__main__":
    unittest.main()
