"""Maquina de estados das contas: invariantes de dinheiro (RNF-01, RF-06, RF-08)."""

from __future__ import annotations

import pytest


class TestSaldoNuncaNegativo:
    """RF-06: nenhuma operacao pode deixar um saldo negativo."""

    def test_saque_acima_do_saldo_e_rejeitado(self):
        pytest.skip("fase 2")

    def test_transferencia_acima_do_saldo_nao_move_nada(self):
        """Nem debita a origem nem credita o destino -- rejeicao e tudo ou nada."""
        pytest.skip("fase 2")


class TestInvarianteDaSoma:
    """RNF-01: a soma de todos os saldos nunca muda com transferencias."""

    def test_transferencia_preserva_o_total(self):
        pytest.skip("fase 2")

    def test_sequencia_aleatoria_preserva_o_total(self):
        """Milhares de operacoes sorteadas com semente fixa; o total tem de bater."""
        pytest.skip("fase 2")


class TestAplicacaoDeEntradas:
    def test_reaplicar_o_mesmo_op_id_nao_move_dinheiro_duas_vezes(self):
        """Idempotencia: e o que torna seguro o cliente repetir apos um failover."""
        pytest.skip("fase 2")

    def test_entrada_fora_de_ordem_e_recusada(self):
        """Aplicar salteado corromperia o estado em silencio."""
        pytest.skip("fase 2")
