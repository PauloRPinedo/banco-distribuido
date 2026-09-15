"""Conversão e formatação de dinheiro (subfase 1.2)."""

import unittest

from banco.dominio.dinheiro import formatar, para_centavos
from banco.dominio.erros import ValorInvalido


class TesteParaCentavos(unittest.TestCase):

    def teste_ponto_e_virgula_dao_o_mesmo_valor(self):
        self.assertEqual(para_centavos("123.45"), 12345)
        self.assertEqual(para_centavos("123,45"), 12345)

    def teste_valor_sem_decimais_e_aceite(self):
        self.assertEqual(para_centavos("100"), 10000)

    def teste_uma_casa_decimal_e_aceite(self):
        self.assertEqual(para_centavos("1.5"), 150)

    def teste_zero_e_aceite_como_texto(self):
        self.assertEqual(para_centavos("0"), 0)

    def teste_espacos_a_volta_sao_ignorados(self):
        self.assertEqual(para_centavos("  12.30  "), 1230)

    def teste_tres_casas_decimais_sao_recusadas(self):
        # 10.005 não tem representação em centavos; aceitá-la seria arredondar
        # dinheiro sem o cliente saber.
        with self.assertRaises(ValorInvalido):
            para_centavos("10.005")

    def teste_valor_negativo_e_recusado(self):
        with self.assertRaises(ValorInvalido):
            para_centavos("-1.00")

    def teste_texto_sem_numero_e_recusado(self):
        for entrada in ("", "abc", "1.2.3", "R$ 10", "1e5", " "):
            with self.subTest(entrada=entrada):
                with self.assertRaises(ValorInvalido):
                    para_centavos(entrada)


class TesteFormatar(unittest.TestCase):

    def teste_usa_ponto_nos_milhares_e_virgula_nos_decimais(self):
        self.assertEqual(formatar(123456), "R$ 1.234,56")

    def teste_completa_os_centavos_com_zero(self):
        self.assertEqual(formatar(1200), "R$ 12,00")
        self.assertEqual(formatar(5), "R$ 0,05")

    def teste_zero(self):
        self.assertEqual(formatar(0), "R$ 0,00")

    def teste_milhoes(self):
        self.assertEqual(formatar(123456789), "R$ 1.234.567,89")

    def teste_negativo_leva_o_sinal_a_frente(self):
        # Um saldo nunca é negativo, mas a divergência de auditoria pode ser.
        self.assertEqual(formatar(-150), "-R$ 1,50")


class TesteIdaEVolta(unittest.TestCase):

    def teste_converter_e_formatar_devolve_o_valor_original(self):
        # Sem float em lado nenhum, nem no teste: é a regra que o projeto
        # inteiro defende.
        casos = [("0.01", "R$ 0,01"),
                 ("1.00", "R$ 1,00"),
                 ("999.99", "R$ 999,99"),
                 ("1234.56", "R$ 1.234,56"),
                 ("1000000.00", "R$ 1.000.000,00")]
        for texto, esperado in casos:
            with self.subTest(texto=texto):
                self.assertEqual(formatar(para_centavos(texto)), esperado)


if __name__ == "__main__":
    unittest.main()
