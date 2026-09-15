"""O que só o armazém em PostgreSQL pode fazer errado (subfase 1.4).

O contrato comum está em `tests/unitarios/teste_armazem.py` e corre também contra
esta implementação. Aqui ficam as garantias que só existem por haver uma base: a
recusa de duas instâncias na mesma base, a durabilidade declarada, e a
deduplicação garantida pelo índice único.

Saltam-se sozinhos sem `BANCO_BD_TESTE`, com o motivo escrito — o ROADMAP 3.5
proíbe testes pendentes sem explicação.
"""

import os
import unittest

from banco.dominio.erros import ArmazemIndisponivel
from banco.persistencia.entrada import EntradaDeLog

DSN_DE_TESTE = os.environ.get("BANCO_BD_TESTE")


def entrada(indice, op_id=None, epoch=1):
    return EntradaDeLog(indice=indice, epoch=epoch, op_id=op_id or f"op-{indice}",
                        tipo="deposito",
                        dados={"conta": "alice", "valor_centavos": 100},
                        instante=1756742400.0)


@unittest.skipUnless(DSN_DE_TESTE,
                     "sem BANCO_BD_TESTE: defina o DSN de um PostgreSQL de "
                     "testes, por exemplo "
                     "BANCO_BD_TESTE=postgresql:///banco_teste")
class BaseComPostgres(unittest.TestCase):

    def setUp(self):
        self.primeiro = self.abrir("A")
        self.primeiro.apagar_tudo()

    def abrir(self, no_id):
        from banco.persistencia.armazem_postgres import ArmazemPostgres
        armazem = ArmazemPostgres(DSN_DE_TESTE, no_id)
        self.addCleanup(armazem.fechar)
        return armazem


class TesteDonoDaBase(BaseComPostgres):

    def teste_outro_no_na_mesma_base_e_recusado(self):
        """Dois nós com o mesmo DSN partilhariam log em silêncio.

        Os índices chocavam, a correspondência de log falhava, e o sintoma
        pareceria um erro de eleição — procurar-se-ia no protocolo durante horas.
        """
        with self.assertRaises(ArmazemIndisponivel) as capturado:
            self.abrir("B")

        self.assertIn("cada nó precisa da sua própria base",
                      capturado.exception.mensagem)

    def teste_no_recusado_nao_estraga_a_base(self):
        """A recusa tem de ser inofensiva para quem é dono.

        Numa primeira versão a linha do intruso era inserida **antes** da
        verificação. Em autocommit já não havia transação para desfazer, a base
        ficava com dois donos, e a partir daí nem o nó legítimo a conseguia
        abrir: uma tentativa errada arruinava o nó certo.
        """
        with self.assertRaises(ArmazemIndisponivel):
            self.abrir("B")

        renascido = self.abrir("A")

        self.assertEqual(renascido.ler_estado().epoch, 1)

    def teste_o_mesmo_no_reabre_a_sua_base(self):
        self.primeiro.gravar_estado(5, "C")
        self.primeiro.fechar()

        renascido = self.abrir("A")

        self.assertEqual(renascido.ler_estado().epoch, 5)


class TesteDurabilidade(BaseComPostgres):

    def teste_a_base_confirma_que_faz_fsync(self):
        """Não se afirma a durabilidade: pergunta-se à base e mostra-se.

        É a resposta pronta a "como é que sabes que houve fsync?" na defesa.
        """
        descricao = self.primeiro.descrever_durabilidade()

        self.assertIn("fsync=on", descricao)
        self.assertIn("synchronous_commit=on", descricao)


class TesteDeduplicacaoPelaBase(BaseComPostgres):

    def teste_op_id_repetido_e_recusado_pela_base(self):
        """A rede de segurança que o ficheiro JSONL não tinha.

        A tabela de `op_id` em memória continua a ser o mecanismo normal. Isto
        cobre o intervalo que ela não cobre: o processo morrer entre o commit da
        entrada e o aplicar, e a repetição chegar a um nó que ainda não
        reconstruiu a tabela.
        """
        self.primeiro.acrescentar(entrada(1, op_id="repetido"))

        with self.assertRaises(ArmazemIndisponivel):
            self.primeiro.acrescentar(entrada(2, op_id="repetido"))

        self.assertEqual(self.primeiro.ultimo_indice(), 1)

    def teste_lote_com_op_id_repetido_nao_grava_metade(self):
        """Tudo ou nada: meio lote deixaria um buraco no log."""
        self.primeiro.acrescentar(entrada(1, op_id="repetido"))

        with self.assertRaises(ArmazemIndisponivel):
            self.primeiro.acrescentar_muitas(
                [entrada(2), entrada(3, op_id="repetido")])

        self.assertEqual(self.primeiro.ultimo_indice(), 1)


class TesteRestricoesDoEsquema(BaseComPostgres):

    def teste_tipo_desconhecido_e_recusado(self):
        """O esquema não deixa entrar uma operação que o domínio não conhece."""
        estranha = EntradaDeLog(indice=1, epoch=1, op_id="x", tipo="inventada",
                                dados={}, instante=0.0)

        with self.assertRaises(ArmazemIndisponivel):
            self.primeiro.acrescentar(estranha)


if __name__ == "__main__":
    unittest.main()
