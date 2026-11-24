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

import http.client
import json
import threading
import urllib.parse
from dataclasses import dataclass

from banco.autenticacao.chaves import CABECALHO_CLUSTER, chave_do_cluster
from banco.cluster.configuracao import NoDoCluster

# As ligações abertas aos pares, por thread: abrir uma ligação nova (e
# resolver o nome do par) a cada envio era um dos custos de cada escrita. Os
# envios de replicação saem sempre da mesma thread por par, por isso cada
# ligação fica aberta enquanto o par a mantiver.
_local = threading.local()


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
    cabecalhos = {"Content-Type": "application/json",
                  CABECALHO_CLUSTER: chave_do_cluster()}
    url = urllib.parse.urlsplit(no.url)
    for tentativa in (1, 2):
        ligacao, reaproveitada = _ligacao(url.hostname, url.port or 80, prazo_ms / 1000)
        try:
            ligacao.request(metodo, caminho, body=dados, headers=cabecalhos)
            resposta = ligacao.getresponse()
            conteudo = resposta.read()
            estado = resposta.status
        except (http.client.RemoteDisconnected, BrokenPipeError,
                ConnectionResetError) as falha:
            _esquecer(url.hostname, url.port or 80)
            # Uma ligação guardada que o par fechou entretanto: repete-se uma
            # vez com uma nova. Os RPCs do protocolo podem repetir-se.
            if reaproveitada and tentativa == 1:
                continue
            return Resposta(False, motivo=str(falha))
        except (http.client.HTTPException, TimeoutError, OSError) as falha:
            _esquecer(url.hostname, url.port or 80)
            return Resposta(False, motivo=str(falha))
        try:
            lido = json.loads(conteudo) if conteudo else {}
        except (json.JSONDecodeError, ValueError) as falha:
            # Respondeu com algo que não é JSON: para o protocolo vale tanto
            # como não ter respondido, mas o motivo distingue-se no log.
            return Resposta(False, motivo=f"resposta ilegível: {falha}")
        # Respondeu, mesmo que a dizer que não: um `409 epoch_velho` é
        # informação de protocolo, não uma falha de rede.
        return Resposta(True, estado, lido)
    return Resposta(False, motivo="sem ligação")


def _ligacao(anfitriao: str, porta: int, prazo_s: float):
    """(ligação, reaproveitada) a este par, nesta thread."""
    ligacoes = getattr(_local, "ligacoes", None)
    if ligacoes is None:
        ligacoes = _local.ligacoes = {}
    ligacao = ligacoes.get((anfitriao, porta))
    if ligacao is not None:
        ligacao.timeout = prazo_s
        if ligacao.sock is not None:
            ligacao.sock.settimeout(prazo_s)
        return ligacao, True
    ligacao = http.client.HTTPConnection(anfitriao, porta, timeout=prazo_s)
    ligacoes[(anfitriao, porta)] = ligacao
    return ligacao, False


def _esquecer(anfitriao: str, porta: int) -> None:
    ligacoes = getattr(_local, "ligacoes", {})
    ligacao = ligacoes.pop((anfitriao, porta), None)
    if ligacao is not None:
        ligacao.close()
