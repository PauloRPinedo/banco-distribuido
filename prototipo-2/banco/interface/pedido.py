"""O que uma rota recebe, e o que é uma rota.

Existe como módulo próprio para os três ficheiros de rotas — cliente, internas e
administração — poderem partilhar isto sem se importarem uns aos outros.

`consulta` foi acrescentada quando `/interno/log?desde=N` passou a existir: até
aí o servidor descartava a query string, e uma réplica atrasada não tinha como
dizer de onde queria o log. Um `@dataclass` em vez de mais um parâmetro solto é
o que o CODESTYLE secção 4 pede — dicionários soltos a atravessar camadas são
exatamente o que ali se proíbe.
"""

import re
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Pedido:
    """Os pedaços do caminho, o corpo já descodificado, e a query string."""

    partes: tuple = ()
    corpo: dict = field(default_factory=dict)
    consulta: dict[str, list[str]] = field(default_factory=dict)

    def inteiro(self, nome: str, por_omissao: int = 0) -> int:
        """Lê um inteiro da query string, ou devolve o valor por omissão.

        Um valor ilegível vale o mesmo que ausente: quem pergunta é outro nó, e
        para o protocolo `?desde=abc` e `?desde=` pedem ambos "manda o que
        tiveres" — recusar seria dar a um erro de escrita o poder de travar uma
        réplica que está a tentar pôr-se em dia.
        """
        valores = self.consulta.get(nome)
        if not valores:
            return por_omissao
        try:
            return int(valores[0])
        except (TypeError, ValueError):
            return por_omissao


# (método, padrão do caminho, função que atende)
Rota = tuple[str, re.Pattern, Callable]
