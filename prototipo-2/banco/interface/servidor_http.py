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
from urllib.parse import parse_qs, urlparse

from banco.cluster.no import No
from banco.dominio.erros import ErroDoBanco, NaoSouPrimario
from banco.interface import despacho
from banco.interface.cliente_interno import encaminhar
from banco.interface.pedido import Pedido

TAMANHO_MAXIMO_DO_CORPO = 64 * 1024


class _Manipulador(BaseHTTPRequestHandler):

    protocol_version = "HTTP/1.1"
    no: No
    origens: str = "*"
    encaminhar_escritas: bool = False

    def do_GET(self) -> None:
        self._atender("GET")

    def do_POST(self) -> None:
        self._atender("POST")

    def do_OPTIONS(self) -> None:
        """O *preflight* que o navegador faz antes de um POST com JSON.

        Responde 204 sem corpo. Não é uma rota do banco: é a pergunta que o
        navegador faz ao próprio protocolo, e a resposta são só cabeçalhos.
        """
        caminho = urlparse(self.path).path
        if not despacho.caminho_existe(caminho):
            self._responder(404, {"erro": "rota_inexistente",
                                  "mensagem": f"{caminho} não existe"})
            return
        self.send_response(204)
        self._cabecalhos_de_origem()
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

    def _atender(self, metodo: str) -> None:
        endereco = urlparse(self.path)
        caminho = endereco.path
        encontrada = despacho.encontrar(metodo, caminho)
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

        pedido = Pedido(partes=partes, corpo=corpo,
                        consulta=parse_qs(endereco.query))
        try:
            estado, resposta = funcao(self.no, pedido)
        except NaoSouPrimario as erro:
            if not self._reencaminhado(metodo, caminho, corpo, erro):
                self._responder(erro.estado_http, erro.para_json())
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

    def _reencaminhado(self, metodo: str, caminho: str, corpo: dict,
                       erro: NaoSouPrimario) -> bool:
        """Manda o pedido ao primário e devolve a resposta dele, tal e qual.

        Só acontece com `--encaminhar-escritas`, e existe por causa do frontend:
        o túnel aponta a um nó, e o `primario_provavel` de um 409 é um endereço
        de LAN que o navegador não alcança. Sem isto, o failover partiria a
        página exatamente no momento que ela existe para mostrar.

        Este nó não grava nada — é um cliente do primário como outro qualquer.
        """
        if not self.encaminhar_escritas or not erro.primario_provavel:
            return False
        prazo = self.no.configuracao.timeout_replicacao_ms * 2
        resposta = encaminhar(erro.primario_provavel, metodo, caminho, corpo,
                              prazo)
        if not resposta.respondeu:
            # O primário provável também não atende. Vale mais devolver o 409
            # original, que diz a verdade, do que inventar outro erro.
            return False
        self._responder(resposta.estado_http, resposta.corpo or {})
        return True

    def _cabecalhos_de_origem(self) -> None:
        """CORS, num sítio só.

        `*` por omissão, e é defensável aqui: não há autenticação nem cookies —
        estão fora do âmbito por decisão da proposta — e o endereço do frontend
        na Vercel muda a cada publicação, por isso uma origem fixa partir-se-ia
        sozinha. Quem quiser apertar usa `--origens`.
        """
        self.send_header("Access-Control-Allow-Origin", self.origens)
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Max-Age", "86400")

    def _responder(self, estado: int, conteudo: dict) -> None:
        bruto = json.dumps(conteudo, ensure_ascii=False).encode("utf-8")
        self.send_response(estado)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(bruto)))
        self._cabecalhos_de_origem()
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


def criar_servidor(no: No, endereco: str, porta: int, origens: str = "*",
                   encaminhar_escritas: bool = False) -> ThreadingHTTPServer:
    """Liga em 0.0.0.0 por omissão.

    Ligar a 127.0.0.1 faria o nó funcionar em testes locais e ser inalcançável
    do outro laptop — o modo de falha que a demonstração em dois laptops mais
    tem de evitar.
    """
    manipulador = type("Manipulador", (_Manipulador,),
                       {"no": no, "origens": origens,
                        "encaminhar_escritas": encaminhar_escritas})
    return ThreadingHTTPServer((endereco, porta), manipulador)
