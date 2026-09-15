"""Recuperação, deduplicação e auditoria do nó (subfase 1.4).

Corre sobre o armazém em memória: "reiniciar" é construir um `No` novo sobre o
mesmo armazém, que é o equivalente exato a matar o processo e voltar a subi-lo.
O mesmo corpo corre também sobre o armazém em ficheiro, com disco a sério — sem
isso, provava-se a recuperação contra um armazém que nunca perde nada, que é
justamente o caso fácil.
"""

import tempfile
import unittest
from pathlib import Path

from banco.cluster.no import No
from banco.dominio.erros import SaldoInsuficiente
from banco.dominio.operacoes import CriarConta, Deposito, Saque, Transferencia
from banco.persistencia.armazem_ficheiro import ArmazemEmFicheiro
from banco.persistencia.armazem_memoria import ArmazemEmMemoria


class ContratoDoNo:
    """O corpo comum. A subclasse só decide onde o log vive.

    `reabrir_armazem` existe porque reiniciar não é reutilizar o objeto: o
    armazém em ficheiro fecha o descritor e tem de ser aberto de novo sobre o
    mesmo diretório, tal como acontece quando o processo morre e volta. O de
    memória é a própria coisa guardada, e devolve-se a si mesmo.
    """

    def criar_armazem(self):
        raise NotImplementedError

    def reabrir_armazem(self, armazem):
        raise NotImplementedError

    def setUp(self):
        self.no = self.abrir(self.criar_armazem())

    def abrir(self, armazem):
        no = No("A", armazem)
        self.addCleanup(no.fechar)
        return no

    def reiniciar(self):
        armazem = self.no.armazem
        self.no.fechar()
        self.no = self.abrir(self.reabrir_armazem(armazem))
        return self.no

    # ----------------------------------------------------------- recuperação

    def teste_estado_sobrevive_a_reinicio(self):
        self.no.executar("op-1", CriarConta("alice", 10000))
        self.no.executar("op-2", CriarConta("bob", 0))
        self.no.executar("op-3", Transferencia("alice", "bob", 2500))
        antes = self.no.auditoria()

        renascido = self.reiniciar()

        self.assertEqual(renascido.saldo("alice")["saldo_centavos"], 7500)
        self.assertEqual(renascido.saldo("bob")["saldo_centavos"], 2500)
        self.assertEqual(renascido.auditoria()["total_centavos"],
                         antes["total_centavos"])

    def teste_extrato_sobrevive_a_reinicio(self):
        self.no.executar("op-1", CriarConta("alice", 10000))
        self.no.executar("op-2", Deposito("alice", 500))

        renascido = self.reiniciar()

        self.assertEqual(len(renascido.extrato("alice")["movimentos"]), 2)

    def teste_indice_continua_de_onde_ficou(self):
        self.no.executar("op-1", CriarConta("alice", 100))

        renascido = self.reiniciar()
        renascido.executar("op-2", Deposito("alice", 100))

        self.assertEqual(renascido.estado_do_no()["ultimo_indice"], 2)

    def teste_operacao_recusada_nao_fica_no_log(self):
        self.no.executar("op-1", CriarConta("alice", 100))

        with self.assertRaises(SaldoInsuficiente):
            self.no.executar("op-2", Saque("alice", 999999))

        self.assertEqual(self.no.estado_do_no()["ultimo_indice"], 1)

    # --------------------------------------------------------- deduplicação

    def teste_op_id_repetido_nao_move_o_dinheiro_duas_vezes(self):
        self.no.executar("criar-1", CriarConta("alice", 10000))
        self.no.executar("criar-2", CriarConta("bob", 0))

        self.no.executar("transf-1", Transferencia("alice", "bob", 2500))
        self.no.executar("transf-1", Transferencia("alice", "bob", 2500))

        self.assertEqual(self.no.saldo("alice")["saldo_centavos"], 7500)

    def teste_repeticao_devolve_a_mesma_resposta(self):
        self.no.executar("criar-1", CriarConta("alice", 10000))
        self.no.executar("criar-2", CriarConta("bob", 0))

        primeira = self.no.executar("t-1", Transferencia("alice", "bob", 2500))
        segunda = self.no.executar("t-1", Transferencia("alice", "bob", 2500))

        self.assertEqual(primeira, segunda)

    def teste_repeticao_nao_acrescenta_entrada_ao_log(self):
        self.no.executar("criar-1", CriarConta("alice", 10000))
        self.no.executar("criar-2", CriarConta("bob", 0))
        self.no.executar("t-1", Transferencia("alice", "bob", 2500))
        indice = self.no.estado_do_no()["ultimo_indice"]

        self.no.executar("t-1", Transferencia("alice", "bob", 2500))

        self.assertEqual(self.no.estado_do_no()["ultimo_indice"], indice)

    def teste_deduplicacao_sobrevive_a_reinicio(self):
        self.no.executar("criar-1", CriarConta("alice", 10000))
        self.no.executar("criar-2", CriarConta("bob", 0))
        self.no.executar("t-1", Transferencia("alice", "bob", 2500))

        renascido = self.reiniciar()
        renascido.executar("t-1", Transferencia("alice", "bob", 2500))

        self.assertEqual(renascido.saldo("alice")["saldo_centavos"], 7500)

    # ------------------------------------------------------------- auditoria

    def teste_os_dois_calculos_batem(self):
        self.no.executar("op-1", CriarConta("alice", 10000))
        self.no.executar("op-2", CriarConta("bob", 500))
        self.no.executar("op-3", Deposito("bob", 250))
        self.no.executar("op-4", Saque("alice", 100))
        self.no.executar("op-5", Transferencia("alice", "bob", 1000))

        resultado = self.no.auditoria()

        self.assertEqual(resultado["total_centavos"], 10650)
        self.assertEqual(resultado["total_esperado_centavos"], 10650)
        self.assertFalse(resultado["divergente"])


class TesteNoEmMemoria(ContratoDoNo, unittest.TestCase):

    def criar_armazem(self):
        return ArmazemEmMemoria()

    def reabrir_armazem(self, armazem):
        return armazem


class TesteNoEmFicheiro(ContratoDoNo, unittest.TestCase):

    def criar_armazem(self):
        temporario = tempfile.TemporaryDirectory()
        self.addCleanup(temporario.cleanup)
        self.diretorio = Path(temporario.name)
        return ArmazemEmFicheiro(self.diretorio)

    def reabrir_armazem(self, armazem):
        return ArmazemEmFicheiro(self.diretorio)


if __name__ == "__main__":
    unittest.main()
