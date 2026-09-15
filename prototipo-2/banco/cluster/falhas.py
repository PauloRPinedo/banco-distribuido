"""Provocar falhas de propósito, para as experiências serem repetíveis (F-10, RF-16).

Até aqui, provocar uma falha era matar um processo à mão. Isso chega para
demonstrar, mas não para **testar**: uma partição de rede feita com a firewall
não cabe num teste automático, e um `kill` num laptop não se repete igual no
outro.

Três falhas, e nada mais:

- `atraso` — responder devagar. É o primário lento, que é o caso que justifica a
  eleição por voto em vez de por posição na lista.
- `isolar` — descartar mensagens de nós indicados, nos dois sentidos. Reproduz uma
  partição sem tocar na firewall.
- `derrubar` — morrer já, sem fechar nada.

`derrubar` usa `os._exit` e não `sys.exit` de propósito: `sys.exit` levanta uma
exceção, corre os `finally`, fecha o servidor e a ligação à base com educação. O
que se quer demonstrar é uma queda **abrupta** — se o nó se despedir, o cenário
que se diz estar a testar não é o que está a acontecer.
"""

import os
import threading
import time


class InjetorDeFalhas:

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._atraso_ms = 0
        self._isolado_de: set[str] = set()

    # ------------------------------------------------------------- comandos

    def atraso(self, ms: int) -> None:
        with self._lock:
            self._atraso_ms = max(0, int(ms))

    def isolar(self, ids: list[str]) -> None:
        with self._lock:
            self._isolado_de = {str(i) for i in ids}

    def limpar(self) -> None:
        with self._lock:
            self._atraso_ms = 0
            self._isolado_de = set()

    def derrubar(self) -> None:
        """Morre já. Não devolve."""
        os._exit(1)

    # -------------------------------------------------------- efeitos

    def talvez_atrasar(self) -> None:
        with self._lock:
            atraso = self._atraso_ms
        if atraso:
            time.sleep(atraso / 1000)

    def fala_com(self, id_do_no: str) -> bool:
        """Falso se este nó está isolado daquele.

        Aplica-se **nos dois sentidos**: quem envia não envia, e quem recebe
        descarta. Uma partição de mentira que só corta um lado produz um cenário
        que a rede real não produz, e conclusões que não valem nada.
        """
        with self._lock:
            return id_do_no not in self._isolado_de

    def em_json(self) -> dict:
        with self._lock:
            return {"atraso_ms": self._atraso_ms,
                    "isolado_de": sorted(self._isolado_de)}
