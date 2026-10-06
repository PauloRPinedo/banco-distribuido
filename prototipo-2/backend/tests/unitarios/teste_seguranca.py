"""Testes de banco/api/seguranca.py — sem BD, sem rede.

Precisam do fastapi, porque `usuario_autenticado` é uma dependência dele;
saltam-se com o motivo escrito numa máquina sem a pilha.
"""

import unittest

from tests.ajudas import PILHA_INSTALADA, exige_pilha

if PILHA_INSTALADA:
    from banco.api.seguranca import exigir_dono, usuario_autenticado
    from banco.autenticacao import emitir_token
    from banco.servico.erros import SemPermissao, SemSessao


@exige_pilha
class TesteUsuarioAutenticado(unittest.TestCase):

    def teste_sem_cabecalho_e_sem_sessao(self):
        with self.assertRaises(SemSessao):
            usuario_autenticado(authorization=None)

    def teste_cabecalho_sem_bearer_e_sem_sessao(self):
        with self.assertRaises(SemSessao):
            usuario_autenticado(authorization="Token abc123")

    def teste_token_valido_devolve_o_usuario_id(self):
        token = emitir_token("usuario-1")
        self.assertEqual(usuario_autenticado(authorization=f"Bearer {token}"),
                         "usuario-1")

    def teste_token_invalido_e_sem_sessao(self):
        with self.assertRaises(SemSessao):
            usuario_autenticado(authorization="Bearer token-falso")

    def teste_sem_sessao_sai_como_401(self):
        self.assertEqual(SemSessao("x").estado_http, 401)


@exige_pilha
class TesteExigirDono(unittest.TestCase):

    def teste_dono_certo_nao_lanca_nada(self):
        exigir_dono("usuario-1", "usuario-1", "alice")

    def teste_dono_errado_e_proibido(self):
        with self.assertRaises(SemPermissao):
            exigir_dono("usuario-1", "usuario-2", "alice")


if __name__ == "__main__":
    unittest.main()
