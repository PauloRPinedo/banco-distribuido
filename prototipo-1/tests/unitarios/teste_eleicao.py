"""A máquina de estados da eleição, sem rede nenhuma (subfases 2.4 e 2.5).

Testa-se em memória e sem sockets de propósito: as garantias da secção 8 do SPECS
são sobre **decisões**, não sobre transporte. Um teste que precise de três
servidores para provar que ninguém vota duas vezes está a testar a coisa errada.
"""

import unittest

from banco.cluster.configuracao import ConfiguracaoDoCluster
from banco.cluster.eleicao import (CANDIDATO, PRIMARIO, REPLICA, Eleicao,
                                   PedidoDeVoto)

INTERVALO = (800, 1500)


def eleicao(id_do_no="A", semente=42, epoch=1, votou_em=None):
    return Eleicao(id_do_no, semente, INTERVALO, epoch, votou_em)


class TestePapelInicial(unittest.TestCase):

    def teste_arranca_sempre_como_replica(self):
        """SPECS 4.2: quem manda decide-se por eleição, nunca pela memória."""
        self.assertEqual(eleicao().papel, REPLICA)

    def teste_lembra_se_do_epoch_gravado(self):
        self.assertEqual(eleicao(epoch=7).epoch, 7)

    def teste_lembra_se_de_em_quem_votou(self):
        """Um voto esquecido é um voto repetido, e dois primários no mesmo epoch."""
        self.assertEqual(eleicao(epoch=7, votou_em="B").votou_em, "B")


class TesteSementeDerivada(unittest.TestCase):

    def teste_nos_diferentes_sorteiam_timeouts_diferentes(self):
        """O erro mais caro da etapa, segundo o ROADMAP.

        Com a mesma semente nos três, todos se candidatam ao mesmo tempo,
        dividem os votos, e a eleição nunca converge — com um sintoma que parece
        um erro de protocolo.
        """
        configuracao = ConfiguracaoDoCluster.de_dados({
            "nos": [{"id": id_, "endereco": "127.0.0.1", "porta": 8000 + i}
                    for i, id_ in enumerate("ABC")],
            "heartbeat_ms": 150, "timeout_eleicao_ms": [800, 1500],
            "timeout_replicacao_ms": 500, "semente": 42})

        timeouts = {
            Eleicao(id_, configuracao.semente_do_no(id_), INTERVALO)._timeout_s
            for id_ in "ABC"}

        self.assertEqual(len(timeouts), 3, f"timeouts iguais: {timeouts}")

    def teste_a_mesma_semente_da_o_mesmo_timeout(self):
        """RNF-06: a mesma semente global reproduz a mesma execução."""
        self.assertEqual(eleicao(semente=7)._timeout_s,
                         eleicao(semente=7)._timeout_s)

    def teste_o_timeout_cai_dentro_do_intervalo(self):
        for semente in range(50):
            timeout = eleicao(semente=semente)._timeout_s

            self.assertGreaterEqual(timeout, INTERVALO[0] / 1000)
            self.assertLessEqual(timeout, INTERVALO[1] / 1000)


class TesteCandidatura(unittest.TestCase):

    def teste_candidatar_sobe_o_epoch_e_vota_em_si(self):
        eleitor = eleicao()

        pedido = eleitor.candidatar(5, 1)

        self.assertEqual(pedido.epoch, 2)
        self.assertEqual(eleitor.papel, CANDIDATO)
        self.assertEqual(eleitor.votou_em, "A")

    def teste_o_pedido_leva_o_estado_do_log(self):
        pedido = eleicao().candidatar(42, 7)

        self.assertEqual((pedido.ultimo_indice, pedido.ultimo_epoch), (42, 7))

    def teste_um_primario_nao_se_candidata(self):
        eleitor = eleicao()
        eleitor.candidatar(0, 0)
        eleitor.assumir(2)

        self.assertIsNone(eleitor.candidatar(0, 0))

    def teste_assumir_falha_se_o_epoch_mudou(self):
        """Entre pedir os votos e contá-los pode ter chegado um epoch maior.

        Assumir aí criaria o segundo primário que todo o desenho impede.
        """
        eleitor = eleicao()
        eleitor.candidatar(0, 0)
        eleitor.ver_epoch(99)

        self.assertFalse(eleitor.assumir(2))
        self.assertEqual(eleitor.papel, REPLICA)


class TesteFencing(unittest.TestCase):

    def teste_epoch_maior_despromove_o_primario(self):
        """SPECS 8.3: um primário antigo que volta descobre aqui que já não manda."""
        eleitor = eleicao()
        eleitor.candidatar(0, 0)
        eleitor.assumir(2)

        despromovido = eleitor.ver_epoch(3)

        self.assertTrue(despromovido)
        self.assertEqual(eleitor.papel, REPLICA)
        self.assertEqual(eleitor.epoch, 3)

    def teste_epoch_igual_ou_menor_nao_despromove(self):
        eleitor = eleicao(epoch=5)
        eleitor.candidatar(0, 0)
        eleitor.assumir(6)

        self.assertFalse(eleitor.ver_epoch(6))
        self.assertEqual(eleitor.papel, PRIMARIO)

    def teste_ver_epoch_maior_esquece_o_voto(self):
        eleitor = eleicao(epoch=2, votou_em="B")

        eleitor.ver_epoch(3)

        self.assertIsNone(eleitor.votou_em)


class TesteVoto(unittest.TestCase):

    def teste_concede_ao_candidato_em_dia(self):
        concedido, _ = eleicao().conceder_voto(PedidoDeVoto(2, "B", 5, 1), 5, 1)

        self.assertTrue(concedido)

    def teste_recusa_epoch_menor(self):
        eleitor = eleicao(epoch=5)

        concedido, motivo = eleitor.conceder_voto(
            PedidoDeVoto(3, "B", 5, 1), 5, 1)

        self.assertFalse(concedido)
        self.assertIn("menor", motivo)

    def teste_nao_vota_duas_vezes_no_mesmo_epoch(self):
        """Sem isto, dois candidatos diferentes poderiam somar maioria."""
        eleitor = eleicao()
        eleitor.conceder_voto(PedidoDeVoto(2, "B", 5, 1), 5, 1)

        concedido, motivo = eleitor.conceder_voto(
            PedidoDeVoto(2, "C", 5, 1), 5, 1)

        self.assertFalse(concedido)
        self.assertIn("já votei", motivo)

    def teste_repetir_o_pedido_do_mesmo_candidato_e_aceite(self):
        """A resposta pode ter-se perdido; repetir tem de ser seguro."""
        eleitor = eleicao()
        eleitor.conceder_voto(PedidoDeVoto(2, "B", 5, 1), 5, 1)

        concedido, _ = eleitor.conceder_voto(PedidoDeVoto(2, "B", 5, 1), 5, 1)

        self.assertTrue(concedido)

    def teste_recusa_candidato_com_log_atrasado(self):
        """A condição 3: é ela que impede uma operação confirmada de se perder."""
        eleitor = eleicao()

        concedido, motivo = eleitor.conceder_voto(
            PedidoDeVoto(2, "B", 3, 1), ultimo_indice=9, ultimo_epoch=1)

        self.assertFalse(concedido)
        self.assertIn("atrasado", motivo)

    def teste_o_epoch_do_log_pesa_mais_que_o_indice(self):
        """Um log mais curto mas de um epoch mais recente ganha.

        Comparar só o índice deixaria um nó com muitas entradas por confirmar de
        um mandato velho vencer quem tem o mandato novo.
        """
        eleitor = eleicao()

        concedido, _ = eleitor.conceder_voto(
            PedidoDeVoto(9, "B", ultimo_indice=2, ultimo_epoch=5),
            ultimo_indice=40, ultimo_epoch=4)

        self.assertTrue(concedido)

    def teste_epoch_novo_esquece_o_voto_anterior(self):
        eleitor = eleicao()
        eleitor.conceder_voto(PedidoDeVoto(2, "B", 5, 1), 5, 1)

        concedido, _ = eleitor.conceder_voto(PedidoDeVoto(3, "C", 5, 1), 5, 1)

        self.assertTrue(concedido)

    def teste_o_motivo_da_recusa_e_sempre_dito(self):
        """CODESTYLE secção 10: sem o motivo, depurar uma eleição é adivinhar."""
        eleitor = eleicao(epoch=9)

        _, motivo = eleitor.conceder_voto(PedidoDeVoto(2, "B", 5, 1), 5, 1)

        self.assertTrue(motivo.strip())


class TesteHeartbeat(unittest.TestCase):

    def teste_ver_o_lider_reinicia_o_relogio(self):
        eleitor = eleicao()

        eleitor.vi_o_lider("B", 2)

        self.assertFalse(eleitor.timeout_expirou())
        self.assertEqual(eleitor.lider_conhecido, "B")

    def teste_ver_o_lider_despromove_um_candidato(self):
        eleitor = eleicao()
        eleitor.candidatar(0, 0)

        eleitor.vi_o_lider("B", 5)

        self.assertEqual(eleitor.papel, REPLICA)

    def teste_um_primario_nunca_expira(self):
        eleitor = eleicao()
        eleitor.candidatar(0, 0)
        eleitor.assumir(2)

        self.assertFalse(eleitor.timeout_expirou())


if __name__ == "__main__":
    unittest.main()
