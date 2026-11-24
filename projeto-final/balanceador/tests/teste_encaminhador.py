"""Testes do encaminhador — sem nós reais, com httpx.MockTransport."""

import unittest

import httpx

from balanceador.encaminhador import Encaminhador, SemPrimario

NOS = [
    {"id": "A", "endereco": "no-a", "porta": 8001},
    {"id": "B", "endereco": "no-b", "porta": 8001},
    {"id": "C", "endereco": "no-c", "porta": 8001},
]


def _url_base(no):
    return f"http://{no['endereco']}:{no['porta']}"


class RedeFalsa:
    """Responde por nó; um nó em `mortos` recusa a ligação."""

    def __init__(self, primario: str) -> None:
        self.primario = primario
        self.epoch = 1
        self.mortos: set[str] = set()
        # Antigos primários isolados da maioria: ainda se dizem primários, com
        # o epoch em que ficaram, e recusam escritas com 503 somente_leitura.
        self.isolados: dict[str, int] = {}
        # Quanto log cada nó já aplicou (o `ultimo_aplicado` do estado).
        self.aplicados: dict[str, int] = {}
        self.pedidos: list[str] = []

    def responder(self, pedido: httpx.Request) -> httpx.Response:
        no = pedido.url.host
        self.pedidos.append(f"{pedido.method} {no}{pedido.url.path}")
        if no in self.mortos:
            raise httpx.ConnectError("ligação recusada", request=pedido)
        if no in self.isolados:
            if pedido.url.path == "/interno/estado":
                return httpx.Response(200, json={"papel": "primário", "epoch": self.isolados[no]})
            return httpx.Response(503, json={"erro": "somente_leitura"})
        if pedido.url.path == "/interno/estado":
            papel = "primário" if no == self.primario else "réplica"
            return httpx.Response(200, json={"no": no[-1].upper(), "papel": papel,
                                             "epoch": self.epoch,
                                             "ultimo_aplicado": self.aplicados.get(no, 0)})
        # Como os nós a sério, cada resposta diz se vem de um primário pronto.
        pronto = {"X-Primario-Pronto": "sim" if no == self.primario else "nao"}
        if pedido.method == "GET":
            return httpx.Response(200, json={"atendido_por": no}, headers=pronto)
        if no != self.primario:
            return httpx.Response(409, json={
                "erro": "nao_sou_primario",
                "primario_provavel": f"http://{self.primario}:8001"}, headers=pronto)
        return httpx.Response(200, json={"atendido_por": no}, headers=pronto)


class Base(unittest.TestCase):

    def setUp(self) -> None:
        self.rede = RedeFalsa("no-b")
        cliente = httpx.Client(transport=httpx.MockTransport(lambda pedido: self.rede.responder(pedido)))
        self.addCleanup(cliente.close)
        self.encaminhador = Encaminhador(NOS, _url_base, cliente=cliente)


class TesteEncaminhador(Base):

    def teste_encontra_o_primario(self):
        self.assertEqual(self.encaminhador.encontrar_primario(), "http://no-b:8001")

    def teste_leituras_e_escritas_vao_ao_primario(self):
        for metodo in ("GET", "POST"):
            resposta = self.encaminhador.reenviar(metodo, "/contas/alice")
            self.assertEqual(resposta.json()["atendido_por"], "no-b")

    def teste_se_o_primario_morre_redescobre_e_repete(self):
        self.encaminhador.encontrar_primario()
        self.rede.mortos.add("no-b")
        self.rede.primario = "no-c"

        resposta = self.encaminhador.reenviar("POST", "/transferencias")

        self.assertEqual(resposta.json()["atendido_por"], "no-c")

    def teste_nao_pergunta_ao_primario_antes_de_cada_pedido(self):
        self.encaminhador.encontrar_primario()
        self.rede.pedidos.clear()

        for _ in range(5):
            self.encaminhador.reenviar("GET", "/contas/alice")
            self.encaminhador.reenviar("POST", "/transferencias")

        self.assertFalse([p for p in self.rede.pedidos if p.endswith("/interno/estado")],
                         self.rede.pedidos)
        self.assertEqual(len(self.rede.pedidos), 10)

    def teste_leitura_de_quem_deixou_de_ser_primario_repete_no_novo(self):
        self.encaminhador.encontrar_primario()
        self.rede.primario = "no-a"   # B perdeu a eleição mas continua vivo

        resposta = self.encaminhador.reenviar("GET", "/contas/alice")

        self.assertEqual(resposta.json()["atendido_por"], "no-a")
        self.assertEqual(self.encaminhador.encontrar_primario(), "http://no-a:8001")

    def teste_segue_o_primario_provavel_de_um_409(self):
        self.encaminhador.encontrar_primario()
        self.rede.primario = "no-a"   # B perdeu a eleição mas continua vivo

        resposta = self.encaminhador.reenviar("POST", "/transferencias")

        self.assertEqual(resposta.json()["atendido_por"], "no-a")

    def teste_entre_dois_que_se_dizem_primarios_escolhe_o_de_epoch_maior(self):
        # A ficou isolado no epoch 1; C foi eleito pela maioria no epoch 2.
        self.rede.isolados["no-a"] = 1
        self.rede.primario, self.rede.epoch = "no-c", 2

        self.assertEqual(self.encaminhador.encontrar_primario(), "http://no-c:8001")

    def teste_primario_isolado_que_recusa_escritas_redescobre_e_repete(self):
        # O balanceador ainda alcança o antigo primário, que continua a dizer-se
        # primário mas já não fala com a maioria.
        self.rede.primario = "no-a"
        self.encaminhador.encontrar_primario()
        self.rede.isolados["no-a"] = 1
        self.rede.primario, self.rede.epoch = "no-c", 2

        resposta = self.encaminhador.reenviar("POST", "/transferencias")

        self.assertEqual(resposta.json()["atendido_por"], "no-c")

    def teste_503_sem_outro_primario_devolve_o_503(self):
        self.rede.primario = "nenhum"
        self.rede.isolados["no-a"] = 1

        resposta = self.encaminhador.reenviar("POST", "/transferencias")

        self.assertEqual(resposta.status_code, 503)
        self.assertEqual(resposta.json()["erro"], "somente_leitura")

    def teste_sem_primario_diz_que_nao_ha(self):
        self.rede.primario = "nenhum"
        with self.assertRaises(SemPrimario):
            self.encaminhador.encontrar_primario()


if __name__ == "__main__":
    unittest.main()


class TesteSemPrimario(Base):
    """Só réplicas de pé: lê-se da mais adiantada, avisando; não se escreve."""

    def setUp(self) -> None:
        super().setUp()
        self.rede.primario = None
        self.rede.aplicados = {"no-a": 40, "no-c": 42}
        self.rede.mortos.add("no-b")

    def teste_leitura_vai_a_replica_mais_adiantada_e_diz_que_e_de_replica(self):
        resposta = self.encaminhador.reenviar("GET", "/contas/alice")

        self.assertEqual((resposta.json()["atendido_por"],
                          resposta.headers["X-Leitura-De-Replica"]), ("no-c", "C"))

    def teste_escrita_continua_sem_primario(self):
        with self.assertRaises(SemPrimario):
            self.encaminhador.reenviar("POST", "/contas/alice/deposito")

    def teste_sem_nenhum_no_vivo_nem_a_leitura_passa(self):
        self.rede.mortos.update({"no-a", "no-c"})

        with self.assertRaises(SemPrimario):
            self.encaminhador.reenviar("GET", "/contas/alice")

    def teste_com_primario_a_leitura_nao_e_marcada(self):
        self.rede.primario = "no-a"

        resposta = self.encaminhador.reenviar("GET", "/contas/alice")

        self.assertNotIn("X-Leitura-De-Replica", resposta.headers)


class TestePrimarioAindaNaoPronto(Base):

    def teste_primario_sem_a_noop_aplicada_nao_conta_como_primario(self):
        responder = self.rede.responder

        def ainda_nao_pronto(pedido):
            resposta = responder(pedido)
            if pedido.url.path == "/interno/estado" and pedido.url.host == "no-b":
                return httpx.Response(200, json={**resposta.json(), "pronto": False})
            return resposta

        self.rede.responder = ainda_nao_pronto

        with self.assertRaises(SemPrimario):
            self.encaminhador.encontrar_primario()
