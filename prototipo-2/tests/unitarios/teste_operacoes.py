"""As quatro operações e o extrato (subfase 1.3)."""

import unittest

from banco.dominio.contas import Livro
from banco.dominio.erros import (ContaDuplicada, ContaInexistente,
                                 SaldoInsuficiente, ValorInvalido)
from banco.dominio.operacoes import (CriarConta, Deposito, Saque, Transferencia,
                                     de_dados, total_esperado)


class BaseComDuasContas(unittest.TestCase):

    def setUp(self):
        self.livro = Livro()
        self.indice = 0
        self.aplicar(CriarConta("alice", 10000))
        self.aplicar(CriarConta("bob", 0))

    def aplicar(self, operacao):
        self.indice += 1
        return operacao.aplicar(self.livro, self.indice, 0.0)

    def saldo(self, conta):
        return self.livro.obter(conta).saldo_centavos


class TesteCriarConta(BaseComDuasContas):

    def teste_conta_nasce_com_o_saldo_inicial(self):
        self.assertEqual(self.saldo("alice"), 10000)

    def teste_id_invalido_e_recusado(self):
        with self.assertRaises(ValorInvalido):
            self.aplicar(CriarConta("Alice Maiuscula", 0))

    def teste_saldo_inicial_negativo_e_recusado(self):
        with self.assertRaises(ValorInvalido):
            self.aplicar(CriarConta("carla", -1))

    def teste_conta_repetida_e_recusada(self):
        with self.assertRaises(ContaDuplicada):
            self.aplicar(CriarConta("alice", 0))


class TesteDeposito(BaseComDuasContas):

    def teste_deposito_aumenta_o_saldo(self):
        self.aplicar(Deposito("bob", 2500))

        self.assertEqual(self.saldo("bob"), 2500)

    def teste_deposito_de_zero_e_recusado(self):
        with self.assertRaises(ValorInvalido):
            self.aplicar(Deposito("bob", 0))

    def teste_deposito_negativo_e_recusado(self):
        with self.assertRaises(ValorInvalido):
            self.aplicar(Deposito("bob", -100))

    def teste_deposito_em_conta_inexistente_e_recusado(self):
        with self.assertRaises(ContaInexistente):
            self.aplicar(Deposito("ninguem", 100))


class TesteSaque(BaseComDuasContas):

    def teste_saque_diminui_o_saldo(self):
        self.aplicar(Saque("alice", 2500))

        self.assertEqual(self.saldo("alice"), 7500)

    def teste_saque_do_saldo_inteiro_e_permitido(self):
        self.aplicar(Saque("alice", 10000))

        self.assertEqual(self.saldo("alice"), 0)

    def teste_saque_maior_que_o_saldo_e_recusado(self):
        with self.assertRaises(SaldoInsuficiente):
            self.aplicar(Saque("alice", 10001))

    def teste_saque_recusado_nao_mexe_no_saldo(self):
        try:
            self.aplicar(Saque("alice", 10001))
        except SaldoInsuficiente:
            pass

        self.assertEqual(self.saldo("alice"), 10000)

    def teste_mensagem_do_erro_traz_os_dois_valores(self):
        with self.assertRaises(SaldoInsuficiente) as capturado:
            self.aplicar(Saque("alice", 50000))

        self.assertIn("R$ 100,00", capturado.exception.mensagem)
        self.assertIn("R$ 500,00", capturado.exception.mensagem)


class TesteTransferencia(BaseComDuasContas):

    def teste_move_o_valor_entre_as_duas_contas(self):
        self.aplicar(Transferencia("alice", "bob", 2500))

        self.assertEqual(self.saldo("alice"), 7500)
        self.assertEqual(self.saldo("bob"), 2500)

    def teste_nao_muda_o_total_em_circulacao(self):
        antes = self.livro.total_centavos()

        self.aplicar(Transferencia("alice", "bob", 2500))

        self.assertEqual(self.livro.total_centavos(), antes)

    def teste_transferencia_sem_saldo_e_recusada(self):
        with self.assertRaises(SaldoInsuficiente):
            self.aplicar(Transferencia("alice", "bob", 10001))

    def teste_transferencia_recusada_nao_mexe_em_nenhuma_conta(self):
        try:
            self.aplicar(Transferencia("alice", "bob", 10001))
        except SaldoInsuficiente:
            pass

        self.assertEqual(self.saldo("alice"), 10000)
        self.assertEqual(self.saldo("bob"), 0)

    def teste_transferir_para_a_propria_conta_e_recusado(self):
        with self.assertRaises(ValorInvalido):
            self.aplicar(Transferencia("alice", "alice", 100))

    def teste_destino_inexistente_e_recusado_sem_debitar(self):
        with self.assertRaises(ContaInexistente):
            self.aplicar(Transferencia("alice", "ninguem", 100))

        self.assertEqual(self.saldo("alice"), 10000)


class TesteContasTocadas(unittest.TestCase):

    def teste_transferencia_devolve_as_contas_por_ordem_crescente(self):
        # A ordem total dos locks nasce aqui. Se esta ordenação desaparecer,
        # alice->bob e bob->alice em paralelo passam a poder ficar em deadlock.
        self.assertEqual(Transferencia("zoe", "ana", 1).contas_tocadas(),
                         ("ana", "zoe"))
        self.assertEqual(Transferencia("ana", "zoe", 1).contas_tocadas(),
                         ("ana", "zoe"))

    def teste_operacoes_de_uma_conta_devolvem_so_essa(self):
        self.assertEqual(Deposito("alice", 1).contas_tocadas(), ("alice",))
        self.assertEqual(Saque("alice", 1).contas_tocadas(), ("alice",))
        self.assertEqual(CriarConta("alice", 1).contas_tocadas(), ("alice",))


class TesteExtrato(BaseComDuasContas):

    def teste_transferencia_aparece_nas_duas_contas_com_sinais_opostos(self):
        self.aplicar(Transferencia("alice", "bob", 2500))

        saida = self.livro.extrato("alice")[-1]
        entrada = self.livro.extrato("bob")[-1]

        self.assertEqual(saida.valor_centavos, -2500)
        self.assertEqual(entrada.valor_centavos, 2500)
        self.assertEqual(saida.contraparte, "bob")
        self.assertEqual(entrada.contraparte, "alice")

    def teste_movimento_guarda_o_saldo_depois(self):
        self.aplicar(Deposito("bob", 2500))

        self.assertEqual(self.livro.extrato("bob")[-1].saldo_depois_centavos, 2500)


class TesteSerializacao(unittest.TestCase):

    def teste_operacao_sobrevive_a_ida_e_volta_pelo_log(self):
        for operacao in (CriarConta("alice", 100), Deposito("alice", 50),
                         Saque("alice", 25), Transferencia("alice", "bob", 10)):
            with self.subTest(tipo=operacao.tipo):
                voltou = de_dados(operacao.tipo, operacao.para_dados())

                self.assertEqual(voltou, operacao)

    def teste_tipo_desconhecido_e_recusado(self):
        with self.assertRaises(ValorInvalido):
            de_dados("pagar_juros", {})


class TesteTotalEsperado(BaseComDuasContas):

    def teste_bate_com_a_soma_dos_saldos(self):
        operacoes = [CriarConta("alice", 10000), CriarConta("bob", 0),
                     Deposito("bob", 500), Saque("alice", 200),
                     Transferencia("alice", "bob", 1000)]
        livro = Livro()
        for indice, operacao in enumerate(operacoes, 1):
            operacao.aplicar(livro, indice, 0.0)

        self.assertEqual(livro.total_centavos(), total_esperado(operacoes))

    def teste_transferencia_e_neutra_no_total(self):
        so_transferencias = [CriarConta("alice", 10000), CriarConta("bob", 0),
                             Transferencia("alice", "bob", 4000)]

        self.assertEqual(total_esperado(so_transferencias), 10000)


if __name__ == "__main__":
    unittest.main()
