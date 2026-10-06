"""Testes de banco/autenticacao — sem BD, sem rede (RN-15, RN-16)."""

import unittest

import tests.ajudas  # noqa: F401 — define a SECRET_KEY dos testes
from banco.autenticacao import calcular_hash, emitir_token, validar_token, verificar_senha


class TesteHashDaSenha(unittest.TestCase):

    def teste_senha_correta_verifica(self):
        hash_guardado = calcular_hash("cavalo-correto-bateria-agrafo")
        self.assertTrue(verificar_senha("cavalo-correto-bateria-agrafo", hash_guardado))

    def teste_senha_incorreta_nao_verifica(self):
        hash_guardado = calcular_hash("cavalo-correto-bateria-agrafo")
        self.assertFalse(verificar_senha("outra-coisa", hash_guardado))

    def teste_hash_nunca_e_a_senha_em_claro(self):
        hash_guardado = calcular_hash("ola-mundo")
        self.assertNotIn("ola-mundo", hash_guardado)

    def teste_mesma_senha_da_hashes_diferentes(self):
        # o sal é aleatório em cada chamada — evita que dois utilizadores com
        # a mesma senha tenham o mesmo hash guardado
        self.assertNotEqual(calcular_hash("igual"), calcular_hash("igual"))


class TesteTokenDeSessao(unittest.TestCase):

    def teste_token_valido_devolve_o_usuario(self):
        token = emitir_token("usuario-123")
        self.assertEqual(validar_token(token), "usuario-123")

    def teste_token_alterado_e_rejeitado(self):
        token = emitir_token("usuario-123")
        alterado = token[:-1] + ("0" if token[-1] != "0" else "1")
        self.assertIsNone(validar_token(alterado))

    def teste_token_valida_sem_chamar_quem_o_emitiu(self):
        # simula "outro nó": a mesma SECRET_KEY, nenhuma chamada de rede — a
        # própria chamada a validar_token já o demonstra (RN-16)
        token = emitir_token("usuario-456")
        self.assertEqual(validar_token(token), "usuario-456")


if __name__ == "__main__":
    unittest.main()
