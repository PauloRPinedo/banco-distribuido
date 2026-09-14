"""El balanceador propio — ver
docs/entregables/03-arquitectura/diagrama-de-componentes.md, sección
"Por qué el balanceador es un componente propio".

No es un balanceador de carga clásico (round-robin): solo el primario
acepta escrituras, así que este componente pregunta quién es el primario
ahora mismo, lo cachea, y sigue la redirección de un 409 cuando se
equivoca — exactamente lo que RF-13 ya le pide al cliente en CU-04, solo
que centralizado aquí en vez de repetido en cada cliente.

Sin estado durable: si este proceso se reinicia, vuelve a preguntar. Por
eso correr dos copias no necesita ningún protocolo de consenso.
"""

import logging

import httpx

logger = logging.getLogger("balanceador")


class Enrutador:

    def __init__(self, nodos: list[dict], url_base_fn, timeout_s: float = 2.0):
        self._nodos = nodos
        self._url_base = url_base_fn
        self._timeout_s = timeout_s
        self._primario_cacheado: str | None = None

    def _candidatos(self) -> list[str]:
        """El primario cacheado primero (si hay), luego el resto — así la
        mayoría de los pedidos no necesitan más que una llamada."""
        urls = [self._url_base(nodo) for nodo in self._nodos]
        if self._primario_cacheado and self._primario_cacheado in urls:
            urls.remove(self._primario_cacheado)
            urls.insert(0, self._primario_cacheado)
        return urls

    def cualquier_nodo_vivo(self) -> str:
        """Para lecturas: no importa cuál, todas las cuentas están en
        todos los nodos (RN-04)."""
        for url in self._candidatos():
            try:
                r = httpx.get(f"{url}/interno/estado", timeout=self._timeout_s)
                if r.status_code == 200:
                    return url
            except httpx.HTTPError:
                continue
        raise RuntimeError("sin_nodos_disponibles")

    def encontrar_primario(self) -> str:
        for url in self._candidatos():
            try:
                r = httpx.get(f"{url}/interno/estado", timeout=self._timeout_s)
                if r.status_code == 200 and r.json().get("rol") == "primario":
                    self._primario_cacheado = url
                    return url
            except httpx.HTTPError:
                continue
        raise RuntimeError("sin_primario_disponible")

    def reenviar(self, metodo: str, ruta: str, es_escritura: bool, **kwargs) -> httpx.Response:
        """Reenvía una petición. Si el nodo que creíamos primario rechaza con
        409 (`nao_sou_primario`), sigue `primario_provavel` y reintenta una
        vez — igual que ya hace el cliente en CU-04, flujo 3a."""
        url = self.encontrar_primario() if es_escritura else self.cualquier_nodo_vivo()
        respuesta = httpx.request(metodo, f"{url}{ruta}", timeout=self._timeout_s, **kwargs)

        if es_escritura and respuesta.status_code == 409:
            cuerpo = respuesta.json()
            probable = cuerpo.get("primario_provavel")
            if probable:
                logger.info("siguiendo primario_provavel=%s tras 409", probable)
                self._primario_cacheado = probable
                respuesta = httpx.request(metodo, f"{probable}{ruta}",
                                           timeout=self._timeout_s, **kwargs)
        return respuesta
