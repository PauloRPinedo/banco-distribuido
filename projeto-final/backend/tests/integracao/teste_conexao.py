"""O pool de ligações (`banco/repositorio/conexao.py`).

Fechar uma ligação devolve-a ao pool. O que importa provar é que ela volta
limpa: o que ficou por confirmar desfaz-se, e o próximo a usá-la não herda
nem a transação nem o modo de quem a usou antes.
"""

import os
import unittest

from tests.ajudas import BASE_DE_TESTE, exige_base, exige_pilha, preparar_base


@exige_pilha
@exige_base
class TesteDoPool(unittest.TestCase):

    def setUp(self) -> None:
        preparar_base()
        anterior = os.environ.get("BANCO_BD")
        os.environ["BANCO_BD"] = BASE_DE_TESTE
        self.addCleanup(lambda: os.environ.__setitem__("BANCO_BD", anterior)
                        if anterior is not None else os.environ.pop("BANCO_BD", None))

    def obter(self):
        from banco.repositorio import obter_conexao
        return obter_conexao()

    def teste_fechar_reaproveita_a_mesma_ligacao(self):
        primeira = self.obter()
        primeira.close()

        segunda = self.obter()
        self.addCleanup(segunda.close)

        self.assertIs(segunda, primeira)
        self.assertFalse(segunda.closed)

    def teste_o_que_ficou_por_confirmar_desfaz_se(self):
        import psycopg2.extensions

        conexao = self.obter()
        with conexao.cursor() as cursor:
            cursor.execute("INSERT INTO usuario (id, nome, email, hash_senha, criado_em) "
                           "VALUES (gen_random_uuid(), 'Pool', 'pool@exemplo.pt', 'x', 0)")
        conexao.close()   # sem commit

        outra = self.obter()
        self.addCleanup(outra.close)
        self.assertEqual(outra.info.transaction_status,
                         psycopg2.extensions.TRANSACTION_STATUS_IDLE)
        self.assertFalse(outra.autocommit)
        with outra.cursor() as cursor:
            cursor.execute("SELECT count(*) AS n FROM usuario WHERE email = 'pool@exemplo.pt'")
            self.assertEqual(cursor.fetchone()["n"], 0)

    def teste_quem_ligou_o_autocommit_nao_o_passa_ao_seguinte(self):
        conexao = self.obter()
        conexao.autocommit = True
        conexao.close()

        outra = self.obter()
        self.addCleanup(outra.close)
        self.assertFalse(outra.autocommit)


if __name__ == "__main__":
    unittest.main()
