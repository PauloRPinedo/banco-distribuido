"""O desafio central do projeto: derrubar o primario sem perder dinheiro.

Estes sao os testes que a proposta descreve como validacao pratica
(RF-09, RF-10, RF-11, RF-12, RNF-01, RNF-02, RNF-03).
"""

from __future__ import annotations

import threading
import time
import uuid

import httpx
import pytest


class TestTrocaAutomatica:
    def test_novo_primario_assume_em_poucos_segundos(self, live_cluster):
        """RNF-03. Mede o tempo entre o SIGKILL e o primeiro no que se declara
        primario com epoch maior."""
        antigo = live_cluster.esperar_primario()
        epoch_antigo = antigo.status()["epoch"]

        inicio = time.monotonic()
        antigo.matar()
        novo = live_cluster.esperar_primario(timeout=20.0)
        decorrido = time.monotonic() - inicio

        assert novo.id != antigo.id
        assert novo.status()["epoch"] > epoch_antigo, "o epoch tem de avancar na troca"
        assert decorrido < 15.0, f"failover levou {decorrido:.1f}s"

    def test_cluster_segue_aceitando_escritas_apos_a_queda(self, banco, live_cluster):
        """RF-11: 1 de 3 caido, escritas continuam normalmente."""
        banco.create_account("alice", 10000)
        banco.create_account("bob", 0)

        live_cluster.esperar_primario().matar()
        live_cluster.esperar_primario(timeout=20.0)

        banco.transfer("alice", "bob", 1000)
        assert banco.get_balance("bob")["balance_cents"] == 1000

    def test_dois_nos_caidos_deixam_o_cluster_somente_leitura(self, banco, live_cluster):
        """Desvio documentado da proposta: sem maioria, o no recusa escrita em vez
        de aceitar uma que nunca sera confirmada. Leitura e auditoria seguem."""
        from banco_cli import BankError

        banco.create_account("alice", 5000)
        live_cluster.esperar_convergencia()

        primario = live_cluster.esperar_primario()
        sobrevivente = [n for n in live_cluster.vivos() if n.id != primario.id][0]
        for no in list(live_cluster.vivos()):
            if no.id != sobrevivente.id:
                no.matar()

        # Leitura continua respondendo (RNF-11).
        prazo = time.monotonic() + 10
        while time.monotonic() < prazo:
            resposta = httpx.get(f"{sobrevivente.url}/audit", timeout=2.0)
            if resposta.status_code == 200:
                assert resposta.json()["total_cents"] == 5000
                break
            time.sleep(0.3)
        else:
            pytest.fail("o no sobrevivente parou de responder leituras")

        # Escrita e recusada, nunca aceita sem quorum.
        cliente_local = type(banco)([sobrevivente.url], timeout_s=2.0, max_retries=2)
        try:
            with pytest.raises(BankError):
                cliente_local.deposit("alice", 100)
        finally:
            cliente_local.close()
        assert httpx.get(f"{sobrevivente.url}/audit", timeout=2.0).json()["total_cents"] == 5000


class TestDinheiroPreservado:
    def test_soma_total_inalterada_apos_queda_no_meio_de_transferencias(
        self, banco, live_cluster
    ):
        """RNF-01, o teste mais importante da entrega: carga de transferencias
        concorrentes, SIGKILL no primario no meio, e ao final a soma dos saldos
        tem de ser exatamente a inicial -- nem um centavo a mais ou a menos."""
        contas = [f"c{i}" for i in range(6)]
        for nome in contas:
            banco.create_account(nome, 10000)
        total_inicial = 10000 * len(contas)
        assert banco.audit()["total_cents"] == total_inicial

        parar = threading.Event()
        confirmadas = []
        falhas = []

        def carga(semente: int) -> None:
            import random

            rng = random.Random(semente)
            cliente = type(banco)(live_cluster.urls, timeout_s=5.0, max_retries=10)
            try:
                while not parar.is_set():
                    origem, destino = rng.sample(contas, 2)
                    try:
                        cliente.transfer(origem, destino, rng.randint(1, 100))
                        confirmadas.append(1)
                    except Exception as exc:  # noqa: BLE001
                        falhas.append(repr(exc))
                    time.sleep(0.01)
            finally:
                cliente.close()

        threads = [threading.Thread(target=carga, args=(i,)) for i in range(4)]
        for thread in threads:
            thread.start()
        try:
            time.sleep(2.0)
            live_cluster.esperar_primario().matar()  # queda no meio da carga
            live_cluster.esperar_primario(timeout=20.0)
            time.sleep(2.0)
        finally:
            parar.set()
            for thread in threads:
                thread.join(timeout=20)

        assert confirmadas, f"nenhuma transferencia passou; falhas: {falhas[:3]}"
        totais = live_cluster.esperar_convergencia()
        assert set(totais.values()) == {total_inicial}, (
            f"o dinheiro mudou durante o failover: {totais} != {total_inicial}"
        )

    def test_operacao_confirmada_sobrevive_a_queda_imediata(self, banco, live_cluster):
        """RNF-02: matar o primario logo apos ele responder 200; a operacao tem de
        aparecer no novo primario."""
        banco.create_account("alice", 10000)
        banco.create_account("bob", 0)
        banco.transfer("alice", "bob", 4200)  # respondeu 200 => esta na maioria

        live_cluster.esperar_primario().matar()
        live_cluster.esperar_primario(timeout=20.0)

        assert banco.get_balance("bob")["balance_cents"] == 4200
        assert set(live_cluster.esperar_convergencia().values()) == {10000}

    def test_retentativa_do_cliente_apos_failover_nao_duplica(self, banco, live_cluster):
        """Historia de usuario 4. O cliente repete com o mesmo op_id; o dinheiro
        so pode se mover uma vez."""
        banco.create_account("alice", 10000)
        banco.create_account("bob", 0)
        live_cluster.esperar_convergencia()

        op_id = str(uuid.uuid4())
        corpo = {
            "op_id": op_id,
            "from_account": "alice",
            "to_account": "bob",
            "amount_cents": 700,
        }
        primario = live_cluster.esperar_primario()
        assert httpx.post(f"{primario.url}/transfers", json=corpo, timeout=5.0).status_code == 200

        primario.matar()
        novo = live_cluster.esperar_primario(timeout=20.0)

        # Mesma operacao logica, reenviada ao novo primario apos o failover.
        for _ in range(3):
            resposta = httpx.post(f"{novo.url}/transfers", json=corpo, timeout=5.0)
            assert resposta.status_code == 200

        assert banco.get_balance("bob")["balance_cents"] == 700, "a retentativa duplicou o dinheiro"
        assert set(live_cluster.esperar_convergencia().values()) == {10000}


class TestReintegracao:
    def test_no_reiniciado_volta_como_replica_e_alcanca_o_log(self, banco, live_cluster):
        """RF-12, sem intervencao manual."""
        banco.create_account("alice", 10000)
        banco.create_account("bob", 0)

        caido = live_cluster.esperar_primario()
        caido.matar()
        live_cluster.esperar_primario(timeout=20.0)

        for _ in range(5):
            banco.transfer("alice", "bob", 200)

        # Reinicia o no com o mesmo data-dir: tem de recuperar pelo disco.
        live_cluster.iniciar(caido.id)
        totais = live_cluster.esperar_convergencia(timeout=25.0)

        assert len(totais) == 3, f"o no reiniciado nao voltou: {totais}"
        assert set(totais.values()) == {10000}
        estado = live_cluster.nodes[caido.id].status()
        assert estado["role"] == "replica", "quem volta sobe como replica, nunca como primario"
        assert estado["applied_idx"] > 0
