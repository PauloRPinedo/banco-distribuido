"""O balanceador próprio.

Não é um balanceador de carga clássico (*round-robin*): só o primário aceita
escritas, e as leituras também vão a ele, porque as réplicas aplicam as entradas
um heartbeat depois e podiam devolver um saldo atrasado. Este componente
descobre quem é o primário, guarda-o em cache e manda-lhe tudo.

Quando o primário muda — caiu, ou perdeu uma eleição — o pedido falha de uma de
duas maneiras, e as duas tratam-se igual: esquecer a cache, voltar a descobrir,
e repetir **uma vez**. Repetir é seguro porque as escritas levam o `op_id` do
cliente: se a primeira tentativa chegou a ser aplicada, a segunda devolve o
resultado guardado.

- a ligação falha (o nó morreu): redescobrir;
- `409 nao_sou_primario`: o nó diz quem julga ser o primário; tenta-se esse.

Sem estado durável: se este processo reinicia, volta a perguntar. Por isso
correr duas cópias não precisa de nenhum protocolo de consenso.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

import httpx

logger = logging.getLogger("balanceador")

PAPEIS_DE_PRIMARIO = ("primário", "primario")


class SemPrimario(Exception):
    """Nenhum nó se diz primário — há uma eleição a decorrer, ou não há maioria."""


class Encaminhador:

    def __init__(self, nos: list[dict], url_base_fn, timeout_s: float = 2.0,
                 timeout_sonda_s: float = 0.5) -> None:
        self._nos = nos
        self._url_base = url_base_fn
        self._timeout_s = timeout_s
        self._timeout_sonda_s = timeout_sonda_s
        self._primario_em_cache: str | None = None

    def _sondar(self, url: str) -> str | None:
        try:
            r = httpx.get(f"{url}/interno/estado", timeout=self._timeout_sonda_s)
            if r.status_code == 200 and r.json().get("papel") in PAPEIS_DE_PRIMARIO:
                return url
        except httpx.HTTPError:
            pass
        return None

    def encontrar_primario(self) -> str:
        """O primário em cache, se ainda o for; senão pergunta aos três ao mesmo tempo.

        Em paralelo, e com um *timeout* curto: perguntar um a um esperaria pelo
        nó morto antes de chegar aos vivos, e é exatamente quando há um morto
        que a resposta é urgente.
        """
        if self._primario_em_cache and self._sondar(self._primario_em_cache):
            return self._primario_em_cache
        urls = [self._url_base(no) for no in self._nos]
        with ThreadPoolExecutor(max_workers=len(urls)) as executor:
            encontrados = [url for url in executor.map(self._sondar, urls) if url]
        if not encontrados:
            self._primario_em_cache = None
            raise SemPrimario("nenhum nó se diz primário")
        self._primario_em_cache = encontrados[0]
        return self._primario_em_cache

    def reenviar(self, metodo: str, caminho: str, **kwargs) -> httpx.Response:
        """Reenvia ao primário; se ele mudou entretanto, redescobre e repete uma vez."""
        url = self.encontrar_primario()
        try:
            resposta = httpx.request(metodo, f"{url}{caminho}",
                                     timeout=self._timeout_s, **kwargs)
        except httpx.HTTPError as falha:
            logger.info("o primário %s não respondeu (%s); a redescobrir", url, falha)
            self._primario_em_cache = None
            return self._repetir(metodo, caminho, **kwargs)

        if resposta.status_code == 409 and _diz_nao_sou_primario(resposta):
            provavel = resposta.json().get("primario_provavel")
            logger.info("%s já não é primário; primário provável: %s", url, provavel)
            self._primario_em_cache = provavel
            return self._repetir(metodo, caminho, **kwargs)
        return resposta

    def _repetir(self, metodo: str, caminho: str, **kwargs) -> httpx.Response:
        url = self.encontrar_primario()
        return httpx.request(metodo, f"{url}{caminho}", timeout=self._timeout_s, **kwargs)


def _diz_nao_sou_primario(resposta: httpx.Response) -> bool:
    try:
        return resposta.json().get("erro") == "nao_sou_primario"
    except ValueError:
        return False
