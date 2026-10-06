"""Moedas, câmbio, poupança, prazo fixo e transferência externa (RF-19 a RF-25).

O domínio é puro: o instante entra como argumento, e por isso um prazo fixo
"vence" num teste sem esperar dias nenhuns.
"""

import unittest

from banco.dominio.contas import Livro
from banco.dominio.dinheiro import (converter, formatar, formatar_taxa,
                                    para_milionesimos)
from banco.dominio.erros import (ContaBloqueada, MoedasDiferentes,
                                 SaldoInsuficiente, ValorInvalido)
from banco.dominio.operacoes import (SEGUNDOS_POR_ANO, SEGUNDOS_POR_DIA, Cambio,
                                     CriarConta, DesfechoExterno, Juros, Saque,
                                     Transferencia, TransferenciaExterna,
                                     de_dados, total_esperado)

DEZ_POR_CENTO = 100_000   # em milionésimos


class Base(unittest.TestCase):

    def setUp(self):
        self.livro = Livro()
        self.indice = 0

    def aplicar(self, operacao, instante=0.0):
        self.indice += 1
        return operacao.aplicar(self.livro, self.indice, instante)

    def saldo(self, conta):
        return self.livro.obter(conta).saldo_centavos


class TesteTaxas(unittest.TestCase):

    def teste_taxa_em_texto_vira_milionesimos(self):
        self.assertEqual(para_milionesimos("5.4321"), 5_432_100)

    def teste_taxa_com_sete_casas_e_recusada(self):
        with self.assertRaises(ValorInvalido):
            para_milionesimos("1.1234567")

    def teste_taxa_zero_e_recusada(self):
        with self.assertRaises(ValorInvalido):
            para_milionesimos("0")

    def teste_conversao_arredonda_para_baixo(self):
        # 1,00 USD a 5,4321 dá 5,4321 BRL: o banco paga 5,43 e não inventa 0,0021.
        self.assertEqual(converter(100, 5_432_100), 543)

    def teste_formatar_em_dolares_e_soles(self):
        self.assertEqual((formatar(123456, "USD"), formatar(5, "PEN")),
                         ("US$ 1.234,56", "S/ 0,05"))

    def teste_formatar_taxa(self):
        self.assertEqual(formatar_taxa(5_432_100), "5.432100")


class TesteMoedas(Base):

    def setUp(self):
        super().setUp()
        self.aplicar(CriarConta("real", 10000, moeda="BRL"))
        self.aplicar(CriarConta("dolar", 10000, moeda="USD"))
        self.aplicar(CriarConta("outro-real", 0, moeda="BRL"))

    def teste_moeda_desconhecida_e_recusada(self):
        with self.assertRaises(ValorInvalido):
            self.aplicar(CriarConta("euro", 0, moeda="EUR"))

    def teste_transferencia_entre_moedas_e_recusada(self):
        with self.assertRaises(MoedasDiferentes):
            self.aplicar(Transferencia("real", "dolar", 100))

    def teste_transferencia_na_mesma_moeda_continua_a_funcionar(self):
        self.aplicar(Transferencia("real", "outro-real", 100))
        self.assertEqual(self.saldo("outro-real"), 100)

    def teste_cambio_debita_na_origem_e_credita_convertido(self):
        resposta = self.aplicar(Cambio("dolar", "real", 1000, 5_432_100))

        self.assertEqual((self.saldo("dolar"), self.saldo("real"),
                          resposta["valor_destino_centavos"]),
                         (9000, 10000 + 5432, 5432))

    def teste_cambio_na_mesma_moeda_e_recusado(self):
        with self.assertRaises(ValorInvalido):
            self.aplicar(Cambio("real", "outro-real", 100, 1_000_000))

    def teste_cambio_sem_saldo_e_recusado_sem_mexer_em_nada(self):
        with self.assertRaises(SaldoInsuficiente):
            self.aplicar(Cambio("dolar", "real", 999999, 5_432_100))
        self.assertEqual((self.saldo("dolar"), self.saldo("real")), (10000, 10000))

    def teste_cambio_que_nao_chega_a_um_centavo_e_recusado(self):
        with self.assertRaises(ValorInvalido):
            self.aplicar(Cambio("real", "dolar", 1, 184_162))

    def teste_cambio_reconstroi_se_do_log_com_a_mesma_taxa(self):
        original = Cambio("dolar", "real", 1000, 5_432_100)
        self.assertEqual(de_dados(original.tipo, original.para_dados()), original)


class TestePoupanca(Base):

    def setUp(self):
        super().setUp()
        self.aplicar(CriarConta("poupar", 100_000, produto="poupanca",
                                taxa_juros_milionesimos=DEZ_POR_CENTO), instante=0.0)

    def teste_poupanca_sem_taxa_e_recusada(self):
        with self.assertRaises(ValorInvalido):
            self.aplicar(CriarConta("sem-taxa", 0, produto="poupanca"))

    def teste_corrente_com_taxa_e_recusada(self):
        with self.assertRaises(ValorInvalido):
            self.aplicar(CriarConta("estranha", 0, taxa_juros_milionesimos=1))

    def teste_um_ano_a_dez_por_cento_rende_dez_por_cento(self):
        resposta = self.aplicar(Juros("poupar", float(SEGUNDOS_POR_ANO)))

        self.assertEqual((resposta["juros_centavos"], self.saldo("poupar")),
                         (10_000, 110_000))

    def teste_juros_nao_se_pagam_duas_vezes_pelo_mesmo_periodo(self):
        self.aplicar(Juros("poupar", float(SEGUNDOS_POR_ANO)))
        with self.assertRaises(ValorInvalido):
            self.aplicar(Juros("poupar", float(SEGUNDOS_POR_ANO)))

    def teste_conta_corrente_nao_tem_juros(self):
        self.aplicar(CriarConta("corrente", 100_000))
        with self.assertRaises(ValorInvalido):
            self.aplicar(Juros("corrente", float(SEGUNDOS_POR_ANO)))

    def teste_da_poupanca_pode_sacar_se(self):
        self.aplicar(Saque("poupar", 100))
        self.assertEqual(self.saldo("poupar"), 99_900)


class TestePrazoFixo(Base):

    TRINTA_DIAS = 30 * SEGUNDOS_POR_DIA

    def setUp(self):
        super().setUp()
        self.aplicar(CriarConta("prazo", 100_000, produto="prazo_fixo",
                                taxa_juros_milionesimos=DEZ_POR_CENTO,
                                prazo_dias=30), instante=0.0)
        self.aplicar(CriarConta("livre", 0))

    def teste_prazo_fixo_sem_prazo_e_recusado(self):
        with self.assertRaises(ValorInvalido):
            self.aplicar(CriarConta("sem-prazo", 0, produto="prazo_fixo",
                                    taxa_juros_milionesimos=DEZ_POR_CENTO))

    def teste_saque_antes_do_vencimento_e_bloqueado(self):
        with self.assertRaises(ContaBloqueada):
            self.aplicar(Saque("prazo", 100), instante=self.TRINTA_DIAS - 1)

    def teste_transferencia_antes_do_vencimento_e_bloqueada(self):
        with self.assertRaises(ContaBloqueada):
            self.aplicar(Transferencia("prazo", "livre", 100),
                         instante=self.TRINTA_DIAS - 1)

    def teste_depois_de_vencer_o_dinheiro_sai(self):
        self.aplicar(Saque("prazo", 100), instante=self.TRINTA_DIAS)
        self.assertEqual(self.saldo("prazo"), 99_900)

    def teste_juros_antes_de_vencer_nao_ha(self):
        with self.assertRaises(ValorInvalido):
            self.aplicar(Juros("prazo", self.TRINTA_DIAS - 1))

    def teste_juros_pagam_se_uma_vez_ate_ao_vencimento(self):
        # Pedir os juros um ano depois paga só os 30 dias do prazo.
        resposta = self.aplicar(Juros("prazo", float(SEGUNDOS_POR_ANO)))

        self.assertEqual(resposta["juros_centavos"], 100_000 * 30 // 365 // 10)

    def teste_depois_de_pagos_os_juros_do_prazo_nao_se_repetem(self):
        self.aplicar(Juros("prazo", float(SEGUNDOS_POR_ANO)))
        with self.assertRaises(ValorInvalido):
            self.aplicar(Juros("prazo", float(2 * SEGUNDOS_POR_ANO)))


class TesteTransferenciaExterna(Base):

    def setUp(self):
        super().setUp()
        self.aplicar(CriarConta("alice", 10_000))

    def teste_o_debito_sai_logo(self):
        self.aplicar(TransferenciaExterna("alice", "banco-externo", 2_500))
        self.assertEqual(self.saldo("alice"), 7_500)

    def teste_sem_saldo_nao_sai_nada(self):
        with self.assertRaises(SaldoInsuficiente):
            self.aplicar(TransferenciaExterna("alice", "banco-externo", 99_999))

    def teste_confirmada_nao_devolve(self):
        self.aplicar(TransferenciaExterna("alice", "banco-externo", 2_500))
        self.aplicar(DesfechoExterno("alice", 2_500, True, "ref-1", "op-ext-01"))
        self.assertEqual(self.saldo("alice"), 7_500)

    def teste_rejeitada_devolve_o_valor_inteiro(self):
        self.aplicar(TransferenciaExterna("alice", "banco-externo", 2_500))
        self.aplicar(DesfechoExterno("alice", 2_500, False, None, "op-ext-02"))
        self.assertEqual(self.saldo("alice"), 10_000)

    def teste_o_total_esperado_conta_a_saida_e_a_devolucao(self):
        operacoes = [CriarConta("alice", 10_000),
                     TransferenciaExterna("alice", "banco-externo", 2_500),
                     DesfechoExterno("alice", 2_500, False, None, "op-ext-03"),
                     TransferenciaExterna("alice", "banco-externo", 1_000),
                     DesfechoExterno("alice", 1_000, True, "ref", "op-ext-04")]
        self.assertEqual(total_esperado(operacoes), 9_000)


if __name__ == "__main__":
    unittest.main()
