"""Três nós a falar por HTTP: eleição, replicação e quórum (subfases 2.2 a 2.5).

Não há `sleep` de valor fixo em lado nenhum: espera-se por condições, com limite
de tempo. Um `sleep` passa na máquina de quem o escreveu e falha na do colega, e
quando falha não se sabe se o erro é do código ou do relógio.
"""

import json
import unittest
import urllib.error
import urllib.request

from banco.dominio.erros import NaoSouPrimario, SemQuorum
from banco.dominio.operacoes import CriarConta, Deposito, Transferencia
from tests.ajudas import (criar_cluster_de_teste, esperar_ate,
                          esperar_por_primario)


class TesteEleicao(unittest.TestCase):

    def teste_o_cluster_elege_um_primario(self):
        cluster = criar_cluster_de_teste(self)

        primario = esperar_por_primario(self, cluster.nos)

        self.assertIn(primario.id, {no.id for no in cluster.nos})

    def teste_todos_arrancam_como_replica(self):
        """Quem manda decide-se por eleição, nunca pela memória.

        Verifica-se antes de o ciclo ter tempo de correr — daí olhar para o papel
        imediatamente a seguir a construir o cluster.
        """
        cluster = criar_cluster_de_teste(self, timeout_eleicao_ms=(3000, 4000))

        papeis = {no.estado_do_no()["papel"] for no in cluster.nos}

        self.assertEqual(papeis, {"réplica"})

    def teste_nunca_ha_dois_primarios_no_mesmo_epoch(self):
        """A garantia central do fencing.

        Duas maiorias intersectam-se sempre, e cada nó vota uma vez por epoch:
        logo não pode haver dois primários no mesmo epoch. Se isto falhar, o
        dinheiro pode duplicar-se.
        """
        cluster = criar_cluster_de_teste(self)
        esperar_por_primario(self, cluster.nos)

        por_epoch = {}
        for no in cluster.nos:
            estado = no.estado_do_no()
            if estado["papel"] == "primário":
                por_epoch.setdefault(estado["epoch"], []).append(no.id)

        for epoch, primarios in por_epoch.items():
            self.assertEqual(len(primarios), 1,
                             f"dois primários no epoch {epoch}: {primarios}")

    def teste_as_replicas_reconhecem_o_lider(self):
        cluster = criar_cluster_de_teste(self)
        primario = esperar_por_primario(self, cluster.nos)
        replicas = cluster.outros(primario)

        conhecem = esperar_ate(
            lambda: all(no.eleicao.lider_conhecido == primario.id
                        for no in replicas))

        self.assertTrue(conhecem,
                        {no.id: no.eleicao.lider_conhecido for no in replicas})


class TesteEscrita(unittest.TestCase):

    def setUp(self):
        self.cluster = criar_cluster_de_teste(self)
        self.nos = self.cluster.nos
        self.primario = esperar_por_primario(self, self.nos)
        self.replicas = self.cluster.outros(self.primario)

    def teste_o_primario_aceita_escritas(self):
        resposta = self.primario.executar("c1", CriarConta("alice", 10000))

        self.assertEqual(resposta["saldo_centavos"], 10000)

    def teste_a_replica_recusa_escritas(self):
        with self.assertRaises(NaoSouPrimario) as capturado:
            self.replicas[0].executar("c1", CriarConta("alice", 10000))

        self.assertEqual(capturado.exception.estado_http, 409)

    def teste_a_recusa_diz_a_quem_perguntar(self):
        """Sem isto, o cliente teria de tentar os nós às cegas.

        Espera-se que a réplica tenha recebido um heartbeat: antes disso ela
        ainda não sabe quem manda, e responder "não sou eu, mas não sei quem é" é
        a resposta correta — não uma falha.
        """
        replica = self.replicas[0]
        esperar_ate(lambda: replica.eleicao.lider_conhecido is not None)

        with self.assertRaises(NaoSouPrimario) as capturado:
            replica.executar("c1", CriarConta("alice", 10000))

        self.assertEqual(capturado.exception.primario_provavel,
                         f"127.0.0.1:{self.cluster.porta_de(self.primario.id)}")

    def teste_a_recusa_sem_lider_conhecido_nao_inventa_um_endereco(self):
        """Apontar para um nó ao acaso seria pior do que não apontar.

        O cliente seguiria o endereço errado, levaria outro 409, e a mensagem
        deixaria de significar alguma coisa.
        """
        cluster = criar_cluster_de_teste(self, timeout_eleicao_ms=(3000, 4000))

        with self.assertRaises(NaoSouPrimario) as capturado:
            cluster.nos[0].executar("c1", CriarConta("alice", 10000))

        self.assertIsNone(capturado.exception.primario_provavel)

    def teste_a_escrita_chega_as_replicas(self):
        self.primario.executar("c1", CriarConta("alice", 10000))

        chegou = esperar_ate(
            lambda: all(no.log.ultimo_indice >= self.primario.log.ultimo_indice
                        for no in self.replicas))

        self.assertTrue(chegou,
                        {no.id: no.log.ultimo_indice for no in self.nos})

    def teste_a_replica_aplica_o_que_esta_confirmado(self):
        self.primario.executar("c1", CriarConta("alice", 10000))
        self.primario.executar("c2", CriarConta("bob", 0))
        self.primario.executar("t1", Transferencia("alice", "bob", 2500))

        igual = esperar_ate(
            lambda: all(no.auditoria()["total_centavos"] == 10000
                        for no in self.replicas))

        self.assertTrue(igual,
                        {no.id: no.auditoria() for no in self.nos})

    def teste_as_replicas_podem_ser_lidas(self):
        """RF-11: o cluster continua a responder a leituras."""
        self.primario.executar("c1", CriarConta("alice", 10000))
        esperar_ate(lambda: self.replicas[0].livro.contas)

        self.assertEqual(self.replicas[0].auditoria()["total_centavos"], 10000)

    def teste_a_invariante_aguenta_o_cluster(self):
        """RNF-01 com replicação pelo meio: o total não muda."""
        self.primario.executar("c1", CriarConta("alice", 10000))
        self.primario.executar("c2", CriarConta("bob", 5000))
        antes = self.primario.auditoria()["total_centavos"]

        for numero in range(20):
            self.primario.executar(f"t{numero}",
                                   Transferencia("alice", "bob", 100))
            self.primario.executar(f"d{numero}", Deposito("alice", 100))
            self.primario.executar(f"s{numero}",
                                   Transferencia("bob", "alice", 100))

        depois = self.primario.auditoria()
        self.assertEqual(depois["total_centavos"], antes + 20 * 100)
        self.assertFalse(depois["divergente"])

    def teste_a_noop_do_proprio_epoch_e_gravada_ao_assumir(self):
        """Sem ela, uma entrada herdada não se pode confirmar."""
        entradas = self.primario.log.ler_desde(0)

        self.assertTrue(any(e.tipo == "noop" for e in entradas),
                        [e.tipo for e in entradas])

    def teste_a_noop_nao_cria_dinheiro(self):
        """Se a noop contasse para a auditoria, cada failover criaria dinheiro."""
        self.primario.executar("c1", CriarConta("alice", 10000))

        resultado = self.primario.auditoria()

        self.assertEqual(resultado["total_centavos"], 10000)
        self.assertFalse(resultado["divergente"])


class TesteSemQuorum(unittest.TestCase):

    def teste_com_um_no_so_as_escritas_sao_recusadas(self):
        """Com 3 nós a maioria é 2: um nó sozinho não confirma nada.

        É o preço honesto de RNF-02 — e é a razão pela qual se correm 3 nós
        mesmo com 2 laptops.
        """
        cluster = criar_cluster_de_teste(self)
        primario = esperar_por_primario(self, cluster.nos)
        primario.executar("c1", CriarConta("alice", 10000))

        for no in cluster.outros(primario):
            cluster.derrubar(no)

        with self.assertRaises(SemQuorum):
            primario.executar("d1", Deposito("alice", 100))

    def teste_sem_quorum_a_leitura_continua_a_funcionar(self):
        cluster = criar_cluster_de_teste(self)
        primario = esperar_por_primario(self, cluster.nos)
        primario.executar("c1", CriarConta("alice", 10000))
        for no in cluster.outros(primario):
            cluster.derrubar(no)
        with self.assertRaises(SemQuorum):
            primario.executar("d1", Deposito("alice", 100))

        self.assertEqual(primario.saldo("alice")["saldo_centavos"], 10000)

    def teste_sem_quorum_o_dinheiro_nao_se_move(self):
        """A entrada fica gravada por confirmar, mas não aplicada."""
        cluster = criar_cluster_de_teste(self)
        primario = esperar_por_primario(self, cluster.nos)
        primario.executar("c1", CriarConta("alice", 10000))
        antes = primario.auditoria()["total_centavos"]
        for no in cluster.outros(primario):
            cluster.derrubar(no)

        with self.assertRaises(SemQuorum):
            primario.executar("d1", Deposito("alice", 5000))

        self.assertEqual(primario.auditoria()["total_centavos"], antes)


if __name__ == "__main__":
    unittest.main()


class TesteVistaDoCluster(unittest.TestCase):
    """`/interno/cluster`: os três nós a partir de um endereço só.

    É o que permite ao frontend desenhar os três cartões com um túnel apenas —
    na demonstração há um, não três.
    """

    def setUp(self):
        self.cluster = criar_cluster_de_teste(self)
        self.primario = esperar_por_primario(self, self.cluster.nos)

    def teste_lista_os_tres_nos(self):
        vista = self.primario.estado_do_cluster()

        self.assertEqual([no["no"] for no in vista["nos"]], ["A", "B", "C"])

    def teste_diz_quem_respondeu(self):
        """A resposta é o que **este** nó sabe; apresentá-la sem dono seria mentir."""
        vista = self.primario.estado_do_cluster()

        self.assertEqual(vista["eu"], self.primario.id)

    def teste_traz_a_maioria_da_configuracao(self):
        self.assertEqual(self.primario.estado_do_cluster()["maioria"], 2)

    def teste_a_ordem_e_a_do_ficheiro_e_nao_a_das_respostas(self):
        """Cartões a trocar de sítio a cada segundo não se conseguem ler."""
        primeira = [no["no"] for no in self.primario.estado_do_cluster()["nos"]]
        segunda = [no["no"] for no in self.primario.estado_do_cluster()["nos"]]

        self.assertEqual(primeira, segunda)
        self.assertEqual(primeira, sorted(primeira))

    def teste_uma_replica_tambem_ve_o_cluster(self):
        """O túnel pode apontar a qualquer nó, e durante um failover aponta mesmo."""
        replica = self.cluster.outros(self.primario)[0]

        vista = replica.estado_do_cluster()

        self.assertEqual(vista["eu"], replica.id)
        self.assertEqual(len(vista["nos"]), 3)

    def teste_o_no_derrubado_aparece_sem_contacto(self):
        """Some da lista seria pior: é justamente o nó em falta que interessa."""
        alvo = self.cluster.outros(self.primario)[0]
        self.cluster.derrubar(alvo)

        vista = self.primario.estado_do_cluster()

        caido = next(no for no in vista["nos"] if no["no"] == alvo.id)
        self.assertFalse(caido["vivo"])
        self.assertEqual(len(vista["nos"]), 3)

    def teste_um_no_derrubado_nao_atrasa_a_resposta(self):
        """Uma página que atualiza a cada segundo não pode esperar por um morto."""
        import time
        self.cluster.derrubar(self.cluster.outros(self.primario)[0])
        prazo = self.primario.configuracao.timeout_replicacao_ms / 1000

        comeco = time.monotonic()
        self.primario.estado_do_cluster()
        demorou = time.monotonic() - comeco

        self.assertLess(demorou, prazo * 2 + 1)

    def teste_o_no_isolado_aparece_sem_contacto(self):
        """Uma partição injetada tem de ver-se igual a um nó caído."""
        alvo = self.cluster.outros(self.primario)[0]
        self.primario.falhas.isolar([alvo.id])

        vista = self.primario.estado_do_cluster()

        isolado = next(no for no in vista["nos"] if no["no"] == alvo.id)
        self.assertFalse(isolado["vivo"])
        self.assertIn("isolado", isolado["motivo"])

    def teste_um_no_sozinho_ve_se_a_si_proprio(self):
        """Sem cluster não há pares, e a vista continua a fazer sentido."""
        from tests.ajudas import criar_no_de_teste

        sozinho = criar_no_de_teste(self)
        vista = sozinho.estado_do_cluster()

        self.assertEqual(vista["maioria"], 1)
        self.assertEqual(len(vista["nos"]), 1)
        self.assertTrue(vista["nos"][0]["vivo"])


class TesteReencaminhamento(unittest.TestCase):
    """Uma réplica reenvia a escrita ao primário em vez de a recusar.

    Existe por causa do frontend: o túnel HTTPS aponta a **um** nó, e o
    `primario_provavel` de um 409 é um endereço de LAN que o navegador não
    alcança. Sem isto, o failover partiria a página exatamente no momento em que
    ela serve para alguma coisa.
    """

    def setUp(self):
        self.cluster = criar_cluster_de_teste(self, encaminhar_escritas=True)
        self.primario = esperar_por_primario(self, self.cluster.nos)
        self.replica = self.cluster.outros(self.primario)[0]
        esperar_ate(lambda: self.replica.eleicao.lider_conhecido is not None)

    def pedir(self, no, metodo, caminho, corpo=None):
        porta = self.cluster.porta_de(no.id)
        dados = json.dumps(corpo).encode() if corpo is not None else None
        pedido = urllib.request.Request(
            f"http://127.0.0.1:{porta}{caminho}", data=dados, method=metodo,
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(pedido, timeout=5) as resposta:
                return resposta.status, json.loads(resposta.read())
        except urllib.error.HTTPError as erro:
            return erro.code, json.loads(erro.read())

    def teste_a_replica_aceita_a_escrita_reencaminhando(self):
        estado, corpo = self.pedir(self.replica, "POST", "/contas",
                                   {"conta": "alice", "saldo_inicial": "100.00",
                                    "op_id": "r1"})

        self.assertEqual(estado, 201)
        self.assertEqual(corpo["saldo_centavos"], 10000)

    def teste_a_escrita_reencaminhada_fica_no_primario(self):
        """A réplica é um cliente puro: não grava nada por sua conta."""
        self.pedir(self.replica, "POST", "/contas",
                   {"conta": "alice", "saldo_inicial": "100.00", "op_id": "r1"})

        self.assertEqual(self.primario.saldo("alice")["saldo_centavos"], 10000)

    def teste_uma_recusa_por_regra_chega_tal_e_qual(self):
        """Reencaminhar não pode maquilhar o que o banco respondeu."""
        self.pedir(self.replica, "POST", "/contas",
                   {"conta": "alice", "saldo_inicial": "1.00", "op_id": "r1"})
        self.pedir(self.replica, "POST", "/contas",
                   {"conta": "bob", "saldo_inicial": "0", "op_id": "r2"})

        estado, corpo = self.pedir(
            self.replica, "POST", "/transferencias",
            {"de": "alice", "para": "bob", "valor": "9999.00", "op_id": "r3"})

        self.assertEqual(estado, 422)
        self.assertEqual(corpo["erro"], "saldo_insuficiente")

    def teste_o_mesmo_op_id_reencaminhado_nao_duplica(self):
        """O op_id vem no corpo original, por isso o reenvio é seguro de repetir."""
        corpo = {"conta": "alice", "saldo_inicial": "100.00", "op_id": "r1"}
        self.pedir(self.replica, "POST", "/contas", corpo)

        estado, _ = self.pedir(self.replica, "POST", "/contas", corpo)

        self.assertEqual(estado, 201)
        self.assertEqual(self.primario.auditoria()["total_centavos"], 10000)

    def teste_sem_a_bandeira_a_replica_continua_a_recusar(self):
        """O reencaminhamento é uma escolha, não o comportamento por omissão."""
        cluster = criar_cluster_de_teste(self)
        primario = esperar_por_primario(self, cluster.nos)
        replica = cluster.outros(primario)[0]

        with self.assertRaises(NaoSouPrimario):
            replica.executar("x1", CriarConta("alice", 100))
