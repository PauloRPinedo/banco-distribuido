"""O que cada comando do CLI faz.

Separado de `cli.py` para nenhum dos dois passar das 250 linhas que o CODESTYLE
marca como sinal de um módulo a fazer duas coisas: aqui está o **que** cada
comando mostra, ali está como os argumentos se leem e como os erros se traduzem.

Nenhuma função aqui sabe qual é o nó primário: falam com uma `Ligacao`, que
segue o `primario_provavel` sozinha (SPECS 6.1).
"""

import sys
import uuid

from banco.interface.cliente_http import RecusaDoBanco, ServidorInacessivel
from banco.interface.formato import dinheiro, erro, tabela

OK = 0
RECUSADO = 1
USO_INCORRETO = 2
SEM_SERVIDOR = 3


def _op_id() -> str:
    """Gerado no cliente, e não no servidor.

    É o que torna a retentativa segura: repetir depois de uma resposta perdida
    devolve o resultado guardado em vez de mover o dinheiro outra vez (RF-13).
    """
    return uuid.uuid4().hex


def criar_conta(opcoes) -> int:
    resposta = opcoes.ligacao.pedir("POST", "/contas",
                     {"conta": opcoes.conta, "saldo_inicial": opcoes.saldo,
                      "op_id": _op_id()})
    print(f"  conta {resposta['conta']} criada com "
          f"{dinheiro(resposta['saldo_centavos'])}")
    return OK


def consultar_saldo(opcoes) -> int:
    resposta = opcoes.ligacao.pedir("GET", f"/contas/{opcoes.conta}")
    print(f"  {resposta['conta']}   {dinheiro(resposta['saldo_centavos'])}")
    return OK


def depositar(opcoes) -> int:
    return _movimentar(opcoes, f"/contas/{opcoes.conta}/deposito", "depositado")


def sacar(opcoes) -> int:
    return _movimentar(opcoes, f"/contas/{opcoes.conta}/saque", "sacado")


def _movimentar(opcoes, caminho: str, verbo: str) -> int:
    resposta = opcoes.ligacao.pedir("POST", caminho,
                     {"valor": opcoes.valor, "op_id": _op_id()})
    print(f"  {verbo} · {resposta['conta']} fica com "
          f"{dinheiro(resposta['saldo_centavos'])}")
    return OK


def transferir(opcoes) -> int:
    resposta = opcoes.ligacao.pedir("POST", "/transferencias",
                     {"de": opcoes.de, "para": opcoes.para,
                      "valor": opcoes.valor, "op_id": _op_id()})
    saldos = resposta["saldos_centavos"]
    print(tabela(["conta", "saldo"],
                 [[opcoes.de, dinheiro(saldos[opcoes.de])],
                  [opcoes.para, dinheiro(saldos[opcoes.para])]],
                 a_direita={1}))
    return OK


def extrato(opcoes) -> int:
    resposta = opcoes.ligacao.pedir("GET", f"/contas/{opcoes.conta}/extrato")
    movimentos = resposta["movimentos"]
    if not movimentos:
        print(f"  {opcoes.conta} não tem movimentos")
        return OK
    linhas = [[m["indice"], m["tipo"], m["contraparte"] or "—",
               dinheiro(m["valor_centavos"]),
               dinheiro(m["saldo_depois_centavos"])] for m in movimentos]
    print(tabela(["#", "operação", "contraparte", "valor", "saldo"], linhas,
                 a_direita={0, 3, 4}))
    return OK


def auditoria(opcoes) -> int:
    resposta = opcoes.ligacao.pedir("GET", "/auditoria")
    print(f"  total em circulação   {dinheiro(resposta['total_centavos'])}")
    print(f"  esperado pelo log     {dinheiro(resposta['total_esperado_centavos'])}")
    print(f"  contas {resposta['contas']} · operações {resposta['operacoes']}")
    if resposta["divergente"]:
        # Não pode acontecer. Se acontecer, é o achado mais importante do
        # projeto e não pode passar despercebido numa linha de tabela.
        print()
        print(erro("a auditoria diverge",
                   f"os saldos somam {dinheiro(resposta['divergencia_centavos'])} "
                   "a mais do que o log explica",
                   "guarde o wal.jsonl antes de mexer em mais nada"),
              file=sys.stderr)
        return RECUSADO
    return OK


def estado(opcoes) -> int:
    """Uma linha por nó, no formato da secção 9.2 do CODESTYLE.

    Pergunta a **cada** nó em vez de perguntar a um só: durante um failover é
    justamente a discordância entre eles que interessa ver. Um nó que não
    responde aparece na tabela como "sem contacto" — omiti-lo daria a ideia de
    que o cluster é mais pequeno do que é.
    """
    linhas = []
    atrasos = {}
    for servidor in opcoes.ligacao.servidores:
        try:
            resposta = opcoes.ligacao.pedir_a(servidor, "GET", "/interno/estado")
        except (RecusaDoBanco, ServidorInacessivel):
            linhas.append([servidor, "sem contacto", "—", "—", "—", "—"])
            continue
        atrasos[resposta["no"]] = resposta["ultimo_indice"]
        linhas.append([resposta["no"], resposta["papel"], resposta["epoch"],
                       resposta["ultimo_indice"], resposta["indice_commit"],
                       resposta["contas"]])

    if not atrasos:
        print(erro("nenhum nó respondeu",
                   f"tentei {opcoes.ligacao}",
                   "confirme que estão a correr: "
                   "./scripts/verificar_rede.sh config/cluster.json"),
              file=sys.stderr)
        return SEM_SERVIDOR

    # "2 atrás" diz o tamanho do problema; uma luz amarela só diz que existe um.
    a_frente = max(atrasos.values())
    for linha in linhas:
        indice = atrasos.get(linha[0])
        if indice is not None and a_frente - indice > 0:
            linha[1] = f"{linha[1]} · {a_frente - indice} atrás"

    print(tabela(["nó", "papel", "epoch", "índice", "commit", "contas"],
                 linhas, a_direita={2, 3, 4, 5}))
    return OK


# ----------------------------------------------------------------- ensaio

def _ficheiro_da_fixacao():
    """Onde a prova de posse da sessão fica guardada, por laptop.

    Em `~`, e não na pasta do projeto: é estado do operador, não do repositório,
    e dois operadores que partilhem o mesmo clone continuam a ter sessões
    distintas.
    """
    from pathlib import Path
    return Path.home() / ".banco_ensaio"


def _guardar_fixacao(fixacao: str) -> None:
    _ficheiro_da_fixacao().write_text(fixacao, encoding="utf-8")


def _ler_fixacao() -> str:
    caminho = _ficheiro_da_fixacao()
    return caminho.read_text(encoding="utf-8").strip() if caminho.exists() else ""


def ensaio(opcoes) -> int:
    if opcoes.acao == "estado":
        resposta = opcoes.ligacao.pedir("GET", "/admin/ensaio")
        if not resposta.get("tomado"):
            print(f"  a sessão de ensaio está livre · segundo o nó {resposta['no']}")
        else:
            print(f"  {resposta['dono']} tem a sessão · "
                  f"expira em {round(resposta['falta_s'])} s · "
                  f"segundo o nó {resposta['no']}")
        return OK

    if opcoes.acao == "tomar":
        resposta = opcoes.ligacao.pedir(
            "POST", "/admin/ensaio",
            {"acao": "tomar", "dono": opcoes.dono, "duracao_s": opcoes.duracao})
        _guardar_fixacao(resposta["fixacao"])
        print(f"  sessão de ensaio tomada por {resposta['dono']} · "
              f"{resposta['duracao_s']} s")
        return OK

    resposta = opcoes.ligacao.pedir("POST", "/admin/ensaio",
                                    {"acao": "largar", "fixacao": _ler_fixacao()})
    if not resposta.get("largado"):
        print(erro("a sessão não era sua",
                   "a fixação guardada neste computador não corresponde",
                   "veja quem a tem: python3 -m banco.cli ensaio estado"),
              file=sys.stderr)
        return RECUSADO
    print("  sessão de ensaio largada")
    return OK


def falha(opcoes) -> int:
    """Injeta uma falha **num nó concreto**, não no cluster.

    Por isso fala diretamente com o endereço, sem seguir o primário: derrubar
    "o primário" quando se queria derrubar o nó C seria o oposto de uma
    experiência controlada.
    """
    corpo = {"tipo": opcoes.tipo, "fixacao": _ler_fixacao()}
    if opcoes.tipo == "atraso":
        corpo["ms"] = opcoes.ms
    if opcoes.tipo == "isolar":
        corpo["de"] = [parte.strip() for parte in opcoes.de.split(",")
                       if parte.strip()]

    alvo = _endereco_do_alvo(opcoes)
    try:
        resposta = opcoes.ligacao.pedir_a(alvo, "POST", "/admin/falha", corpo)
    except ServidorInacessivel:
        if opcoes.tipo == "derrubar":
            # Derrubar um nó já morto é o resultado que se queria.
            print(f"  o nó em {alvo} já não responde")
            return OK
        raise

    if opcoes.tipo == "derrubar":
        print(f"  nó {resposta['no']} derrubado")
    else:
        print(f"  nó {resposta['no']} · {resposta['falhas']}")
    return OK


def _endereco_do_alvo(opcoes) -> str:
    """O endereço do nó indicado por `--no`, lido do ficheiro do cluster."""
    import json
    from pathlib import Path

    from banco.interface.cliente_http import normalizar

    if not opcoes.cluster:
        return opcoes.ligacao.servidores[0]
    bruto = json.loads(Path(opcoes.cluster).read_text(encoding="utf-8"))
    for no in bruto["nos"]:
        if no["id"] == opcoes.no:
            return normalizar(f"{no['endereco']}:{no['porta']}")
    conhecidos = ", ".join(no["id"] for no in bruto["nos"])
    raise SystemExit(f"  erro: o nó {opcoes.no!r} não está no cluster\n"
                     f"  conhecidos: {conhecidos}\n"
                     f"  → confira o ficheiro {opcoes.cluster}")
