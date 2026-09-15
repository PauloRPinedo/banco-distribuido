"""A vista do cluster inteiro, para quem o quer ver de fora (F-11).

Existe separada da replicação por duas razões, e a segunda é de correção:

- **é um caminho de leitura.** `replicacao.py` trata do que faz o dinheiro
  mover-se; isto só responde a "como está o cluster?". Misturá-los fazia esse
  módulo passar das ~250 linhas a partir das quais um módulo costuma estar a
  fazer duas coisas.
- **não pode roubar trabalhadores à replicação.** O frontend pergunta uma vez por
  segundo, e se essas chamadas entrassem no mesmo `ThreadPoolExecutor` de dois
  lugares que envia os heartbeats, uma página aberta podia atrasar o batimento —
  e um heartbeat atrasado derruba um primário saudável.
"""

from concurrent.futures import ThreadPoolExecutor

from banco.cluster.configuracao import ConfiguracaoDoCluster, NoDoCluster
from banco.interface.cliente_interno import pedir_ao_no


def ver_cluster(id_do_no: str, configuracao: ConfiguracaoDoCluster | None,
                estado_proprio: dict, falhas=None) -> dict:
    """O que **este** nó sabe sobre todos os nós.

    O campo `eu` diz quem respondeu: a resposta é sempre uma opinião, e
    apresentá-la como verdade absoluta seria mentir. Um par calado aparece com
    `vivo: False` em vez de desaparecer — durante um failover é justamente o nó
    em falta que interessa ver.
    """
    meu = dict(estado_proprio, vivo=True)
    if configuracao is None:
        return {"eu": id_do_no, "maioria": 1, "nos": [meu]}

    eu = configuracao.obter(id_do_no)
    meu["endereco"] = f"{eu.endereco}:{eu.porta}"
    pares = _perguntar_aos_pares(configuracao.pares_de(id_do_no),
                                 configuracao.timeout_replicacao_ms, falhas)

    # Pela ordem do ficheiro de configuração, e não pela ordem de resposta: se os
    # cartões trocassem de sítio a cada segundo, ninguém conseguiria ler a tabela
    # durante um failover.
    por_id = {estado["no"]: estado for estado in [meu, *pares]}
    return {"eu": id_do_no,
            "maioria": configuracao.maioria,
            "nos": [por_id[no.id] for no in configuracao.nos if no.id in por_id]}


def _perguntar_aos_pares(pares: tuple, prazo_ms: int, falhas) -> list[dict]:
    if not pares:
        return []
    # Executor próprio e de vida curta: nasce e morre com o pedido, e nunca
    # compete com a replicação por trabalhadores.
    with ThreadPoolExecutor(max_workers=len(pares),
                            thread_name_prefix="vista") as executor:
        futuros = [(par, executor.submit(_perguntar, par, prazo_ms, falhas))
                   for par in pares]
        estados = []
        for par, futuro in futuros:
            try:
                estados.append(futuro.result(timeout=prazo_ms / 1000 + 0.5))
            except Exception as falha:  # noqa: BLE001
                estados.append(sem_contacto(par, str(falha)))
        return estados


def _perguntar(par: NoDoCluster, prazo_ms: int, falhas) -> dict:
    """O estado de um par. Respeita o isolamento injetado."""
    if falhas is not None and not falhas.fala_com(par.id):
        return sem_contacto(par, "isolado por falha injetada")
    resposta = pedir_ao_no(par, "/interno/estado", None, prazo_ms, metodo="GET")
    if not resposta or not resposta.corpo:
        return sem_contacto(par, resposta.motivo or "sem resposta")
    return {**resposta.corpo, "endereco": f"{par.endereco}:{par.porta}",
            "vivo": True}


def sem_contacto(par: NoDoCluster, motivo: str) -> dict:
    return {"no": par.id, "endereco": f"{par.endereco}:{par.porta}",
            "vivo": False, "motivo": motivo}
