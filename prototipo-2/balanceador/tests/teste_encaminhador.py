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
        self.mortos: set[str] = set()
        self.pedidos: list[str] = []

    def responder(self, pedido: httpx.Request) -> httpx.Response:
        no = pedido.url.host
        self.pedidos.append(f"{pedido.method} {no}{pedido.url.path}")
        if no in self.mortos:
            raise httpx.ConnectError("ligação recusada", request=pedido)
        if pedido.url.path == "/interno/estado":
            papel = "primário" if no == self.primario else "réplica"
            return httpx.Response(200, json={"papel": papel})
        if no != self.primario:
            return httpx.Response(409, json={
                "erro": "nao_sou_primario",
                "primario_provavel": f"http://{self.primario}:8001"})
        return httpx.Response(200, json={"atendido_por": no})


class Base(unittest.TestCase):

    def setUp(self) -> None:
        self.rede = RedeFalsa("no-b")
        cliente = httpx.Client(transport=httpx.MockTransport(self.rede.responder))
        originais = (httpx.get, httpx.request)
        httpx.get = lambda url, timeout: cliente.get(url)
        httpx.request = lambda metodo, url, timeout, **kw: cliente.request(metodo, url, **kw)
        self.addCleanup(lambda: (setattr(httpx, "get", originais[0]),
                                 setattr(httpx, "request", originais[1])))
        self.encaminhador = Encaminhador(NOS, _url_base)


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

    def teste_segue_o_primario_provavel_de_um_409(self):
        self.encaminhador.encontrar_primario()
        self.rede.primario = "no-a"   # B perdeu a eleição mas continua vivo

        resposta = self.encaminhador.reenviar("POST", "/transferencias")

        self.assertEqual(resposta.json()["atendido_por"], "no-a")

    def teste_sem_primario_diz_que_nao_ha(self):
        self.rede.primario = "nenhum"
        with self.assertRaises(SemPrimario):
            self.encaminhador.encontrar_primario()


if __name__ == "__main__":
    unittest.main()
