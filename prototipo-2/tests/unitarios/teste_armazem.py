"""O contrato que qualquer armazém tem de cumprir (subfase 1.4).

O mesmo corpo de testes corre contra as três implementações. É isto que dá
sentido a poder trocar de armazém: se o de memória e o de PostgreSQL não se
comportarem igual, os testes que correm em memória não dizem nada sobre o que
acontece na demonstração.

Os testes contra o PostgreSQL saltam-se sozinhos quando não há base, com o
motivo escrito: um teste pendente sem explicação não diz nada a quem o lê.
"""

import os
import tempfile
import unittest
from pathlib import Path

from banco.persistencia.armazem_ficheiro import ArmazemEmFicheiro
from banco.persistencia.armazem_memoria import ArmazemEmMemoria
from banco.persistencia.entrada import EntradaDeLog

DSN_DE_TESTE = os.environ.get("BANCO_BD_TESTE")


def entrada(indice, op_id=None, epoch=1, centavos=100):
    return EntradaDeLog(indice=indice, epoch=epoch, op_id=op_id or f"op-{indice}",
                        tipo="deposito",
                        dados={"conta": "alice", "valor_centavos": centavos},
                        instante=1756742400.0 + indice)


class ContratoDoArmazem:
    """O corpo comum. Cada subclasse só tem de saber criar o seu armazém."""

    def criar_armazem(self):
        raise NotImplementedError

    def setUp(self):
        self.armazem = self.criar_armazem()
        self.addCleanup(self.armazem.fechar)

    # ------------------------------------------------------------------- log

    def teste_armazem_vazio_nao_tem_entradas(self):
        self.assertEqual(self.armazem.ler_desde(0), [])
        self.assertEqual(self.armazem.ultimo_indice(), 0)
        self.assertEqual(self.armazem.ultimo_epoch(), 0)

    def teste_entrada_gravada_e_relida_igual(self):
        original = entrada(1)

        self.armazem.acrescentar(original)

        self.assertEqual(self.armazem.ler_desde(0), [original])

    def teste_ordem_das_entradas_e_preservada(self):
        for indice in range(1, 6):
            self.armazem.acrescentar(entrada(indice))

        lidas = [e.indice for e in self.armazem.ler_desde(0)]

        self.assertEqual(lidas, [1, 2, 3, 4, 5])

    def teste_ler_desde_salta_o_que_ja_se_tem(self):
        for indice in range(1, 6):
            self.armazem.acrescentar(entrada(indice))

        lidas = [e.indice for e in self.armazem.ler_desde(3)]

        self.assertEqual(lidas, [4, 5])

    def teste_acrescentar_muitas_grava_o_lote_todo(self):
        self.armazem.acrescentar_muitas([entrada(1), entrada(2), entrada(3)])

        self.assertEqual(self.armazem.ultimo_indice(), 3)

    def teste_acrescentar_muitas_com_lista_vazia_nao_mexe(self):
        self.armazem.acrescentar(entrada(1))

        self.armazem.acrescentar_muitas([])

        self.assertEqual(self.armazem.ultimo_indice(), 1)

    def teste_ultimo_epoch_e_o_da_ultima_entrada(self):
        self.armazem.acrescentar(entrada(1, epoch=1))
        self.armazem.acrescentar(entrada(2, epoch=4))

        self.assertEqual(self.armazem.ultimo_epoch(), 4)

    def teste_epoch_em_indice_conhecido(self):
        self.armazem.acrescentar(entrada(1, epoch=2))

        self.assertEqual(self.armazem.epoch_em(1), 2)

    def teste_epoch_em_indice_que_nao_existe_e_nulo(self):
        self.assertIsNone(self.armazem.epoch_em(7))

    def teste_indice_de_op_id_conhecido(self):
        self.armazem.acrescentar(entrada(1, op_id="abc"))

        self.assertEqual(self.armazem.indice_de("abc"), 1)

    def teste_indice_de_op_id_desconhecido_e_nulo(self):
        self.assertIsNone(self.armazem.indice_de("nunca-visto"))

    def teste_truncar_apaga_do_indice_para_a_frente(self):
        for indice in range(1, 6):
            self.armazem.acrescentar(entrada(indice))

        self.armazem.truncar_a_partir_de(3)

        self.assertEqual([e.indice for e in self.armazem.ler_desde(0)], [1, 2])
        self.assertEqual(self.armazem.ultimo_indice(), 2)

    def teste_truncar_acima_do_fim_nao_faz_nada(self):
        self.armazem.acrescentar(entrada(1))

        self.armazem.truncar_a_partir_de(9)

        self.assertEqual(self.armazem.ultimo_indice(), 1)

    # ---------------------------------------------------------------- estado

    def teste_estado_inicial(self):
        estado = self.armazem.ler_estado()

        self.assertEqual(estado.epoch, 1)
        self.assertIsNone(estado.votou_em)
        self.assertEqual(estado.indice_commit, 0)

    def teste_estado_gravado_e_relido(self):
        self.armazem.gravar_estado(7, "B")

        estado = self.armazem.ler_estado()

        self.assertEqual(estado.epoch, 7)
        self.assertEqual(estado.votou_em, "B")

    def teste_voto_pode_ser_limpo(self):
        self.armazem.gravar_estado(7, "B")

        self.armazem.gravar_estado(8, None)

        self.assertIsNone(self.armazem.ler_estado().votou_em)

    def teste_commit_gravado_e_relido(self):
        self.armazem.gravar_commit(42)

        self.assertEqual(self.armazem.ler_estado().indice_commit, 42)

    def teste_commit_e_estado_nao_se_pisam(self):
        self.armazem.gravar_estado(3, "C")

        self.armazem.gravar_commit(9)

        estado = self.armazem.ler_estado()
        self.assertEqual((estado.epoch, estado.votou_em, estado.indice_commit),
                         (3, "C", 9))

    def teste_o_estado_lido_e_uma_copia(self):
        """Mexer no que se leu não pode mexer no armazém.

        Sem isto, um `estado.epoch = 9` no meio do código de eleição mudaria o
        armazém sem passar por `gravar_estado` — e sem passar pelo disco.
        """
        lido = self.armazem.ler_estado()

        lido.epoch = 99

        self.assertEqual(self.armazem.ler_estado().epoch, 1)

    # -------------------------------------------------------------- dinheiro

    def teste_centavos_acima_de_2_53_sobrevivem_intactos(self):
        """O guarda contra um `float` a entrar pela porta das traseiras.

        2^53 + 1 é o primeiro inteiro que um `float` de dupla precisão não
        consegue representar: se alguém, em qualquer camada, converter este
        número para vírgula flutuante, ele volta diferente. É a forma mais barata
        de provar que RNF-01 não depende de boa vontade.
        """
        enorme = 9007199254740993
        self.armazem.acrescentar(entrada(1, centavos=enorme))

        lido = self.armazem.ler_desde(0)[0].dados["valor_centavos"]

        self.assertIsInstance(lido, int)
        self.assertEqual(lido, enorme)


class TesteArmazemEmMemoria(ContratoDoArmazem, unittest.TestCase):

    def criar_armazem(self):
        return ArmazemEmMemoria()


class TesteArmazemEmFicheiro(ContratoDoArmazem, unittest.TestCase):

    def criar_armazem(self):
        temporario = tempfile.TemporaryDirectory()
        self.addCleanup(temporario.cleanup)
        return ArmazemEmFicheiro(Path(temporario.name))


@unittest.skipUnless(DSN_DE_TESTE,
                     "sem BANCO_BD_TESTE: defina o DSN de um PostgreSQL de "
                     "testes para correr o contrato contra a base real, por "
                     "exemplo BANCO_BD_TESTE=postgresql://banco@localhost/banco_teste")
class TesteArmazemPostgres(ContratoDoArmazem, unittest.TestCase):

    def criar_armazem(self):
        from banco.persistencia.armazem_postgres import ArmazemPostgres
        armazem = ArmazemPostgres(DSN_DE_TESTE, "A")
        armazem.apagar_tudo()
        return armazem


if __name__ == "__main__":
    unittest.main()
