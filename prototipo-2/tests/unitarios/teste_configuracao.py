"""Carregamento e validação do ficheiro do cluster (subfase 2.1)."""

import json
import tempfile
import unittest
from pathlib import Path

from banco.cluster.configuracao import (ConfiguracaoDoCluster,
                                        ConfiguracaoInvalida)

VALIDA = {
    "nos": [
        {"id": "A", "endereco": "192.168.0.11", "porta": 8001},
        {"id": "B", "endereco": "192.168.0.12", "porta": 8001},
        {"id": "C", "endereco": "192.168.0.12", "porta": 8002},
    ],
    "heartbeat_ms": 150,
    "timeout_eleicao_ms": [800, 1500],
    "timeout_replicacao_ms": 500,
    "semente": 42,
}


def com(**mudancas):
    bruto = json.loads(json.dumps(VALIDA))
    bruto.update(mudancas)
    return bruto


class TesteCarregamento(unittest.TestCase):

    def teste_le_o_exemplo_versionado(self):
        """O ficheiro de exemplo do repositório tem de ser sempre válido.

        É o primeiro comando que alguém corre numa máquina nova; se ele estiver
        partido, o erro aparece no pior momento possível.
        """
        caminho = Path(__file__).parents[2] / "config" / "cluster.exemplo.json"

        configuracao = ConfiguracaoDoCluster.de_ficheiro(caminho)

        self.assertEqual([no.id for no in configuracao.nos], ["A", "B", "C"])

    def teste_ficheiro_que_nao_existe_diz_como_o_criar(self):
        with tempfile.TemporaryDirectory() as pasta:
            with self.assertRaises(ConfiguracaoInvalida) as capturado:
                ConfiguracaoDoCluster.de_ficheiro(Path(pasta) / "nao_existe.json")

        self.assertIn("cluster.exemplo.json", str(capturado.exception))

    def teste_url_de_um_no(self):
        configuracao = ConfiguracaoDoCluster.de_dados(VALIDA)

        self.assertEqual(configuracao.obter("C").url, "http://192.168.0.12:8002")


class TesteMaioria(unittest.TestCase):

    def teste_tres_nos_maioria_dois(self):
        self.assertEqual(ConfiguracaoDoCluster.de_dados(VALIDA).maioria, 2)

    def teste_dois_nos_maioria_continua_a_ser_dois(self):
        """O motivo pelo qual se correm 3 nós mesmo com 2 laptops.

        Com 2 nós, a queda de um deixa o outro sem maioria e em somente leitura:
        não há failover com escrita para demonstrar.
        """
        dois = com(nos=VALIDA["nos"][:2])

        self.assertEqual(ConfiguracaoDoCluster.de_dados(dois).maioria, 2)


class TesteSementePorNo(unittest.TestCase):

    def teste_cada_no_sorteia_a_sua_semente(self):
        """O erro mais caro desta etapa, segundo o próprio ROADMAP.

        Com a mesma semente nos três, todos sorteiam o mesmo timeout,
        candidatam-se juntos, dividem os votos, e a eleição nunca converge — com
        um sintoma que parece um erro de protocolo.
        """
        configuracao = ConfiguracaoDoCluster.de_dados(VALIDA)

        sementes = {configuracao.semente_do_no(no.id) for no in configuracao.nos}

        self.assertEqual(len(sementes), 3)

    def teste_a_semente_de_um_no_e_sempre_a_mesma(self):
        """RNF-06: a mesma semente global tem de dar a mesma execução.

        Usar `hash()` em vez de `crc32` partiria isto sem dar sinal: o hash de
        uma string muda a cada arranque do interpretador.
        """
        primeira = ConfiguracaoDoCluster.de_dados(VALIDA).semente_do_no("A")
        segunda = ConfiguracaoDoCluster.de_dados(VALIDA).semente_do_no("A")

        self.assertEqual(primeira, segunda)


class TesteValidacao(unittest.TestCase):

    def recusa(self, bruto, trecho):
        with self.assertRaises(ConfiguracaoInvalida) as capturado:
            ConfiguracaoDoCluster.de_dados(bruto)
        self.assertIn(trecho, str(capturado.exception))

    def teste_ids_repetidos(self):
        repetidos = com(nos=[VALIDA["nos"][0], dict(VALIDA["nos"][0], porta=8002)])

        self.recusa(repetidos, "ids repetidos")

    def teste_dois_nos_no_mesmo_endereco_e_porta(self):
        chocam = com(nos=[VALIDA["nos"][0], dict(VALIDA["nos"][1],
                                                 endereco="192.168.0.11")])

        self.recusa(chocam, "mesmo endereço e porta")

    def teste_heartbeat_demasiado_perto_do_timeout(self):
        """A validação que evita um cluster a trocar de primário sem parar."""
        apertado = com(heartbeat_ms=400)

        self.recusa(apertado, "demasiado perto")

    def teste_a_mensagem_diz_o_valor_maximo_aceitavel(self):
        """Um erro que não diz o passo seguinte deixa quem o lê onde estava."""
        with self.assertRaises(ConfiguracaoInvalida) as capturado:
            ConfiguracaoDoCluster.de_dados(com(heartbeat_ms=400))

        self.assertIn("200 ms", str(capturado.exception))

    def teste_intervalo_de_eleicao_invertido(self):
        self.recusa(com(timeout_eleicao_ms=[1500, 800]), "menor que")

    def teste_cluster_sem_nos(self):
        self.recusa(com(nos=[]), "não tem nós")

    def teste_campo_em_falta(self):
        sem_semente = json.loads(json.dumps(VALIDA))
        del sem_semente["semente"]

        self.recusa(sem_semente, "'semente'")

    def teste_porta_como_booleano_e_recusada(self):
        """`bool` é subclasse de `int` em Python: sem cuidado, isto passava."""
        estranho = com(nos=[dict(VALIDA["nos"][0], porta=True)])

        self.recusa(estranho, "'porta'")

    def teste_no_desconhecido_lista_os_conhecidos(self):
        configuracao = ConfiguracaoDoCluster.de_dados(VALIDA)

        with self.assertRaises(ConfiguracaoInvalida) as capturado:
            configuracao.obter("Z")

        self.assertIn("A, B, C", str(capturado.exception))


if __name__ == "__main__":
    unittest.main()
