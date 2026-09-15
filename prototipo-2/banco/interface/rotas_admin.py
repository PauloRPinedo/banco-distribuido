"""Rotas de administração: injeção de falhas e sessão de ensaio.

Separadas das outras porque a audiência é outra vez diferente: aqui quem chama é
um operador a preparar uma experiência, não um cliente nem um nó.

Todas as falhas exigem a sessão de ensaio. A razão está em `cluster/ensaio.py`:
com dois laptops e três pessoas, dois operadores a derrubar nós ao mesmo tempo
produzem um cluster sem maioria por acidente, e o que se vê no ecrã deixa de ser
a experiência que se estava a fazer.
"""

import re
import threading

from banco.cluster.ensaio import DURACAO_POR_OMISSAO_S
from banco.cluster.no import No
from banco.dominio.erros import NaoSouPrimario, ValorInvalido
from banco.interface.pedido import Pedido, Rota

ACOES = ("tomar", "renovar", "largar")
TIPOS_DE_FALHA = ("atraso", "isolar", "derrubar", "limpar")


def ensaio(no: No, pedido: Pedido) -> tuple[int, dict]:
    """`GET` mostra quem tem a sessão; `POST` toma, renova ou larga.

    **Tomar só acontece no primário.** A sessão é um *lease* dele, e é dele que
    se propaga às réplicas pelo heartbeat. Deixar tomar numa réplica era o erro
    que tornava a exclusão inútil: dois operadores tomavam a sessão em nós
    diferentes, os dois achavam-se donos, e nenhum era recusado.

    Ler pode ser em qualquer nó: todos têm o estado propagado, e saber quem tem a
    sessão é justamente o que faz falta quando o primário está em baixo.
    """
    resposta = dict(no.ensaio.em_json())
    resposta["no"] = no.id
    if not pedido.corpo:
        return 200, resposta

    _exigir_primario(no)
    acao = str(pedido.corpo.get("acao", "")).strip()
    if acao not in ACOES:
        raise ValorInvalido(f"ação desconhecida: {acao!r}; use uma de {ACOES}")

    if acao == "tomar":
        dono = str(pedido.corpo.get("dono", "")).strip()
        if not dono:
            raise ValorInvalido("falta o 'dono': diga quem está a conduzir")
        duracao = int(pedido.corpo.get("duracao_s", DURACAO_POR_OMISSAO_S))
        fixacao = no.ensaio.tomar(dono, duracao)
        return 200, {"tomado": True, "dono": dono, "fixacao": fixacao,
                     "duracao_s": duracao}

    fixacao = str(pedido.corpo.get("fixacao", "")).strip()
    if acao == "renovar":
        return 200, {"renovado": no.ensaio.renovar(fixacao)}
    return 200, {"largado": no.ensaio.largar(fixacao)}


def _exigir_primario(no: No) -> None:
    """Encaminha para o primário, reaproveitando a recusa que o cliente já segue."""
    if no.eleicao is None or no.eleicao.sou_primario():
        return
    raise NaoSouPrimario(
        f"a sessão de ensaio toma-se no primário, e o nó {no.id} não é o "
        f"primário deste cluster", no.endereco_do_lider())


def falha(no: No, pedido: Pedido) -> tuple[int, dict]:
    """`POST /admin/falha` (F-10, RF-16).

    A verificação da sessão vem **antes** de olhar para o tipo: um operador sem
    sessão não deve sequer descobrir se o comando que escreveu era válido.
    """
    no.ensaio.verificar(str(pedido.corpo.get("fixacao", "")).strip() or None)

    tipo = str(pedido.corpo.get("tipo", "")).strip()
    if tipo not in TIPOS_DE_FALHA:
        raise ValorInvalido(
            f"falha desconhecida: {tipo!r}; use uma de {TIPOS_DE_FALHA}")

    if tipo == "atraso":
        no.falhas.atraso(int(pedido.corpo.get("ms", 0)))
    elif tipo == "isolar":
        no.falhas.isolar(list(pedido.corpo.get("de", [])))
    elif tipo == "limpar":
        no.falhas.limpar()
    else:
        # Responder primeiro e morrer depois. Ao contrário, quem pediu leria a
        # ligação cortada como "não consegui falar com o nó" e ficaria sem saber
        # se a ordem chegou a ser executada.
        threading.Timer(0.1, no.falhas.derrubar).start()
        return 200, {"tipo": "derrubar", "no": no.id, "adeus": True}

    no.ensaio.renovar(str(pedido.corpo.get("fixacao", "")).strip())
    return 200, {"tipo": tipo, "no": no.id, "falhas": no.falhas.em_json()}


ROTAS: list[Rota] = [
    ("GET", re.compile(r"^/admin/ensaio$"), ensaio),
    ("POST", re.compile(r"^/admin/ensaio$"), ensaio),
    ("POST", re.compile(r"^/admin/falha$"), falha),
]
