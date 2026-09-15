"""O `Pedido` e o despacho de rotas (subfase 2.1)."""

import unittest

from banco.interface import despacho
from banco.interface.pedido import Pedido


class TesteInteiroDaConsulta(unittest.TestCase):

    def teste_le_o_valor(self):
        self.assertEqual(Pedido(consulta={"desde": ["7"]}).inteiro("desde"), 7)

    def teste_ausente_da_o_valor_por_omissao(self):
        self.assertEqual(Pedido().inteiro("desde", 3), 3)

    def teste_ilegivel_da_o_valor_por_omissao(self):
        """`?desde=abc` vale "manda o que tiveres", não um erro.

        Quem pergunta é outro nó a tentar pôr-se em dia. Recusar daria a um erro
        de escrita o poder de travar uma réplica que está a recuperar.
        """
        self.assertEqual(Pedido(consulta={"desde": ["abc"]}).inteiro("desde"), 0)

    def teste_vazio_da_o_valor_por_omissao(self):
        self.assertEqual(Pedido(consulta={"desde": [""]}).inteiro("desde"), 0)


class TesteDespacho(unittest.TestCase):

    def teste_encontra_rota_de_cliente(self):
        funcao, partes = despacho.encontrar("GET", "/contas/alice")

        self.assertEqual(funcao.__name__, "consultar_saldo")
        self.assertEqual(partes, ("alice",))

    def teste_extrato_ganha_ao_saldo(self):
        """A ordem dentro da tabela importa: /contas/{id} apanharia o extrato."""
        funcao, _ = despacho.encontrar("GET", "/contas/alice/extrato")

        self.assertEqual(funcao.__name__, "consultar_extrato")

    def teste_encontra_rota_interna(self):
        funcao, _ = despacho.encontrar("GET", "/interno/estado")

        self.assertEqual(funcao.__name__, "estado")

    def teste_metodo_errado_nao_encontra(self):
        self.assertIsNone(despacho.encontrar("POST", "/auditoria"))

    def teste_caminho_existe_ignora_o_metodo(self):
        """É o que permite responder ao preflight sem dizer que sim a tudo."""
        self.assertTrue(despacho.caminho_existe("/auditoria"))
        self.assertFalse(despacho.caminho_existe("/inventada"))


if __name__ == "__main__":
    unittest.main()
