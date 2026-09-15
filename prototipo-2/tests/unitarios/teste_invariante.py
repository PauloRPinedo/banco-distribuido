"""A invariante do dinheiro (RNF-01) — o teste que não pode faltar.

Sortear milhares de operações, aplicá-las, e verificar que o dinheiro não foi
criado nem destruído. É a afirmação central do projeto inteiro; se este teste
falhar, nada do resto interessa.

A semente é fixa: por RNF-06, a mesma execução tem de se repetir igual.
"""

import random
import unittest

from banco.dominio.contas import Livro
from banco.dominio.erros import ErroDoBanco
from banco.dominio.operacoes import (CriarConta, Deposito, Saque, Transferencia,
                                     total_esperado)

SEMENTE = 42
CONTAS = [f"conta-{n:02d}" for n in range(20)]
SALDO_INICIAL = 100_000


def _livro_com_contas():
    livro = Livro()
    operacoes = []
    for indice, identificador in enumerate(CONTAS, 1):
        operacao = CriarConta(identificador, SALDO_INICIAL)
        operacao.aplicar(livro, indice, 0.0)
        operacoes.append(operacao)
    return livro, operacoes


def _sortear_e_aplicar(livro, operacoes, quantidade, sorteio, so_transferencias):
    """Aplica operações sorteadas, ignorando as que o banco recusa.

    Uma operação recusada é um resultado legítimo — saldo insuficiente acontece
    e tem de acontecer. O que se verifica é que uma recusa não deixa nada meio
    aplicado.
    """
    aplicadas = 0
    indice = len(operacoes)
    while aplicadas < quantidade:
        origem, destino = sorteio.sample(CONTAS, 2)
        valor = sorteio.randint(1, 5_000)
        if so_transferencias:
            operacao = Transferencia(origem, destino, valor)
        else:
            operacao = sorteio.choice([Transferencia(origem, destino, valor),
                                       Deposito(origem, valor),
                                       Saque(origem, valor)])
        indice += 1
        try:
            operacao.aplicar(livro, indice, 0.0)
        except ErroDoBanco:
            continue
        operacoes.append(operacao)
        aplicadas += 1
    return operacoes


class TesteInvarianteDoDinheiro(unittest.TestCase):

    def teste_3000_transferencias_nao_mudam_o_total(self):
        livro, operacoes = _livro_com_contas()
        total_antes = livro.total_centavos()

        _sortear_e_aplicar(livro, operacoes, 3000, random.Random(SEMENTE), True)

        self.assertEqual(livro.total_centavos(), total_antes)

    def teste_nenhum_saldo_fica_negativo(self):
        livro, operacoes = _livro_com_contas()

        _sortear_e_aplicar(livro, operacoes, 3000, random.Random(SEMENTE), False)

        for conta in livro.contas.values():
            with self.subTest(conta=conta.id):
                self.assertGreaterEqual(conta.saldo_centavos, 0)

    def teste_soma_dos_saldos_bate_com_o_total_esperado(self):
        # O lado esquerdo vem dos saldos, o direito vem do log. São dois
        # cálculos independentes; é a igualdade entre eles que audita (F-06).
        livro, operacoes = _livro_com_contas()

        _sortear_e_aplicar(livro, operacoes, 3000, random.Random(SEMENTE), False)

        self.assertEqual(livro.total_centavos(), total_esperado(operacoes))

    def teste_a_mesma_semente_produz_o_mesmo_resultado(self):
        # RNF-06. Sem isto, um teste que falha de vez em quando é impossível
        # de investigar.
        saldos = []
        for _ in range(2):
            livro, operacoes = _livro_com_contas()
            _sortear_e_aplicar(livro, operacoes, 500, random.Random(SEMENTE), False)
            saldos.append({c: v.saldo_centavos for c, v in livro.contas.items()})

        self.assertEqual(saldos[0], saldos[1])

    def teste_sementes_diferentes_produzem_resultados_diferentes(self):
        # Guarda contra o teste acima passar por o sorteio não estar a sortear.
        saldos = []
        for semente in (1, 2):
            livro, operacoes = _livro_com_contas()
            _sortear_e_aplicar(livro, operacoes, 500, random.Random(semente), False)
            saldos.append({c: v.saldo_centavos for c, v in livro.contas.items()})

        self.assertNotEqual(saldos[0], saldos[1])


if __name__ == "__main__":
    unittest.main()
