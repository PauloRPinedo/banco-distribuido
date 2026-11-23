"""As duas chaves que não são de um utilizador: a do cluster e a de operador.

**Chave do cluster.** As rotas entre nós (`/interno/replicar`, `/interno/votar`,
`/interno/log`) mudam o log ou mostram-no inteiro. Na AWS a porta 8001 de cada
nó está aberta à Internet (o balanceador em Lambda chega por IP público), por
isso, sem chave, um pedido forjado com um `epoch` alto seria aceite como vindo
de um líder legítimo. A chave deriva-se da `SECRET_KEY`, que já é igual nos
três nós: não há um segundo segredo para distribuir, e quem não a tem não
consegue nem emitir tokens nem falar como um par.

**Chave de operador** (`CHAVE_ADMIN`). Registar uma taxa de câmbio muda quanto
vale o dinheiro de toda a gente: com qualquer sessão bastava registar uma taxa
absurda e converter. Sem `CHAVE_ADMIN` definida, a rota recusa sempre.

As comparações são em tempo constante e sobre bytes: `compare_digest` com
`str` não-ASCII levanta `TypeError`, e um cabeçalho vem de fora.
"""

import hashlib
import hmac
import os

from banco.autenticacao.token import _chave

CABECALHO_CLUSTER = "X-Chave-Cluster"
CABECALHO_ADMIN = "X-Chave-Admin"


def chave_do_cluster() -> str:
    return hmac.new(_chave(), b"banco/cluster-interno", hashlib.sha256).hexdigest()


def _iguais(recebida: str | None, esperada: str | None) -> bool:
    if not recebida or not esperada:
        return False
    return hmac.compare_digest(recebida.encode("utf-8"), esperada.encode("utf-8"))


def e_chave_do_cluster(recebida: str | None) -> bool:
    return _iguais(recebida, chave_do_cluster())


def e_chave_de_admin(recebida: str | None) -> bool:
    return _iguais(recebida, os.environ.get("CHAVE_ADMIN"))


def falhas_ativas() -> bool:
    """A injeção de falhas só existe se se pedir: `FALHAS_ATIVAS=1`.

    No compose local liga-se, para as demonstrações; na AWS fica desligada,
    porque `POST /admin/falha {"tipo": "derrubar"}` mata o nó.
    """
    return os.environ.get("FALHAS_ATIVAS") == "1"
