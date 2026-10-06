"""Contas, ids e extrato (subfase 1.2)."""

import unittest

from banco.dominio.contas import Livro, Movimento, validar_id
from banco.dominio.erros import ContaDuplicada, ContaInexistente, ValorInvalido


class TesteValidarId(unittest.TestCase):

    def teste_aceita_letras_digitos_traco_e_underscore(self):
        for identificador in ("alice", "conta-1", "conta_1", "a", "x" * 32):
            with self.subTest(identificador=identificador):
                self.assertEqual(validar_id(identificador), identificador)

    def teste_recusa_maiusculas_espacos_e_acentos(self):
        for identificador in ("Alice", "co nta", "josé", "", "x" * 33, "a/b"):
            with self.subTest(identificador=identificador):
                with self.assertRaises(ValorInvalido):
                    validar_id(identificador)


class TesteLivro(unittest.TestCase):

    def setUp(self):
        self.livro = Livro()

    def teste_conta_criada_fica_com_o_saldo_inicial(self):
        self.livro.criar("alice", 10000, 0.0)

        conta = self.livro.obter("alice")

        self.assertEqual(conta.saldo_centavos, 10000)

    def teste_criar_a_mesma_conta_duas_vezes_e_recusado(self):
        self.livro.criar("alice", 0, 0.0)

        with self.assertRaises(ContaDuplicada):
            self.livro.criar("alice", 0, 0.0)

    def teste_obter_conta_que_nao_existe_levanta_erro(self):
        with self.assertRaises(ContaInexistente):
            self.livro.obter("ninguem")

    def teste_total_soma_todos_os_saldos(self):
        self.livro.criar("alice", 10000, 0.0)
        self.livro.criar("bob", 2500, 0.0)

        self.assertEqual(self.livro.total_centavos(), 12500)

    def teste_total_de_livro_vazio_e_zero(self):
        self.assertEqual(self.livro.total_centavos(), 0)

    def teste_extrato_devolve_copia_e_nao_a_lista_interna(self):
        self.livro.criar("alice", 0, 0.0)
        self.livro.registar("alice", Movimento(1, "deposito", 100, None, 100, 0.0))

        copia = self.livro.extrato("alice")
        copia.clear()

        self.assertEqual(len(self.livro.extrato("alice")), 1)


if __name__ == "__main__":
    unittest.main()
