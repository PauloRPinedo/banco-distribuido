"""O desafio central do projeto: derrubar o primario sem perder dinheiro.

Estes sao os testes que a proposta descreve como validacao pratica
(RF-09, RF-10, RF-11, RF-12, RNF-01, RNF-02, RNF-03).
"""

from __future__ import annotations

import pytest


class TestTrocaAutomatica:
    def test_novo_primario_assume_em_poucos_segundos(self, live_cluster):
        """RNF-03. Mede o tempo entre o SIGKILL e o primeiro no que se declara
        primario com epoch maior."""
        pytest.skip("fase 4")

    def test_cluster_segue_aceitando_escritas_apos_a_queda(self, live_cluster):
        """RF-11: 1 de 3 caido, escritas continuam normalmente."""
        pytest.skip("fase 4")

    def test_dois_nos_caidos_deixam_o_cluster_somente_leitura(self, live_cluster):
        """Desvio documentado da proposta: sem maioria, o no recusa escrita em vez
        de aceitar uma que nunca sera confirmada. Leitura e auditoria seguem."""
        pytest.skip("fase 4")


class TestDinheiroPreservado:
    def test_soma_total_inalterada_apos_queda_no_meio_de_transferencias(self, live_cluster):
        """RNF-01, o teste mais importante da entrega: carga de transferencias
        concorrentes, SIGKILL no primario no meio, e ao final a soma dos saldos
        tem de ser exatamente a inicial -- nem um centavo a mais ou a menos."""
        pytest.skip("fase 4")

    def test_operacao_confirmada_sobrevive_a_queda_imediata(self, live_cluster):
        """RNF-02: matar o primario logo apos ele responder 200; a operacao tem de
        aparecer no novo primario."""
        pytest.skip("fase 4")

    def test_retentativa_do_cliente_apos_failover_nao_duplica(self, live_cluster):
        """Historia de usuario 4. O cliente repete com o mesmo op_id; o dinheiro
        so pode se mover uma vez."""
        pytest.skip("fase 4")

    def test_operacao_sem_quorum_nao_aparece_como_confirmada(self, live_cluster):
        """503 tem de significar 503: a operacao nao pode reaparecer aplicada
        depois, nem sumir se chegou a ser confirmada."""
        pytest.skip("fase 4")


class TestSemSplitBrain:
    def test_primario_congelado_nao_confirma_apos_perder_o_mandato(self, live_cluster):
        """Congela o primario (``freeze``), deixa o cluster eleger outro, descongela.
        O antigo tem de ser rejeitado por epoch e se rebaixar, sem confirmar nada."""
        pytest.skip("fase 5")


class TestReintegracao:
    def test_no_reiniciado_volta_como_replica_e_alcanca_o_log(self, live_cluster):
        """RF-12, sem intervencao manual."""
        pytest.skip("fase 4")

    def test_entradas_nao_confirmadas_do_no_antigo_sao_truncadas(self, live_cluster):
        pytest.skip("fase 4")
