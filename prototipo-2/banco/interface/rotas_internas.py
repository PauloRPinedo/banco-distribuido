"""As rotas entre servidores.

Separadas das de cliente porque a audiência é outra: aqui quem chama é um nó, e
as respostas são de protocolo, não de banco. Um cliente nunca devia precisar
destas rotas, e quem lê `rotas.py` não devia ter de passar por elas para perceber
o que o banco oferece.

Nenhuma delas levanta `ErroDoBanco`: uma recusa de protocolo é uma resposta
normal, com `ok: false` e o motivo. Traduzi-la para um estado HTTP de erro faria o
nó que chama tratar uma discordância legítima — um epoch velho, um log
divergente — como uma falha de rede, e o protocolo deixaria de convergir.
"""

import re

from banco.cluster.eleicao import PedidoDeVoto
from banco.cluster.no import No
from banco.interface.pedido import Pedido, Rota
from banco.persistencia.entrada import EntradaDeLog

# Um lote muito grande bloquearia o nó a desserializar enquanto o líder espera.
# Uma réplica muito atrasada usa /interno/log, que é o caminho feito para isso.
MAXIMO_DE_ENTRADAS = 500


def estado(no: No, _pedido: Pedido) -> tuple[int, dict]:
    """Papel, epoch e índices.

    Serve duas audiências: os outros nós, para saberem quem manda, e quem prepara
    a demonstração e quer confirmar com `curl` que a porta está aberta antes de
    subir o cluster.
    """
    return 200, no.estado_do_no()


def cluster(no: No, _pedido: Pedido) -> tuple[int, dict]:
    """O cluster inteiro visto por este nó, para o frontend (F-11).

    Rota **nova**, e não um campo a mais em `/interno/estado`, de propósito:
    aquela é chamada pelos pares em cada heartbeat e pelo `verificar_rede.sh`, e
    pô-la a fazer chamadas de rede tornaria o caminho quente caro — e recursivo.
    Esta chama o `/interno/estado` simples dos pares, por isso a recursão é
    impossível por construção.
    """
    return 200, no.estado_do_cluster()


def replicar(no: No, pedido: Pedido) -> tuple[int, dict]:
    """Replicação e heartbeat no mesmo RPC.

    Com `entradas` vazio é um heartbeat. Reaproveitar o RPC garante que o
    heartbeat carrega sempre o `epoch` e o `commit_lider` certos — um segundo
    caminho de código acabaria por divergir do primeiro.
    """
    corpo = pedido.corpo
    entradas = [_entrada_de_json(bruto)
                for bruto in corpo.get("entradas", [])[:MAXIMO_DE_ENTRADAS]]
    resposta = no.replicar(
        epoch=int(corpo.get("epoch", 0)),
        id_lider=str(corpo.get("id_lider", "")),
        indice_anterior=int(corpo.get("indice_anterior", 0)),
        epoch_anterior=int(corpo.get("epoch_anterior", 0)),
        entradas=entradas,
        commit_lider=int(corpo.get("commit_lider", 0)),
        ensaio=corpo.get("ensaio"))
    return 200, resposta


def votar(no: No, pedido: Pedido) -> tuple[int, dict]:
    """Pedido de voto, com as três condições do voto."""
    corpo = pedido.corpo
    return 200, no.votar(PedidoDeVoto(
        epoch=int(corpo.get("epoch", 0)),
        id_candidato=str(corpo.get("id_candidato", "")),
        ultimo_indice=int(corpo.get("ultimo_indice", 0)),
        ultimo_epoch=int(corpo.get("ultimo_epoch", 0))))


def log(no: No, pedido: Pedido) -> tuple[int, dict]:
    """`GET /interno/log?desde=N` para a réplica muito atrasada.

    Existe para não pôr um log inteiro dentro de um heartbeat: uma réplica que
    esteve fora cem operações põe-se em dia de uma vez, em vez de arrastar o
    ritmo do cluster durante cem rondas.
    """
    desde = pedido.inteiro("desde", 0)
    entradas = no.log.ler_desde(desde)[:MAXIMO_DE_ENTRADAS]
    return 200, {"desde": desde,
                 "indice_commit": no.log.indice_commit,
                 "entradas": [_entrada_em_json(e) for e in entradas]}


ROTAS: list[Rota] = [
    ("GET", re.compile(r"^/interno/estado$"), estado),
    ("GET", re.compile(r"^/interno/cluster$"), cluster),
    ("POST", re.compile(r"^/interno/replicar$"), replicar),
    ("POST", re.compile(r"^/interno/votar$"), votar),
    ("GET", re.compile(r"^/interno/log$"), log),
]


def _entrada_de_json(bruto: dict) -> EntradaDeLog:
    return EntradaDeLog(indice=int(bruto["indice"]), epoch=int(bruto["epoch"]),
                        op_id=str(bruto["op_id"]), tipo=str(bruto["tipo"]),
                        dados=bruto["dados"], instante=float(bruto["instante"]))


def _entrada_em_json(entrada: EntradaDeLog) -> dict:
    return {"indice": entrada.indice, "epoch": entrada.epoch,
            "op_id": entrada.op_id, "tipo": entrada.tipo,
            "dados": entrada.dados, "instante": entrada.instante}
