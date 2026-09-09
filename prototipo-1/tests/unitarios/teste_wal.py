"""WAL, recuperação e deduplicação (subfase 1.4)."""

import tempfile
import unittest
from pathlib import Path

from banco.cluster.no import No
from banco.dominio.erros import SaldoInsuficiente
from banco.dominio.operacoes import CriarConta, Deposito, Saque, Transferencia
from banco.persistencia.entrada import EntradaDeLog
from banco.persistencia.wal import Wal, WalCorrompido


class BaseComDiretorio(unittest.TestCase):

    def setUp(self):
        self._temporario = tempfile.TemporaryDirectory()
        self.diretorio = Path(self._temporario.name)
        self.addCleanup(self._temporario.cleanup)

    def caminho_do_wal(self):
        return self.diretorio / "wal.jsonl"


class TesteWal(BaseComDiretorio):

    def teste_wal_vazio_le_lista_vazia(self):
        wal = Wal(self.caminho_do_wal())
        self.addCleanup(wal.fechar)

        self.assertEqual(wal.ler_tudo(), [])

    def teste_entrada_gravada_e_relida_igual(self):
        wal = Wal(self.caminho_do_wal())
        self.addCleanup(wal.fechar)
        entrada = EntradaDeLog.de_operacao(1, "op-1", CriarConta("alice", 100), 1.5)

        wal.acrescentar(entrada)

        self.assertEqual(wal.ler_tudo(), [entrada])

    def teste_ordem_das_entradas_e_preservada(self):
        wal = Wal(self.caminho_do_wal())
        self.addCleanup(wal.fechar)
        for indice in range(1, 11):
            wal.acrescentar(
                EntradaDeLog.de_operacao(indice, f"op-{indice}",
                                         Deposito("alice", indice), 0.0))

        indices = [entrada.indice for entrada in wal.ler_tudo()]

        self.assertEqual(indices, list(range(1, 11)))

    def teste_linha_final_truncada_e_descartada(self):
        # O rasto normal de um processo morto a meio de uma escrita. Como o
        # fsync ainda não devolvera, essa operação nunca foi confirmada.
        wal = Wal(self.caminho_do_wal())
        wal.acrescentar(EntradaDeLog.de_operacao(1, "op-1",
                                                 CriarConta("alice", 100), 0.0))
        wal.fechar()
        with open(self.caminho_do_wal(), "a", encoding="utf-8") as ficheiro:
            ficheiro.write('{"indice":2,"epoch":1,"op_id":"op-2","tip')

        wal = Wal(self.caminho_do_wal())
        self.addCleanup(wal.fechar)
        entradas = wal.ler_tudo()

        self.assertEqual(len(entradas), 1)
        self.assertEqual(entradas[0].indice, 1)

    def teste_ficheiro_e_truncado_para_o_append_seguinte_nao_colar(self):
        wal = Wal(self.caminho_do_wal())
        wal.acrescentar(EntradaDeLog.de_operacao(1, "op-1",
                                                 CriarConta("alice", 100), 0.0))
        wal.fechar()
        with open(self.caminho_do_wal(), "a", encoding="utf-8") as ficheiro:
            ficheiro.write('{"indice":2,"lixo')

        wal = Wal(self.caminho_do_wal())
        self.addCleanup(wal.fechar)
        wal.ler_tudo()
        wal.acrescentar(EntradaDeLog.de_operacao(2, "op-2",
                                                 Deposito("alice", 50), 0.0))

        self.assertEqual([e.indice for e in wal.ler_tudo()], [1, 2])

    def teste_linha_corrompida_no_meio_e_denunciada(self):
        # Diferente de uma cauda truncada: significa que o ficheiro foi mexido
        # por fora, e seguir em frente seria aplicar um log com um buraco.
        caminho = self.caminho_do_wal()
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text('{"nao":"e uma entrada"}\n{"tambem":"nao"}\n',
                           encoding="utf-8")
        wal = Wal(caminho)
        self.addCleanup(wal.fechar)

        with self.assertRaises(WalCorrompido):
            wal.ler_tudo()


class TesteRecuperacao(BaseComDiretorio):

    def criar_no(self):
        no = No("A", self.diretorio)
        self.addCleanup(no.fechar)
        return no

    def teste_estado_sobrevive_a_reinicio(self):
        no = self.criar_no()
        no.executar("op-1", CriarConta("alice", 10000))
        no.executar("op-2", CriarConta("bob", 0))
        no.executar("op-3", Transferencia("alice", "bob", 2500))
        antes = no.auditoria()
        no.fechar()

        renascido = self.criar_no()

        self.assertEqual(renascido.saldo("alice")["saldo_centavos"], 7500)
        self.assertEqual(renascido.saldo("bob")["saldo_centavos"], 2500)
        self.assertEqual(renascido.auditoria()["total_centavos"],
                         antes["total_centavos"])

    def teste_extrato_sobrevive_a_reinicio(self):
        no = self.criar_no()
        no.executar("op-1", CriarConta("alice", 10000))
        no.executar("op-2", Deposito("alice", 500))
        no.fechar()

        renascido = self.criar_no()

        self.assertEqual(len(renascido.extrato("alice")["movimentos"]), 2)

    def teste_indice_continua_de_onde_ficou(self):
        no = self.criar_no()
        no.executar("op-1", CriarConta("alice", 100))
        no.fechar()

        renascido = self.criar_no()
        renascido.executar("op-2", Deposito("alice", 100))

        self.assertEqual(renascido.estado_do_no()["ultimo_indice"], 2)

    def teste_operacao_recusada_nao_fica_no_log(self):
        no = self.criar_no()
        no.executar("op-1", CriarConta("alice", 100))

        with self.assertRaises(SaldoInsuficiente):
            no.executar("op-2", Saque("alice", 999999))

        self.assertEqual(no.estado_do_no()["ultimo_indice"], 1)


class TesteDeduplicacao(BaseComDiretorio):

    def setUp(self):
        super().setUp()
        self.no = No("A", self.diretorio)
        self.addCleanup(self.no.fechar)
        self.no.executar("criar-1", CriarConta("alice", 10000))
        self.no.executar("criar-2", CriarConta("bob", 0))

    def teste_op_id_repetido_nao_move_o_dinheiro_duas_vezes(self):
        self.no.executar("transf-1", Transferencia("alice", "bob", 2500))

        self.no.executar("transf-1", Transferencia("alice", "bob", 2500))

        self.assertEqual(self.no.saldo("alice")["saldo_centavos"], 7500)

    def teste_repeticao_devolve_a_mesma_resposta(self):
        primeira = self.no.executar("transf-1", Transferencia("alice", "bob", 2500))

        segunda = self.no.executar("transf-1", Transferencia("alice", "bob", 2500))

        self.assertEqual(primeira, segunda)

    def teste_repeticao_nao_acrescenta_entrada_ao_log(self):
        self.no.executar("transf-1", Transferencia("alice", "bob", 2500))
        indice = self.no.estado_do_no()["ultimo_indice"]

        self.no.executar("transf-1", Transferencia("alice", "bob", 2500))

        self.assertEqual(self.no.estado_do_no()["ultimo_indice"], indice)

    def teste_deduplicacao_sobrevive_a_reinicio(self):
        self.no.executar("transf-1", Transferencia("alice", "bob", 2500))
        self.no.fechar()

        renascido = No("A", self.diretorio)
        self.addCleanup(renascido.fechar)
        renascido.executar("transf-1", Transferencia("alice", "bob", 2500))

        self.assertEqual(renascido.saldo("alice")["saldo_centavos"], 7500)


class TesteAuditoria(BaseComDiretorio):

    def teste_os_dois_calculos_batem(self):
        no = No("A", self.diretorio)
        self.addCleanup(no.fechar)
        no.executar("op-1", CriarConta("alice", 10000))
        no.executar("op-2", CriarConta("bob", 500))
        no.executar("op-3", Deposito("bob", 250))
        no.executar("op-4", Saque("alice", 100))
        no.executar("op-5", Transferencia("alice", "bob", 1000))

        resultado = no.auditoria()

        self.assertEqual(resultado["total_centavos"], 10650)
        self.assertEqual(resultado["total_esperado_centavos"], 10650)
        self.assertFalse(resultado["divergente"])


if __name__ == "__main__":
    unittest.main()
