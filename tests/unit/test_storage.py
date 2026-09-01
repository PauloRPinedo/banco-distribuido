"""WAL, snapshot e recuperacao (RF-12, RNF-02)."""

from __future__ import annotations

import pytest

from bank.domain.operations import LogEntry, Operation, OpType
from bank.replication.log import ReplicatedLog
from bank.storage import snapshot as snapshot_module
from bank.storage.recovery import recover
from bank.storage.wal import WriteAheadLog


def entrada(idx: int, epoch: int = 1, op_id: str | None = None) -> LogEntry:
    return LogEntry(
        idx,
        epoch,
        Operation(op_id or f"op{idx}", OpType.DEPOSIT, account_id="alice", amount_cents=100),
    )


class TestWal:
    def test_append_e_releitura_preservam_a_ordem(self, tmp_path):
        wal = WriteAheadLog(tmp_path / "wal.jsonl", fsync_mode="always")
        for i in range(1, 6):
            wal.append(entrada(i))
        assert wal.last_idx == 5 and wal.last_epoch == 1
        assert [e.idx for e in wal.read_from(3)] == [3, 4, 5]
        wal.close()
        assert [e.idx for e in WriteAheadLog(tmp_path / "wal.jsonl").iter_all()] == [1, 2, 3, 4, 5]

    def test_idx_nao_contiguo_e_recusado(self, tmp_path):
        wal = WriteAheadLog(tmp_path / "wal.jsonl", fsync_mode="off")
        wal.append(entrada(1))
        with pytest.raises(ValueError, match="contiguo"):
            wal.append(entrada(7))

    def test_linha_final_truncada_e_descartada_na_leitura(self, tmp_path):
        """Uma queda no meio de um append deixa meia linha; ela nao pode virar
        uma entrada valida nem impedir o servidor de subir."""
        caminho = tmp_path / "wal.jsonl"
        wal = WriteAheadLog(caminho, fsync_mode="always")
        for i in range(1, 4):
            wal.append(entrada(i))
        wal.close()
        with open(caminho, "a", encoding="utf-8") as handle:
            handle.write('{"idx":4,"epoch":1,"op_i')  # queda no meio da gravacao

        recuperado = WriteAheadLog(caminho)
        assert recuperado.last_idx == 3
        recuperado.append(entrada(4))  # e o log volta a crescer normalmente
        assert recuperado.last_idx == 4

    def test_durabilidade_em_duas_fases(self, tmp_path):
        """append_buffered + wait_durable tem de produzir o mesmo resultado que append."""
        caminho = tmp_path / "wal.jsonl"
        wal = WriteAheadLog(caminho, fsync_mode="always")
        alvo = wal.append_buffered([entrada(1), entrada(2)])
        wal.wait_durable(alvo)
        wal.close()
        assert WriteAheadLog(caminho).last_idx == 2

    def test_truncate_from_remove_apenas_do_indice_em_diante(self, tmp_path):
        wal = WriteAheadLog(tmp_path / "wal.jsonl", fsync_mode="off")
        for i in range(1, 6):
            wal.append(entrada(i))
        wal.truncate_from(3)
        assert [e.idx for e in wal.iter_all()] == [1, 2]
        wal.append(entrada(3, epoch=9))  # a cauda pode ser reescrita com outro epoch
        assert wal.last_idx == 3 and wal.last_epoch == 9

    def test_truncate_abaixo_do_commit_index_e_recusado(self, tmp_path):
        """Apagar algo ja confirmado seria perder dinheiro confirmado."""
        wal = WriteAheadLog(tmp_path / "wal.jsonl", fsync_mode="off")
        log = ReplicatedLog(wal, ["A", "B", "C"], "B")
        log.append_from_leader(0, [entrada(1), entrada(2), entrada(3)])
        log.set_commit(3)
        with pytest.raises(ValueError, match="confirmado"):
            log.append_from_leader(1, [entrada(2, epoch=9)])
        assert wal.last_idx == 3


class TestRecuperacao:
    def test_replay_reconstroi_o_estado_exato(self, tmp_path):
        estado = recover(tmp_path)
        operacoes = [
            Operation("c1", OpType.CREATE_ACCOUNT, account_id="alice", amount_cents=10000),
            Operation("c2", OpType.CREATE_ACCOUNT, account_id="bob", amount_cents=0),
            Operation("t1", OpType.TRANSFER, from_account="alice", to_account="bob", amount_cents=2500),
        ]
        for i, operacao in enumerate(operacoes, start=1):
            item = LogEntry(i, 1, operacao)
            estado.wal.append(item)
            estado.store.apply(item)
        total = estado.store.total_cents()
        estado.wal.close()

        recuperado = recover(tmp_path)
        assert recuperado.store.total_cents() == total
        assert recuperado.store.get_balance("bob") == 2500
        assert recuperado.store.last_applied_idx == 3
        recuperado.wal.close()

    def test_snapshot_mais_wal_equivale_ao_wal_completo(self, tmp_path):
        estado = recover(tmp_path)
        for i, operacao in enumerate(
            [
                Operation("c1", OpType.CREATE_ACCOUNT, account_id="alice", amount_cents=1000),
                Operation("d1", OpType.DEPOSIT, account_id="alice", amount_cents=500),
            ],
            start=1,
        ):
            item = LogEntry(i, 1, operacao)
            estado.wal.append(item)
            estado.store.apply(item)
        snapshot_module.save(estado.store, tmp_path / "snapshot.json", last_included_epoch=1)
        item = LogEntry(3, 1, Operation("d2", OpType.DEPOSIT, account_id="alice", amount_cents=250))
        estado.wal.append(item)
        estado.store.apply(item)
        estado.wal.close()

        recuperado = recover(tmp_path)
        assert recuperado.store.get_balance("alice") == 1750
        # A tabela de deduplicacao tem de sobreviver, senao uma retentativa apos
        # reinicio reaplicaria uma operacao ja aplicada.
        assert "d1" in recuperado.store.applied
        recuperado.wal.close()

    def test_snapshot_corrompido_e_recusado(self, tmp_path):
        (tmp_path / "snapshot.json").write_text(
            '{"meta":{"last_included_idx":3,"last_included_epoch":1,"total_cents":999},'
            '"accounts":{"alice":1}}',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="inconsistente"):
            recover(tmp_path)
