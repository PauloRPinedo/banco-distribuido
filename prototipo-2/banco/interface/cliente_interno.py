"""Falar com outro nó do cluster.

Está separado do `cliente_http` porque as regras são outras. Um cliente humano
quer saber porque é que o banco recusou; um nó só quer saber se o par respondeu a
tempo. Aqui **nada levanta exceção para fora**: um par em baixo, uma porta
fechada ou um timeout são todos a mesma coisa — "este par não contou para o
quórum" — e o protocolo continua.

Confundir os dois é como se perde um cluster: se uma falha de rede subisse como
exceção pelo caminho da replicação, o primário morria a tentar falar com um nó
morto em vez de contar os votos que já tem.
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from banco.cluster.configuracao import NoDoCluster


@dataclass(frozen=True)
class Resposta:
    """O que se soube do par. `corpo` só faz sentido se `respondeu`."""

    respondeu: bool
    estado_http: int = 0
    corpo: dict | None = None
    motivo: str = ""

    def __bool__(self) -> bool:
        return self.respondeu and 200 <= self.estado_http < 300


def pedir_ao_no(no: NoDoCluster, caminho: str, corpo: dict | None = None,
                prazo_ms: int = 500, metodo: str = "POST") -> Resposta:
    """Um pedido a um par, com prazo. Nunca levanta.

    O prazo é o `timeout_replicacao_ms` da configuração: o primário não pode
    esperar por um nó lento mais do que o tempo que tem para responder ao
    cliente.
    """
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    pedido = urllib.request.Request(
        no.url + caminho, data=dados, method=metodo,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=prazo_ms / 1000) as resposta:
            return Resposta(True, resposta.status, json.loads(resposta.read()))
    except urllib.error.HTTPError as falha:
        # Respondeu, e disse que não. Isso conta: um `409 epoch_velho` é
        # informação de protocolo, não uma falha de rede.
        try:
            lido = json.loads(falha.read())
        except (json.JSONDecodeError, ValueError, OSError):
            lido = {}
        return Resposta(True, falha.code, lido)
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as falha:
        return Resposta(False, motivo=str(getattr(falha, "reason", falha)))
    except json.JSONDecodeError as falha:
        # Respondeu com algo que não é JSON: para o protocolo vale tanto como
        # não ter respondido, mas o motivo distingue-se no log.
        return Resposta(False, motivo=f"resposta ilegível: {falha}")


def encaminhar(endereco: str, metodo: str, caminho: str, corpo: dict | None,
               prazo_ms: int) -> Resposta:
    """Reenvia um pedido de cliente para outro nó, tal como veio.

    Existe para o frontend: o túnel HTTPS aponta a **um** nó, e quando esse nó
    deixa de ser primário responderia `409` com um `primario_provavel` que é um
    endereço de LAN — inalcançável do navegador. O nó passa a reencaminhar, e o
    failover vê-se na página sem ninguém tocar em nada.

    Quem reencaminha é um cliente puro: não grava nada, não toca no seu log, e
    por isso a ordem dos passos de uma escrita continua intacta. O `op_id` vem no
    corpo original, o que torna o reenvio seguro de repetir.
    """
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    pedido = urllib.request.Request(
        f"http://{endereco}{caminho}", data=dados, method=metodo,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=prazo_ms / 1000) as resposta:
            return Resposta(True, resposta.status, json.loads(resposta.read()))
    except urllib.error.HTTPError as falha:
        try:
            lido = json.loads(falha.read())
        except (json.JSONDecodeError, ValueError, OSError):
            lido = {}
        return Resposta(True, falha.code, lido)
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError,
            json.JSONDecodeError) as falha:
        return Resposta(False, motivo=str(getattr(falha, "reason", falha)))
