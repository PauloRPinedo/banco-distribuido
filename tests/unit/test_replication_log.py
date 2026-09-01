"""Log matching e regra de confirmacao (o nucleo da corretude do failover)."""

from __future__ import annotations

import pytest

from bank.domain.operations import LogEntry, Operation, OpType
from bank.replication.log import ReplicatedLog
from bank.storage.wal import WriteAheadLog


def novo_log(tmp_path, self_id: str = "A") -> ReplicatedLog:
    wal = WriteAheadLog(tmp_path / f"wal-{self_id}.jsonl", fsync_mode="off")
    return ReplicatedLog(wal, ["A", "B", "C"], self_id)


def operacao(n: int) -> Operation:
    return Operation(f"op{n}", OpType.DEPOSIT, account_id="alice", amount_cents=1)


def entrada(idx: int, epoch: int) -> LogEntry:
    return LogEntry(idx, epoch, operacao(idx))


class TestLogMatching:
    def test_prev_idx_divergente_e_rejeitado_com_dica_de_retrocesso(self, tmp_path):
        log = novo_log(tmp_path, "B")
        log.append_from_leader(0, [entrada(1, 1), entrada(2, 1)])
        assert log.matches(2, 1)
        assert not log.matches(2, 7), "epoch diferente no mesmo idx tem de falhar"
        assert not log.matches(9, 1), "indice que nao existe tem de falhar"

    def test_conflito_de_epoch_no_mesmo_idx_trunca_a_cauda(self, tmp_path):
        log = novo_log(tmp_path, "B")
        log.append_from_leader(0, [entrada(1, 1), entrada(2, 1), entrada(3, 1)])
        # Um novo primario reescreve a partir do idx 2 com o seu epoch.
        log.append_from_leader(1, [entrada(2, 4)])
        assert log.last_idx == 2
        assert log.wal.entry_at(2).epoch == 4
        assert log.wal.entry_at(3) is None, "a cauda divergente tinha de sumir"

    def test_entradas_repetidas_nao_duplicam_o_log(self, tmp_path):
        log = novo_log(tmp_path, "B")
        lote = [entrada(1, 1), entrada(2, 1)]
        log.append_from_leader(0, lote)
        log.append_from_leader(0, lote)  # reenvio do primario
        log.append_from_leader(0, lote)
        assert log.last_idx == 2

    def test_back_off_converge_ate_a_origem(self, tmp_path):
        log = novo_log(tmp_path, "A")
        for i in range(1, 6):
            log.append_local(operacao(i), epoch=1)
        log.reset_tracking()
        assert log.next_idx["B"] == 6
        log.back_off("B", hint_idx=2)
        prev_idx, _, entries = log.next_batch_for("B")
        assert prev_idx == 2 and [e.idx for e in entries] == [3, 4, 5]
        for _ in range(10):
            log.back_off("B", hint_idx=0)
        prev_idx, _, entries = log.next_batch_for("B")
        assert prev_idx == 0 and [e.idx for e in entries] == [1, 2, 3, 4, 5]


class TestAvancoDoCommit:
    def test_maioria_confirma_entrada_do_epoch_corrente(self, tmp_path):
        log = novo_log(tmp_path, "A")
        log.append_local(operacao(1), epoch=2)
        assert log.advance_commit(2) == 0, "sem ACK de replica nao ha maioria"
        log.record_match("B", 1)
        assert log.advance_commit(2) == 1, "A + B = 2 de 3 e maioria"

    def test_entrada_de_epoch_anterior_nao_e_confirmada_por_contagem(self, tmp_path):
        """Regra sutil do Raft: confirmar por contagem uma entrada herdada permite
        reverte-la depois. Ela so e confirmada por arraste, junto com o NOOP do
        epoch novo."""
        log = novo_log(tmp_path, "A")
        log.append_local(operacao(1), epoch=1)  # herdada do primario anterior
        log.append_local(operacao(2), epoch=1)
        log.record_match("B", 2)
        log.record_match("C", 2)
        assert log.advance_commit(current_epoch=2) == 0, (
            "entradas de epoch anterior nao podem ser confirmadas por contagem"
        )

        # O NOOP do epoch corrente arrasta as anteriores.
        log.append_local(operacao(3), epoch=2)
        log.record_match("B", 3)
        assert log.advance_commit(current_epoch=2) == 3

    def test_sem_maioria_o_commit_index_nao_avanca(self, tmp_path):
        log = novo_log(tmp_path, "A")
        for i in range(1, 4):
            log.append_local(operacao(i), epoch=1)
        assert log.advance_commit(1) == 0
        log.record_match("B", 3)
        assert log.advance_commit(1) == 3

    def test_commit_nunca_retrocede(self, tmp_path):
        log = novo_log(tmp_path, "B")
        log.append_from_leader(0, [entrada(1, 1), entrada(2, 1)])
        log.set_commit(2)
        assert log.set_commit(1) == 2, "um leader_commit menor nao pode desfazer"

    def test_set_commit_limitado_ao_que_existe_localmente(self, tmp_path):
        log = novo_log(tmp_path, "B")
        log.append_from_leader(0, [entrada(1, 1)])
        assert log.set_commit(99) == 1, "nao se confirma o que nao se tem"
