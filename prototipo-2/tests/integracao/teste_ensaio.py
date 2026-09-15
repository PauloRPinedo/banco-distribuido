"""A sessão de ensaio exclusiva e a injeção de falhas (subfase 3.1).

O que está aqui a ser testado é uma regra de operação, não de banco: na
demonstração há dois laptops e três pessoas, todas com o CLI, e dois operadores a
derrubar nós ao mesmo tempo produzem um cluster sem maioria por acidente. O que
se vê no ecrã deixaria de ser a experiência que se estava a fazer.
"""

import time
import unittest

from banco.cluster.ensaio import EnsaioTomado, TrancaDeEnsaio
from banco.cluster.falhas import InjetorDeFalhas
from banco.dominio.operacoes import CriarConta
from tests.ajudas import (criar_cluster_de_teste, esperar_ate,
                          esperar_por_primario)


class TesteTranca(unittest.TestCase):

    def setUp(self):
        self.tranca = TrancaDeEnsaio()

    def teste_livre_deixa_passar_qualquer_um(self):
        """Exigir a sessão para uma única experiência seria burocracia."""
        self.tranca.verificar(None)

    def teste_o_dono_passa(self):
        fixacao = self.tranca.tomar("paulo")

        self.tranca.verificar(fixacao)

    def teste_o_segundo_operador_e_recusado(self):
        self.tranca.tomar("paulo")

        with self.assertRaises(EnsaioTomado) as capturado:
            self.tranca.verificar("fixacao-do-cristhian")

        self.assertEqual(capturado.exception.dono, "paulo")
        self.assertEqual(capturado.exception.estado_http, 409)

    def teste_o_segundo_operador_nao_consegue_tomar(self):
        self.tranca.tomar("paulo")

        with self.assertRaises(EnsaioTomado):
            self.tranca.tomar("cristhian")

    def teste_o_mesmo_dono_pode_retomar(self):
        """Repetir o comando não é um erro.

        Recusar aqui seria dizer "não podes porque és tu".
        """
        primeira = self.tranca.tomar("paulo")

        segunda = self.tranca.tomar("paulo")

        self.assertNotEqual(primeira, segunda)

    def teste_a_caducidade_liberta(self):
        """Para o operador que toma a sessão e vai almoçar."""
        self.tranca.tomar("paulo", duracao_s=0)

        self.tranca.verificar(None)

    def teste_largar_com_a_fixacao_errada_nao_larga(self):
        self.tranca.tomar("paulo")

        self.assertFalse(self.tranca.largar("inventada"))

    def teste_largar_liberta_para_o_seguinte(self):
        fixacao = self.tranca.tomar("paulo")

        self.tranca.largar(fixacao)

        self.tranca.tomar("cristhian")

    def teste_renovar_empurra_a_caducidade(self):
        fixacao = self.tranca.tomar("paulo", duracao_s=1)
        antes = self.tranca.expira_em

        self.tranca.renovar(fixacao, duracao_s=60)

        self.assertGreater(self.tranca.expira_em, antes)

    def teste_a_mensagem_diz_o_dono_e_quanto_falta(self):
        """A terceira linha do erro tem de ser acionável."""
        self.tranca.tomar("cristhian", duracao_s=180)

        with self.assertRaises(EnsaioTomado) as capturado:
            self.tranca.verificar("outra")

        corpo = capturado.exception.para_json()
        self.assertEqual(corpo["dono"], "cristhian")
        self.assertIn("180", corpo["falta_s"])


class TesteInjetor(unittest.TestCase):

    def teste_isolar_corta_nos_dois_sentidos(self):
        """Uma partição que só corta um lado não existe na rede real."""
        injetor = InjetorDeFalhas()

        injetor.isolar(["B"])

        self.assertFalse(injetor.fala_com("B"))
        self.assertTrue(injetor.fala_com("C"))

    def teste_limpar_repoe_tudo(self):
        injetor = InjetorDeFalhas()
        injetor.isolar(["B"])
        injetor.atraso(500)

        injetor.limpar()

        self.assertTrue(injetor.fala_com("B"))
        self.assertEqual(injetor.em_json()["atraso_ms"], 0)

    def teste_o_atraso_atrasa_mesmo(self):
        injetor = InjetorDeFalhas()
        injetor.atraso(50)

        comeco = time.monotonic()
        injetor.talvez_atrasar()

        self.assertGreaterEqual(time.monotonic() - comeco, 0.045)


class TesteExclusaoNoCluster(unittest.TestCase):
    """A regra que o enunciado pede: enquanto um opera, o outro não pode."""

    def setUp(self):
        self.cluster = criar_cluster_de_teste(self)
        self.primario = esperar_por_primario(self, self.cluster.nos)

    def teste_a_sessao_chega_as_replicas_pelo_heartbeat(self):
        """É o que permite a uma réplica recusar sem perguntar a ninguém."""
        self.primario.ensaio.tomar("paulo")

        chegou = esperar_ate(
            lambda: all(no.ensaio.em_json().get("dono") == "paulo"
                        for no in self.cluster.outros(self.primario)))

        self.assertTrue(chegou,
                        {no.id: no.ensaio.em_json()
                         for no in self.cluster.outros(self.primario)})

    def teste_o_segundo_operador_e_recusado_noutro_no(self):
        """Tomar no primário e tentar injetar numa réplica tem de falhar.

        Se a tranca fosse local a cada nó, isto passava — e a exclusão não
        excluiria nada, que é o erro que este desenho evita.
        """
        self.primario.ensaio.tomar("paulo")
        replica = self.cluster.outros(self.primario)[0]
        esperar_ate(lambda: replica.ensaio.em_json().get("dono") == "paulo")

        with self.assertRaises(EnsaioTomado):
            replica.ensaio.verificar("fixacao-do-cristhian")

    def teste_o_isolamento_tira_um_no_do_quorum(self):
        """Uma partição sem tocar na firewall (F-10)."""
        self.primario.executar("c1", CriarConta("alice", 10000))
        replicas = self.cluster.outros(self.primario)

        for replica in replicas:
            replica.falhas.isolar([self.primario.id])

        # Sem ninguém a confirmar, o primário perde o quórum e deixa de escrever.
        parou = esperar_ate(
            lambda: not self.primario.replicador.vejo_a_maioria(), limite=3.0)

        self.assertTrue(parou, "o primário continuou a ver a maioria")


if __name__ == "__main__":
    unittest.main()
