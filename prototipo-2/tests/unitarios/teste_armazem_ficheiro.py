"""O que só o armazém em ficheiro pode fazer errado (subfase 1.4).

Estes casos não estão no contrato de `teste_armazem.py` de propósito: são modos
de falha do JSONL que uma base de dados não tem. Com o PostgreSQL, uma escrita
cortada a meio não deixa meia linha — a transação simplesmente não confirma.

É a razão pela qual o armazém em ficheiro continua a existir mesmo depois de o
PostgreSQL passar a principal: é aqui que se demonstra que o cenário do SIGKILL
foi pensado, e é a saída de emergência se a base não arrancar na demonstração.
"""

import tempfile
import unittest
from pathlib import Path

from banco.dominio.operacoes import CriarConta, Deposito
from banco.persistencia.armazem import LogCorrompido
from banco.persistencia.armazem_ficheiro import ArmazemEmFicheiro
from banco.persistencia.entrada import EntradaDeLog


class BaseComDiretorio(unittest.TestCase):

    def setUp(self):
        self._temporario = tempfile.TemporaryDirectory()
        self.diretorio = Path(self._temporario.name)
        self.addCleanup(self._temporario.cleanup)

    def caminho_do_log(self):
        return self.diretorio / "wal.jsonl"

    def abrir(self):
        armazem = ArmazemEmFicheiro(self.diretorio)
        self.addCleanup(armazem.fechar)
        return armazem


class TesteCaudaTruncada(BaseComDiretorio):

    def teste_linha_final_truncada_e_descartada(self):
        # O rasto normal de um processo morto a meio de uma escrita. Como o
        # fsync ainda não devolvera, essa operação nunca foi confirmada.
        armazem = self.abrir()
        armazem.acrescentar(EntradaDeLog.de_operacao(
            1, "op-1", CriarConta("alice", 100), 0.0))
        armazem.fechar()
        with open(self.caminho_do_log(), "a", encoding="utf-8") as ficheiro:
            ficheiro.write('{"indice":2,"epoch":1,"op_id":"op-2","tip')

        entradas = self.abrir().ler_desde(0)

        self.assertEqual(len(entradas), 1)
        self.assertEqual(entradas[0].indice, 1)

    def teste_ficheiro_e_truncado_para_o_append_seguinte_nao_colar(self):
        armazem = self.abrir()
        armazem.acrescentar(EntradaDeLog.de_operacao(
            1, "op-1", CriarConta("alice", 100), 0.0))
        armazem.fechar()
        with open(self.caminho_do_log(), "a", encoding="utf-8") as ficheiro:
            ficheiro.write('{"indice":2,"lixo')

        renascido = self.abrir()
        renascido.acrescentar(EntradaDeLog.de_operacao(
            2, "op-2", Deposito("alice", 50), 0.0))

        self.assertEqual([e.indice for e in renascido.ler_desde(0)], [1, 2])


class TesteLinhaCorrompida(BaseComDiretorio):

    def teste_linha_corrompida_no_meio_e_denunciada(self):
        # Diferente de uma cauda truncada: significa que o ficheiro foi mexido
        # por fora, e seguir em frente seria aplicar um log com um buraco.
        self.caminho_do_log().write_text(
            '{"nao":"e uma entrada"}\n{"tambem":"nao"}\n', encoding="utf-8")

        with self.assertRaises(LogCorrompido):
            ArmazemEmFicheiro(self.diretorio)


class TestePersistenciaEntreArranques(BaseComDiretorio):

    def teste_log_e_estado_sobrevivem_ao_fecho(self):
        armazem = self.abrir()
        armazem.acrescentar(EntradaDeLog.de_operacao(
            1, "op-1", CriarConta("alice", 100), 0.0))
        armazem.gravar_estado(5, "C")
        armazem.gravar_commit(1)
        armazem.fechar()

        renascido = self.abrir()

        self.assertEqual(renascido.ultimo_indice(), 1)
        estado = renascido.ler_estado()
        self.assertEqual((estado.epoch, estado.votou_em, estado.indice_commit),
                         (5, "C", 1))

    def teste_estado_antigo_sem_indice_commit_le_se_como_zero(self):
        """Compatibilidade com os `estado.json` gravados antes da replicação.

        Nessa altura nada era confirmado por maioria, porque não havia maioria:
        zero é o valor correto, não um valor por omissão escolhido à sorte.
        """
        (self.diretorio / "estado.json").write_text(
            '{"epoch": 3, "votou_em": null}', encoding="utf-8")

        self.assertEqual(self.abrir().ler_estado().indice_commit, 0)


if __name__ == "__main__":
    unittest.main()
