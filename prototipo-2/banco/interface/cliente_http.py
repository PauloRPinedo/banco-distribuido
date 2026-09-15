"""Falar com um nó por HTTP.

Está separado do `cli` porque é a parte que a etapa 2 tem de estender: seguir o
`primario_provavel` de um 409, tentar o nó seguinte da lista, repetir com o mesmo
op_id. A apresentação não muda por causa disso, e não deve ter de ser tocada.
"""

import json
import urllib.error
import urllib.request

TEMPO_LIMITE = 10


class RecusaDoBanco(Exception):
    """O nó respondeu, e disse que não.

    Guarda o estado HTTP em bruto: quem chama é que decide o que fazer com ele.
    Guarda também o corpo inteiro, porque algumas recusas trazem mais do que uma
    mensagem — um `409 nao_sou_primario` traz o `primario_provavel`, e é com ele
    que o cliente encontra quem manda sem ter de tentar os nós às cegas.
    """

    def __init__(self, estado_http: int, codigo: str, mensagem: str,
                 detalhes: dict | None = None) -> None:
        super().__init__(mensagem)
        self.estado_http = estado_http
        self.codigo = codigo
        self.mensagem = mensagem
        self.detalhes = detalhes or {}


class ServidorInacessivel(Exception):
    """O nó não pôde atender.

    `respondeu` separa duas situações que parecem a mesma e não são: o processo
    estar em baixo, e o processo estar de pé mas incapaz de gravar — disco
    cheio, por exemplo. Quem está à frente do ecrã precisa de saber qual é.
    """

    def __init__(self, mensagem: str, respondeu: bool = False) -> None:
        super().__init__(mensagem)
        self.respondeu = respondeu


def normalizar(servidor: str) -> str:
    """Aceita `192.168.0.12:8001` além de `http://192.168.0.12:8001`.

    Sem isto, `urllib` levanta "unknown url type" e o CLI traduzia-o para "o
    servidor não respondeu", com o código de saída 3 — a mensagem exata que se dá
    quando o processo está em baixo. Quem escreve o IP à mão na demonstração
    passa a procurar um servidor caído que está perfeitamente vivo. É um erro de
    cinco minutos que custa meia hora no pior momento.
    """
    servidor = servidor.strip().rstrip("/")
    if "://" not in servidor:
        return "http://" + servidor
    return servidor


def pedir(servidor: str, metodo: str, caminho: str,
          corpo: dict | None = None) -> dict:
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    pedido = urllib.request.Request(
        normalizar(servidor) + caminho, data=dados, method=metodo,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE) as resposta:
            return json.loads(resposta.read())
    except urllib.error.HTTPError as falha:
        if falha.code >= 500:
            try:
                detalhe = json.loads(falha.read()).get("mensagem", "")
            except (json.JSONDecodeError, ValueError):
                detalhe = ""
            raise ServidorInacessivel(
                f"respondeu {falha.code}" + (f": {detalhe}" if detalhe else ""),
                respondeu=True) from falha
        try:
            problema = json.loads(falha.read())
        except (json.JSONDecodeError, ValueError):
            problema = {}
        raise RecusaDoBanco(falha.code,
                            problema.get("erro", "erro_desconhecido"),
                            problema.get("mensagem", str(falha)),
                            problema) from falha
    except (urllib.error.URLError, TimeoutError, ConnectionError) as falha:
        raise ServidorInacessivel(str(getattr(falha, "reason", falha))) from falha


class Ligacao:
    """Fala com o cluster sem quem chama ter de saber quem é o primário.

    Três comportamentos, todos da secção 6.1 do SPECS:

    - tenta os nós por ordem, e o que respondeu fica em primeiro na vez seguinte;
    - segue o `primario_provavel` de um `409 nao_sou_primario`;
    - repete **com o mesmo corpo**, logo com o mesmo `op_id` — é isso que torna a
      retentativa segura depois de um failover (RF-13).

    O que **não** faz é repetir indefinidamente: cada endereço é tentado uma vez
    por chamada. Um cliente que insiste sozinho durante um failover esconde o
    problema de quem está a ver a demonstração.
    """

    def __init__(self, servidores: list[str]) -> None:
        if not servidores:
            raise ValueError("a ligação precisa de pelo menos um servidor")
        self.servidores = [normalizar(s) for s in servidores]

    def __str__(self) -> str:
        return ", ".join(self.servidores)

    def pedir(self, metodo: str, caminho: str,
              corpo: dict | None = None) -> dict:
        ultima_falha: Exception | None = None
        por_tentar = list(self.servidores)
        tentados: set[str] = set()

        while por_tentar:
            servidor = por_tentar.pop(0)
            if servidor in tentados:
                continue
            tentados.add(servidor)
            try:
                resposta = pedir(servidor, metodo, caminho, corpo)
                self._promover(servidor)
                return resposta
            except RecusaDoBanco as recusa:
                seguinte = self._seguir(recusa, tentados)
                if seguinte is None:
                    # Uma recusa por regra do banco é a resposta final: não
                    # adianta perguntar a outro nó se alice tem saldo.
                    raise
                por_tentar.insert(0, seguinte)
            except ServidorInacessivel as falha:
                ultima_falha = falha

        raise ultima_falha or ServidorInacessivel(
            f"nenhum dos nós respondeu ({self})")

    def pedir_a(self, servidor: str, metodo: str, caminho: str,
                corpo: dict | None = None) -> dict:
        """Fala com **este** nó, sem seguir ninguém.

        É o que o comando `estado` precisa: durante um failover, a discordância
        entre os nós é justamente o que interessa ver, e seguir o primário
        esconde-a.
        """
        return pedir(servidor, metodo, caminho, corpo)

    def _seguir(self, recusa: RecusaDoBanco, tentados: set[str]) -> str | None:
        """O endereço a tentar a seguir, se a recusa disser qual."""
        if recusa.codigo != "nao_sou_primario":
            return None
        provavel = recusa.detalhes.get("primario_provavel")
        if not provavel:
            # A réplica não sabe quem manda — tipicamente uma eleição a decorrer.
            # Os restantes endereços da lista continuam a ser tentados.
            return None
        provavel = normalizar(provavel)
        return None if provavel in tentados else provavel

    def _promover(self, servidor: str) -> None:
        """O nó que respondeu passa a ser o primeiro a ser tentado.

        Sem isto, depois de um failover cada comando gastaria uma ida e volta a
        perguntar ao nó morto antes de acertar no vivo.
        """
        if self.servidores[0] != servidor and servidor in self.servidores:
            self.servidores.remove(servidor)
            self.servidores.insert(0, servidor)
