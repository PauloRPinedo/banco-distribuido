"""Falar com um nó por HTTP.

Está separado do `cli` porque é a parte que a etapa 2 tem de estender: seguir o
`primario_provavel` de um 409, tentar o nó seguinte da lista, repetir com o mesmo
op_id. A apresentação não muda por causa disso, e não deve ter de ser tocada.
"""

import json
import urllib.error
import urllib.request

TEMPO_LIMITE = 10


class RecusaDoBanco(Exception):
    """O nó respondeu, e disse que não.

    Guarda o estado HTTP em bruto: quem chama é que decide o que fazer com ele.
    """

    def __init__(self, estado_http: int, codigo: str, mensagem: str) -> None:
        super().__init__(mensagem)
        self.estado_http = estado_http
        self.codigo = codigo
        self.mensagem = mensagem


class ServidorInacessivel(Exception):
    """O nó não pôde atender.

    `respondeu` separa duas situações que parecem a mesma e não são: o processo
    estar em baixo, e o processo estar de pé mas incapaz de gravar — disco
    cheio, por exemplo. Quem está à frente do ecrã precisa de saber qual é.
    """

    def __init__(self, mensagem: str, respondeu: bool = False) -> None:
        super().__init__(mensagem)
        self.respondeu = respondeu


def pedir(servidor: str, metodo: str, caminho: str,
          corpo: dict | None = None) -> dict:
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    pedido = urllib.request.Request(
        servidor.rstrip("/") + caminho, data=dados, method=metodo,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE) as resposta:
            return json.loads(resposta.read())
    except urllib.error.HTTPError as falha:
        if falha.code >= 500:
            try:
                detalhe = json.loads(falha.read()).get("mensagem", "")
            except (json.JSONDecodeError, ValueError):
                detalhe = ""
            raise ServidorInacessivel(
                f"respondeu {falha.code}" + (f": {detalhe}" if detalhe else ""),
                respondeu=True) from falha
        try:
            problema = json.loads(falha.read())
        except (json.JSONDecodeError, ValueError):
            problema = {}
        raise RecusaDoBanco(falha.code,
                            problema.get("erro", "erro_desconhecido"),
                            problema.get("mensagem", str(falha))) from falha
    except (urllib.error.URLError, TimeoutError, ConnectionError) as falha:
        raise ServidorInacessivel(str(getattr(falha, "reason", falha))) from falha
