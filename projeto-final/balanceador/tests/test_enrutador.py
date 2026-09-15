"""Pruebas del enrutador — sin nodos reales, con httpx.MockTransport."""

import unittest

import httpx

from balanceador.enrutador import Enrutador

NODOS = [
    {"id": "A", "endereco": "nodo-a", "porta": 8001},
    {"id": "B", "endereco": "nodo-b", "porta": 8001},
    {"id": "C", "endereco": "nodo-c", "porta": 8001},
]


def _url_base(nodo):
    return f"http://{nodo['endereco']}:{nodo['porta']}"


class TestEncontrarPrimario(unittest.TestCase):

    def test_encuentra_al_primero_que_dice_ser_primario(self):
        def manejador(request: httpx.Request) -> httpx.Response:
            if "nodo-b" in str(request.url):
                return httpx.Response(200, json={"rol": "primario"})
            return httpx.Response(200, json={"rol": "replica"})

        cliente = httpx.Client(transport=httpx.MockTransport(manejador))
        original = httpx.get
        httpx.get = lambda url, timeout: cliente.get(url)
        try:
            enrutador = Enrutador(NODOS, _url_base)
            self.assertEqual(enrutador.encontrar_primario(), "http://nodo-b:8001")
        finally:
            httpx.get = original

    def test_cachea_el_primario_para_no_preguntar_de_nuevo(self):
        llamadas = []

        def manejador(request: httpx.Request) -> httpx.Response:
            llamadas.append(str(request.url))
            return httpx.Response(200, json={"rol": "primario"})

        cliente = httpx.Client(transport=httpx.MockTransport(manejador))
        original = httpx.get
        httpx.get = lambda url, timeout: cliente.get(url)
        try:
            enrutador = Enrutador(NODOS, _url_base)
            primera = enrutador.encontrar_primario()
            segunda = enrutador.encontrar_primario()
            self.assertEqual(primera, segunda)
            # la segunda vez, el cacheado va primero en la lista de candidatos
            self.assertTrue(llamadas[-1].startswith(primera))
        finally:
            httpx.get = original


if __name__ == "__main__":
    unittest.main()
