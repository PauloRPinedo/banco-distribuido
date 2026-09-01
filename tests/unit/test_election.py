"""Eleicao: restricao de voto e fencing por epoch (RF-09)."""

from __future__ import annotations

from bank.domain.operations import Operation, OpType
from bank.election.election import ElectionManager
from bank.election.node_state import NodeRole, NodeState
from bank.election.protocol_types import ElectionOutcome
from bank.replication.log import ReplicatedLog
from bank.replication.protocol import RequestVote, VoteReply
from bank.storage.wal import WriteAheadLog


def montar(tmp_path, node_id: str, epochs=()):
    """No com um log cujas entradas tem os epochs dados, em ordem."""
    wal = WriteAheadLog(tmp_path / f"wal-{node_id}.jsonl", fsync_mode="off")
    log = ReplicatedLog(wal, ["A", "B", "C"], node_id)
    for epoch in epochs:
        log.append_local(Operation(f"x{log.last_idx}", OpType.NOOP), epoch)
    return NodeState(node_id, tmp_path / f"state-{node_id}.json"), log


class ParesFalsos:
    """Respostas fixas por par; ``None`` simula no fora do ar."""

    def __init__(self, respostas):
        self.respostas = respostas

    def request_vote(self, node_id, message, timeout_s):
        return self.respostas.get(node_id)


class TestConcessaoDeVoto:
    def test_nao_vota_duas_vezes_no_mesmo_epoch(self, tmp_path):
        """Se votasse duas vezes, dois candidatos poderiam ter maioria."""
        estado, log = montar(tmp_path, "C", [1])
        eleicao = ElectionManager(estado, log, ParesFalsos({}), ["A", "B"], lambda: None)
        primeiro = eleicao.handle_request_vote(RequestVote(2, "A", last_idx=1, last_epoch=1))
        assert primeiro.granted
        segundo = eleicao.handle_request_vote(RequestVote(2, "B", last_idx=9, last_epoch=9))
        assert not segundo.granted and segundo.reason == "already_voted"

    def test_recusa_candidato_com_log_atrasado(self, tmp_path):
        """A garantia central: quem tem log atrasado nao pode virar primario,
        senao operacoes confirmadas sumiriam."""
        estado, log = montar(tmp_path, "C", [1, 1, 2])  # last_epoch=2, last_idx=3
        eleicao = ElectionManager(estado, log, ParesFalsos({}), ["A", "B"], lambda: None)

        atrasado = eleicao.handle_request_vote(RequestVote(3, "A", last_idx=2, last_epoch=1))
        assert not atrasado.granted and atrasado.reason == "log_behind"

        em_dia = eleicao.handle_request_vote(RequestVote(3, "A", last_idx=3, last_epoch=2))
        assert em_dia.granted

    def test_epoch_antigo_e_recusado_como_stale(self, tmp_path):
        estado, log = montar(tmp_path, "C", [1])
        estado.observe_epoch(5)
        eleicao = ElectionManager(estado, log, ParesFalsos({}), ["A", "B"], lambda: None)
        resposta = eleicao.handle_request_vote(RequestVote(2, "A", last_idx=9, last_epoch=9))
        assert not resposta.granted and resposta.reason == "stale_epoch"

    def test_voto_e_persistido_antes_da_resposta(self, tmp_path):
        """Votar, cair e esquecer o voto elegeria dois primarios."""
        estado, log = montar(tmp_path, "C", [1])
        eleicao = ElectionManager(estado, log, ParesFalsos({}), ["A", "B"], lambda: None)
        assert eleicao.handle_request_vote(RequestVote(4, "A", last_idx=1, last_epoch=1)).granted

        # Simula a queda: um NodeState novo le o mesmo arquivo de estado.
        reiniciado = NodeState("C", tmp_path / "state-C.json")
        assert reiniciado.epoch == 4 and reiniciado.voted_for == "A"
        assert not reiniciado.grant_vote(4, "B"), "apos reiniciar votou de novo no mesmo epoch"


class TestApuracao:
    def test_vence_com_maioria(self, tmp_path):
        estado, log = montar(tmp_path, "B", [1])
        promovido = []
        eleicao = ElectionManager(
            estado,
            log,
            ParesFalsos({"A": None, "C": VoteReply(1, True, "C")}),
            ["A", "C"],
            lambda: promovido.append(True),
        )
        assert eleicao.start_election() is ElectionOutcome.WON
        assert estado.role is NodeRole.PRIMARY and promovido == [True]

    def test_perde_sem_maioria(self, tmp_path):
        estado, log = montar(tmp_path, "B", [1])
        eleicao = ElectionManager(
            estado,
            log,
            ParesFalsos({"A": None, "C": VoteReply(1, False, "C", "already_voted")}),
            ["A", "C"],
            lambda: None,
        )
        assert eleicao.start_election() is ElectionOutcome.LOST
        assert estado.role is NodeRole.REPLICA


class TestFencing:
    def test_primario_antigo_com_epoch_menor_e_rejeitado(self, tmp_path):
        estado, log = montar(tmp_path, "C", [1])
        estado.observe_epoch(8)
        eleicao = ElectionManager(estado, log, ParesFalsos({}), ["A", "B"], lambda: None)
        resposta = eleicao.handle_request_vote(RequestVote(3, "A", last_idx=1, last_epoch=1))
        assert not resposta.granted and resposta.epoch == 8

    def test_epoch_maior_rebaixa_o_primario_atual(self, tmp_path):
        estado, _ = montar(tmp_path, "A", [1])
        estado.start_candidacy()
        estado.become_primary()
        assert estado.role is NodeRole.PRIMARY
        assert estado.observe_epoch(99, leader_id="B") is True
        assert estado.role is NodeRole.REPLICA and estado.epoch == 99

    def test_candidato_desiste_ao_ver_epoch_maior_na_apuracao(self, tmp_path):
        estado, log = montar(tmp_path, "B", [1])
        eleicao = ElectionManager(
            estado, log, ParesFalsos({"A": VoteReply(50, False, "A"), "C": None}), ["A", "C"], lambda: None
        )
        assert eleicao.start_election() is ElectionOutcome.STEPPED_DOWN
        assert estado.epoch == 50 and estado.role is NodeRole.REPLICA
