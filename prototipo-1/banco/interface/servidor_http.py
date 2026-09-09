"""Servidor HTTP do nó, sobre a biblioteca padrão.

Escolheu-se HTTP em vez de sockets crus por uma razão operacional: quando o
cluster da etapa 2 não convergir nos laptops, um `curl` diz em cinco segundos se
o problema é a firewall ou o protocolo.

A tradução de erros acontece **num sítio só**, em `_responder_erro`. Uma rota
levanta o erro de domínio que quiser e nunca precisa de saber códigos HTTP.
"""

import json
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from banco.cluster.no import No
from banco.dominio.erros import ErroDoBanco
from banco.interface import rotas

TAMANHO_MAXIMO_DO_CORPO = 64 * 1024


class _Manipulador(BaseHTTPRequestHandler):

    protocol_version = "HTTP/1.1"
    no: No

    def do_GET(self) -> None:
        self._atender("GET")

    def do_POST(self) -> None:
        self._atender("POST")

    def _atender(self, metodo: str) -> None:
        caminho = urlparse(self.path).path
        encontrada = rotas.encontrar(metodo, caminho)
        if encontrada is None:
            self._responder(404, {"erro": "rota_inexistente",
                                  "mensagem": f"{metodo} {caminho} não existe"})
            return

        funcao, partes = encontrada
        try:
            corpo = self._ler_corpo()
        except ValueError as erro:
            self._responder(400, {"erro": "corpo_invalido",
                                  "mensagem": str(erro)})
            return

        try:
            estado, resposta = funcao(self.no, partes, corpo)
        except ErroDoBanco as erro:
            self._responder(erro.estado_http, erro.para_json())
        except Exception as inesperado:  # noqa: BLE001
            # Uma falha não prevista — disco cheio, por exemplo — não pode
            # deixar cair a ligação sem resposta: o cliente leria isso como
            # "servidor em baixo" e sairia com o código 3, quando o banco está
            # de pé e apenas recusou. O rasto vai para stderr, porque engolir o
            # erro esconderia a causa.
            traceback.print_exc()
            self._responder(500, {"erro": "erro_interno",
                                  "mensagem": str(inesperado)})
        else:
            self._responder(estado, resposta)

    def _ler_corpo(self) -> dict:
        comprimento = int(self.headers.get("Content-Length") or 0)
        if comprimento == 0:
            return {}
        if comprimento > TAMANHO_MAXIMO_DO_CORPO:
            raise ValueError("corpo demasiado grande")
        bruto = self.rfile.read(comprimento)
        try:
            corpo = json.loads(bruto.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as erro:
            raise ValueError(f"corpo não é JSON válido: {erro}") from erro
        if not isinstance(corpo, dict):
            raise ValueError("o corpo tem de ser um objeto JSON")
        return corpo

    def _responder(self, estado: int, conteudo: dict) -> None:
        bruto = json.dumps(conteudo, ensure_ascii=False).encode("utf-8")
        self.send_response(estado)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(bruto)))
        # Uma resposta por ligação. Com o keep-alive do HTTP/1.1, a thread que
        # atendeu fica bloqueada à espera de um pedido seguinte que nunca vem,
        # e o encerramento do servidor tem de esperar por ela. Os clientes deste
        # projeto — o CLI, o curl e, na etapa 2, os outros nós — fazem um pedido
        # de cada vez, por isso não se perde nada em fechar.
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(bruto)
        self.close_connection = True

    def log_message(self, formato: str, *argumentos) -> None:
        """Silencia o log por pedido do BaseHTTPRequestHandler.

        O log estruturado de RNF-07 é da etapa 3. Até lá, uma linha por pedido
        para stderr só faz ruído durante a demonstração.
        """


def criar_servidor(no: No, endereco: str, porta: int) -> ThreadingHTTPServer:
    """Liga em 0.0.0.0 por omissão.

    Ligar a 127.0.0.1 faria o nó funcionar em testes locais e ser inalcançável
    do outro laptop — o modo de falha que a etapa 2 mais tem de evitar.
    """
    manipulador = type("Manipulador", (_Manipulador,), {"no": no})
    return ThreadingHTTPServer((endereco, porta), manipulador)
