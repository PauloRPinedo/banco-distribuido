"""O número visível da conta: dígito verificador, normalização e sorteio."""

import unittest

from banco.dominio import numero_conta
from banco.dominio.erros import ValorInvalido
from banco.dominio.operacoes import CriarConta, de_dados
from banco.dominio.contas import Livro


class TesteDigitoVerificador(unittest.TestCase):

    def teste_casos_calculados_a_mao(self):
        # 12345678: 8*2+7*3+6*4+5*5+4*6+3*7+2*8+1*9 = 156; 156 % 11 = 2; 11-2 = 9
        self.assertEqual(numero_conta.digito_verificador("12345678"), "9")
        # 00000000: resto 0 dá 0
        self.assertEqual(numero_conta.digito_verificador("00000000"), "0")

    def teste_resto_um_tambem_da_zero(self):
        corpo = next(f"{n:08d}" for n in range(1000)
                     if sum(int(d) * p for d, p in zip(reversed(f"{n:08d}"),
                                                        (2, 3, 4, 5, 6, 7, 8, 9))) % 11 == 1)
        self.assertEqual(numero_conta.digito_verificador(corpo), "0")

    def teste_um_digito_trocado_deixa_de_validar(self):
        self.assertTrue(numero_conta.e_valido("12345678-9"))
        self.assertFalse(numero_conta.e_valido("12345679-9"))
        self.assertFalse(numero_conta.e_valido("12345678-8"))

    def teste_corpo_mal_formado_e_recusado(self):
        for corpo in ("1234567", "123456789", "1234567a", 12345678):
            with self.subTest(corpo=corpo), self.assertRaises(ValorInvalido):
                numero_conta.digito_verificador(corpo)


class TesteNormalizar(unittest.TestCase):

    def teste_aceita_o_que_uma_pessoa_escreve(self):
        for texto in ("12345678-9", "123456789", "0001 / 12345678-9",
                      "0001123456789", " 1234.5678-9 "):
            with self.subTest(texto=texto):
                self.assertEqual(numero_conta.normalizar(texto), "12345678-9")

    def teste_recusa_digito_errado_e_comprimento_errado(self):
        for texto in ("12345678-0", "1234", "alice", "00011234567890"):
            with self.subTest(texto=texto), self.assertRaises(ValorInvalido):
                numero_conta.normalizar(texto)

    def teste_parece_numero(self):
        self.assertTrue(numero_conta.parece_numero("0001 / 12345678-9"))
        self.assertFalse(numero_conta.parece_numero("alice"))

    def teste_formatar(self):
        self.assertEqual(numero_conta.formatar("12345678-9"), "0001 / 12345678-9")


class TesteSorteio(unittest.TestCase):

    def teste_o_sorteado_e_sempre_valido(self):
        for _ in range(500):
            self.assertTrue(numero_conta.e_valido(numero_conta.sortear()))


class TesteCriarContaComNumero(unittest.TestCase):

    def teste_o_numero_fica_na_conta_e_na_resposta(self):
        livro = Livro()
        resposta = CriarConta("alice", 100, numero="12345678-9").aplicar(livro, 1, 0.0)

        self.assertEqual(livro.obter("alice").numero, "12345678-9")
        self.assertEqual((resposta["agencia"], resposta["numero"]), ("0001", "12345678-9"))

    def teste_numero_invalido_e_recusado(self):
        with self.assertRaises(ValorInvalido):
            CriarConta("alice", 0, numero="12345678-0").validar(Livro(), 0.0)

    def teste_viaja_no_log_e_volta_igual(self):
        operacao = CriarConta("alice", 0, numero="12345678-9")
        self.assertEqual(de_dados(operacao.tipo, operacao.para_dados()), operacao)

    def teste_entrada_antiga_sem_numero_continua_a_ler_se(self):
        dados = CriarConta("alice", 0).para_dados()
        del dados["numero"]
        self.assertIsNone(de_dados("criar_conta", dados).numero)


if __name__ == "__main__":
    unittest.main()
