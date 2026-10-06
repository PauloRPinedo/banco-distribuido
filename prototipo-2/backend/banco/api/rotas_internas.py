"""As rotas entre nós, e a injeção de falhas.

A audiência aqui é outro nó, não um cliente. Uma recusa de protocolo — um epoch
velho, um log que não corresponde — é uma resposta normal (`ok: false` com o
motivo), e não um erro HTTP: tratá-la como falha de rede faria o protocolo
deixar de convergir.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from banco.api.dependencias import no_do_processo
from banco.cluster.eleicao import PedidoDeVoto
from banco.cluster.entrada import EntradaDeLog
from banco.dominio.erros import ValorInvalido

router = APIRouter()

# Um lote muito grande bloquearia o nó a desserializar enquanto o líder espera.
MAXIMO_DE_ENTRADAS = 500


class PedidoDeReplicacao(BaseModel):
    epoch: int
    id_lider: str
    indice_anterior: int
    epoch_anterior: int
    entradas: list[dict] = []
    commit_lider: int


class PedidoDeVotoHttp(BaseModel):
    epoch: int
    id_candidato: str
    ultimo_indice: int
    ultimo_epoch: int


class PedidoDeFalha(BaseModel):
    tipo: str               # atraso, isolar, derrubar, limpar
    ms: int = 0
    nos: list[str] = []


@router.get("/interno/estado")
def estado() -> dict:
    """Papel, epoch, líder conhecido e os três índices do log."""
    return no_do_processo().estado_do_no()


@router.get("/interno/cluster")
def cluster() -> dict:
    """O cluster inteiro visto por este nó: o painel desenha-o a partir daqui."""
    return no_do_processo().estado_do_cluster()


@router.post("/interno/replicar")
def replicar(pedido: PedidoDeReplicacao) -> dict:
    """Replicação e heartbeat no mesmo RPC: sem entradas, é um heartbeat."""
    entradas = [EntradaDeLog(indice=int(e["indice"]), epoch=int(e["epoch"]),
                             op_id=str(e["op_id"]), tipo=str(e["tipo"]),
                             dados=e["dados"], instante=float(e["instante"]))
                for e in pedido.entradas[:MAXIMO_DE_ENTRADAS]]
    return no_do_processo().replicar(
        pedido.epoch, pedido.id_lider, pedido.indice_anterior,
        pedido.epoch_anterior, entradas, pedido.commit_lider)


@router.post("/interno/votar")
def votar(pedido: PedidoDeVotoHttp) -> dict:
    return no_do_processo().votar(PedidoDeVoto(
        pedido.epoch, pedido.id_candidato, pedido.ultimo_indice, pedido.ultimo_epoch))


@router.get("/interno/log")
def log(desde: int = 0) -> dict:
    """O log a partir de um índice — para ver, à mão, que os nós concordam."""
    no = no_do_processo()
    entradas = no.log.ler_desde(desde)[:MAXIMO_DE_ENTRADAS]
    return {"desde": desde, "indice_commit": no.log.indice_commit,
            "entradas": [{"indice": e.indice, "epoch": e.epoch, "op_id": e.op_id,
                          "tipo": e.tipo, "dados": e.dados, "instante": e.instante}
                         for e in entradas]}


@router.post("/admin/falha")
def injetar_falha(pedido: PedidoDeFalha) -> dict:
    """RF-16: atrasar, isolar de outros nós, derrubar já, ou limpar.

    `isolar` reproduz uma partição de rede sem tocar na firewall: as mensagens
    de e para os nós indicados perdem-se nos dois sentidos. `derrubar` mata o
    processo sem fechar nada — é uma queda abrupta, não um desligar educado.
    """
    falhas = no_do_processo().falhas
    if pedido.tipo == "atraso":
        falhas.atraso(pedido.ms)
    elif pedido.tipo == "isolar":
        falhas.isolar(pedido.nos)
    elif pedido.tipo == "limpar":
        falhas.limpar()
    elif pedido.tipo == "derrubar":
        falhas.derrubar()
    else:
        raise ValorInvalido("tipo de falha: atraso, isolar, derrubar ou limpar")
    return {"no": no_do_processo().id, "falhas": falhas.em_json()}
