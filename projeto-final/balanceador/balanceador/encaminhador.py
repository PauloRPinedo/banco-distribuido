"""O balanceador próprio.

Não é um balanceador de carga clássico (*round-robin*): só o primário aceita
escritas, e as leituras também vão a ele, porque as réplicas aplicam as entradas
um heartbeat depois e podiam devolver um saldo atrasado. Este componente
descobre quem é o primário, guarda-o em cache e manda-lhe tudo.

Não volta a perguntar antes de cada pedido: isso custava uma ida e volta a
mais por pedido. Cada resposta de um nó traz `X-Primario-Pronto: sim` ou `nao`,
e uma leitura que volta com `nao` (o nó deixou de ser primário, ou ainda não
aplicou a `noop` do seu mandato) faz esquecer a cache e repetir no primário
certo. As ligações aos nós reaproveitam-se (um `httpx.Client` partilhado).

Quando o primário muda — caiu, ou perdeu uma eleição — o pedido falha de uma de
duas maneiras, e as duas tratam-se igual: esquecer a cache, voltar a descobrir,
e repetir **uma vez**. Repetir é seguro porque as escritas levam o `op_id` do
cliente: se a primeira tentativa chegou a ser aplicada, a segunda devolve o
resultado guardado.

- a ligação falha (o nó morreu): redescobrir;
- `409 nao_sou_primario`: o nó diz quem julga ser o primário; tenta-se esse;
- `503 somente_leitura` ou `sem_quorum`: o nó ainda se diz primário mas perdeu
  a maioria (uma partição que o balanceador não vê). Redescobre-se; se houver
  outro primário, de epoch maior, repete-se lá; senão devolve-se o 503.

Se dois nós se dizem primários (o antigo, isolado, ainda não soube que perdeu),
vale o de epoch maior: foi esse que a maioria elegeu.

Sem primário nenhum (uma eleição a decorrer, ou só um nó de pé), as escritas
recebem `503 sem_primario`. As leituras (`GET`) vão ao nó vivo com mais log
aplicado, e a resposta leva `X-Leitura-De-Replica: <nó>`: o saldo pode vir
atrasado, porque esse nó não sabe se a maioria confirmou mais alguma coisa.

Sem estado durável: se este processo reinicia, volta a perguntar. Por isso
correr duas cópias não precisa de nenhum protocolo de consenso.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

import httpx

logger = logging.getLogger("balanceador")

PAPEIS_DE_PRIMARIO = ("primário", "primario")
# O cabeçalho com que cada nó diz, em cada resposta, se é um primário pronto.
CABECALHO_PRONTO = "x-primario-pronto"
# Respostas de um primário que perdeu a maioria: a escrita não foi confirmada.
ERROS_SEM_MAIORIA = ("somente_leitura", "sem_quorum")


class SemPrimario(Exception):
    """Nenhum nó se diz primário — há uma eleição a decorrer, ou não há maioria."""


class Encaminhador:

    def __init__(self, nos: list[dict], url_base_fn, timeout_s: float = 2.0,
                 timeout_sonda_s: float = 0.5, cliente: httpx.Client | None = None) -> None:
        self._nos = nos
        self._url_base = url_base_fn
        self._timeout_s = timeout_s
        self._timeout_sonda_s = timeout_sonda_s
        self._primario_em_cache: str | None = None
        # Um cliente para todos os pedidos: mantém as ligações aos nós abertas.
        self._cliente = cliente or httpx.Client(
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=64))

    def _estado(self, url: str) -> dict | None:
        """O `/interno/estado` do nó, ou None se não responde."""
        try:
            r = self._cliente.get(f"{url}/interno/estado", timeout=self._timeout_sonda_s)
            if r.status_code == 200:
                return r.json()
        except (httpx.HTTPError, ValueError):
            pass
        return None

    def _sondar(self, url: str) -> tuple[str, int] | None:
        """(url, epoch) se o nó se diz primário; None se não, ou se não responde."""
        estado = self._estado(url)
        # Um primário acabado de eleger só serve depois de aplicar a sua `noop`
        # (`pronto`): antes disso, uma leitura podia não ver uma escrita já
        # confirmada pelo primário anterior. Dura uma ronda de replicação.
        if (estado and estado.get("papel") in PAPEIS_DE_PRIMARIO
                and estado.get("pronto", True)):
            return url, int(estado.get("epoch") or 0)
        return None

    def encontrar_primario(self, ignorar_cache: bool = False) -> str:
        """O primário em cache; sem cache, pergunta aos três ao mesmo tempo.

        A cache não se confirma aqui: confirma-a cada resposta, pelo cabeçalho
        `X-Primario-Pronto`, e esquece-se quando um pedido falha.

        Em paralelo, e com um *timeout* curto: perguntar um a um esperaria pelo
        nó morto antes de chegar aos vivos, e é exatamente quando há um morto
        que a resposta é urgente. Entre vários que se digam primários, o de
        epoch maior.
        """
        if not ignorar_cache and self._primario_em_cache:
            return self._primario_em_cache
        urls = [self._url_base(no) for no in self._nos]
        with ThreadPoolExecutor(max_workers=len(urls)) as executor:
            encontrados = [r for r in executor.map(self._sondar, urls) if r]
        if not encontrados:
            self._primario_em_cache = None
            raise SemPrimario("nenhum nó se diz primário")
        self._primario_em_cache = max(encontrados, key=lambda r: r[1])[0]
        return self._primario_em_cache

    def reenviar(self, metodo: str, caminho: str, **kwargs) -> httpx.Response:
        """Reenvia ao primário; se ele mudou entretanto, redescobre e repete uma vez."""
        try:
            url = self.encontrar_primario()
        except SemPrimario:
            if metodo != "GET":
                raise
            return self._ler_de_uma_replica(caminho, **kwargs)
        try:
            resposta = self._pedir(metodo, f"{url}{caminho}", **kwargs)
        except httpx.HTTPError as falha:
            logger.info("o primário %s não respondeu (%s); a redescobrir", url, falha)
            self._primario_em_cache = None
            return self._repetir(metodo, caminho, **kwargs)

        if resposta.status_code == 409 and _diz_nao_sou_primario(resposta):
            provavel = resposta.json().get("primario_provavel")
            logger.info("%s já não é primário; primário provável: %s", url, provavel)
            self._primario_em_cache = provavel
            return self._repetir(metodo, caminho, **kwargs)

        if resposta.status_code == 503 and _erro(resposta) in ERROS_SEM_MAIORIA:
            # Repetir é seguro: a escrita não foi confirmada, e o op_id é o mesmo.
            try:
                outro = self.encontrar_primario(ignorar_cache=True)
            except SemPrimario:
                return resposta
            if outro != url:
                logger.info("%s perdeu a maioria; a repetir em %s", url, outro)
                return self._pedir(metodo, f"{outro}{caminho}", **kwargs)
            return resposta

        if resposta.headers.get(CABECALHO_PRONTO) == "nao" and metodo == "GET":
            # O nó já não é um primário pronto: a leitura podia vir atrasada.
            # Uma escrita não chega aqui — o nó tê-la-ia recusado com um 409.
            logger.info("%s já não é um primário pronto; a redescobrir", url)
            self._primario_em_cache = None
            try:
                outro = self.encontrar_primario()
            except SemPrimario:
                return self._ler_de_uma_replica(caminho, **kwargs)
            return self._pedir(metodo, f"{outro}{caminho}", **kwargs)
        return resposta

    def _pedir(self, metodo: str, url: str, **kwargs) -> httpx.Response:
        return self._cliente.request(metodo, url, timeout=self._timeout_s, **kwargs)

    def _ler_de_uma_replica(self, caminho: str, **kwargs) -> httpx.Response:
        """Sem primário: uma leitura ao nó vivo com mais log aplicado, marcada."""
        urls = [self._url_base(no) for no in self._nos]
        with ThreadPoolExecutor(max_workers=len(urls)) as executor:
            vivos = [(url, estado) for url, estado in zip(urls, executor.map(self._estado, urls))
                     if estado]
        if not vivos:
            raise SemPrimario("nenhum nó responde")
        url, estado = max(vivos, key=lambda v: int(v[1].get("ultimo_aplicado") or 0))
        logger.info("sem primário; leitura de %s a partir de %s", caminho, url)
        resposta = self._pedir("GET", f"{url}{caminho}", **kwargs)
        resposta.headers["X-Leitura-De-Replica"] = str(estado.get("no") or url)
        return resposta

    def _repetir(self, metodo: str, caminho: str, **kwargs) -> httpx.Response:
        url = self.encontrar_primario()
        return self._pedir(metodo, f"{url}{caminho}", **kwargs)


def _erro(resposta: httpx.Response) -> str | None:
    try:
        return resposta.json().get("erro")
    except ValueError:
        return None


def _diz_nao_sou_primario(resposta: httpx.Response) -> bool:
    return _erro(resposta) == "nao_sou_primario"
