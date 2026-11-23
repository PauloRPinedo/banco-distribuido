"""Testes de banco/autenticacao/chaves.py e das dependências que as usam."""

import os
import unittest
from unittest import mock

from tests.ajudas import PILHA_INSTALADA, exige_pilha

from banco.autenticacao.chaves import (chave_do_cluster, e_chave_de_admin,
                                       e_chave_do_cluster, falhas_ativas)

if PILHA_INSTALADA:
    from banco.api.seguranca import injecao_de_falhas_ativa, operador, par_do_cluster
    from banco.servico.erros import FalhasDesativadas, NaoEParDoCluster, SemChaveDeAdmin


class TesteChaveDoCluster(unittest.TestCase):

    def teste_a_chave_certa_vale(self):
        self.assertTrue(e_chave_do_cluster(chave_do_cluster()))

    def teste_sem_chave_ou_chave_errada_nao_vale(self):
        for recebida in (None, "", "abc", chave_do_cluster()[:-1], "ção"):
            with self.subTest(recebida=recebida):
                self.assertFalse(e_chave_do_cluster(recebida))

    def teste_deriva_da_secret_key(self):
        antes = chave_do_cluster()
        with mock.patch.dict(os.environ, {"SECRET_KEY": "outra-chave"}):
            self.assertNotEqual(chave_do_cluster(), antes)

    def teste_nao_e_a_propria_secret_key(self):
        self.assertNotEqual(chave_do_cluster(), os.environ["SECRET_KEY"])


class TesteChaveDeAdmin(unittest.TestCase):

    def teste_sem_chave_admin_definida_recusa_sempre(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CHAVE_ADMIN", None)
            self.assertFalse(e_chave_de_admin(""))
            self.assertFalse(e_chave_de_admin(None))

    def teste_com_chave_admin_so_a_certa_vale(self):
        with mock.patch.dict(os.environ, {"CHAVE_ADMIN": "segredo"}):
            self.assertTrue(e_chave_de_admin("segredo"))
            self.assertFalse(e_chave_de_admin("segred0"))


class TesteFalhasAtivas(unittest.TestCase):

    def teste_so_com_1(self):
        for valor, esperado in (("1", True), ("0", False), ("true", False), ("", False)):
            with self.subTest(valor=valor), mock.patch.dict(os.environ, {"FALHAS_ATIVAS": valor}):
                self.assertEqual(falhas_ativas(), esperado)


@exige_pilha
class TesteDependencias(unittest.TestCase):

    def teste_par_do_cluster(self):
        par_do_cluster(x_chave_cluster=chave_do_cluster())  # não levanta
        with self.assertRaises(NaoEParDoCluster):
            par_do_cluster(x_chave_cluster=None)

    def teste_operador(self):
        with mock.patch.dict(os.environ, {"CHAVE_ADMIN": "segredo"}):
            operador(x_chave_admin="segredo")
            with self.assertRaises(SemChaveDeAdmin):
                operador(x_chave_admin=None)

    def teste_injecao_de_falhas(self):
        with mock.patch.dict(os.environ, {"FALHAS_ATIVAS": "0"}):
            with self.assertRaises(FalhasDesativadas):
                injecao_de_falhas_ativa()
        with mock.patch.dict(os.environ, {"FALHAS_ATIVAS": "1"}):
            injecao_de_falhas_ativa()


if __name__ == "__main__":
    unittest.main()
