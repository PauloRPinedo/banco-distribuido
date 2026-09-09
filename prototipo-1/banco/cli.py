"""Cliente de linha de comando do banco (F-12, RF-17).

    python3 -m banco.cli criar-conta alice --saldo 100.00
    python3 -m banco.cli transferir alice bob 25.00
    python3 -m banco.cli auditoria

Códigos de saída, conforme a secção 9.5 de docs/CODESTYLE.md:

    0  correu bem
    1  o banco recusou por regra (saldo insuficiente, conta inexistente)
    2  uso incorreto do comando
    3  o servidor não respondeu

O 1 e o 3 têm de ser distintos: os testes precisam de separar "o banco disse não,
e bem" de "o banco está em baixo". Colapsá-los faz um teste de falha passar pelo
motivo errado.
"""

import argparse
import sys
import uuid

from banco.interface.cliente_http import (RecusaDoBanco, ServidorInacessivel,
                                          pedir)
from banco.interface.formato import dinheiro, erro, tabela

SERVIDOR_POR_OMISSAO = "http://127.0.0.1:8001"

OK = 0
RECUSADO = 1
USO_INCORRETO = 2
SEM_SERVIDOR = 3

# O código do erro é para máquinas; o título é para quem está a ler o ecrã.
TITULOS = {
    "conta_inexistente": "essa conta não existe",
    "conta_duplicada": "essa conta já existe",
    "saldo_insuficiente": "saldo insuficiente",
    "valor_invalido": "valor inválido",
    "rota_inexistente": "o servidor não conhece esse pedido",
}

SUGESTOES = {
    "conta_inexistente": "crie a conta primeiro: python3 -m banco.cli "
                         "criar-conta <id> --saldo 0",
    "conta_duplicada": "escolha outro id, ou consulte a conta com: "
                       "python3 -m banco.cli saldo <id>",
    "saldo_insuficiente": "consulte o saldo com: python3 -m banco.cli saldo <id>",
    "valor_invalido": "escreva o valor com duas casas decimais, como 25.00",
    "rota_inexistente": "confirme que o servidor é da mesma etapa do cliente",
}


def _op_id() -> str:
    """Gerado no cliente, e não no servidor.

    É o que torna a retentativa segura: repetir depois de uma resposta perdida
    devolve o resultado guardado em vez de mover o dinheiro outra vez (RF-13).
    """
    return uuid.uuid4().hex


# ----------------------------------------------------------------- comandos

def criar_conta(opcoes) -> int:
    resposta = pedir(opcoes.servidor, "POST", "/contas",
                     {"conta": opcoes.conta, "saldo_inicial": opcoes.saldo,
                      "op_id": _op_id()})
    print(f"  conta {resposta['conta']} criada com "
          f"{dinheiro(resposta['saldo_centavos'])}")
    return OK


def consultar_saldo(opcoes) -> int:
    resposta = pedir(opcoes.servidor, "GET", f"/contas/{opcoes.conta}")
    print(f"  {resposta['conta']}   {dinheiro(resposta['saldo_centavos'])}")
    return OK


def depositar(opcoes) -> int:
    return _movimentar(opcoes, f"/contas/{opcoes.conta}/deposito", "depositado")


def sacar(opcoes) -> int:
    return _movimentar(opcoes, f"/contas/{opcoes.conta}/saque", "sacado")


def _movimentar(opcoes, caminho: str, verbo: str) -> int:
    resposta = pedir(opcoes.servidor, "POST", caminho,
                     {"valor": opcoes.valor, "op_id": _op_id()})
    print(f"  {verbo} · {resposta['conta']} fica com "
          f"{dinheiro(resposta['saldo_centavos'])}")
    return OK


def transferir(opcoes) -> int:
    resposta = pedir(opcoes.servidor, "POST", "/transferencias",
                     {"de": opcoes.de, "para": opcoes.para,
                      "valor": opcoes.valor, "op_id": _op_id()})
    saldos = resposta["saldos_centavos"]
    print(tabela(["conta", "saldo"],
                 [[opcoes.de, dinheiro(saldos[opcoes.de])],
                  [opcoes.para, dinheiro(saldos[opcoes.para])]],
                 a_direita={1}))
    return OK


def extrato(opcoes) -> int:
    resposta = pedir(opcoes.servidor, "GET", f"/contas/{opcoes.conta}/extrato")
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
    resposta = pedir(opcoes.servidor, "GET", "/auditoria")
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
    resposta = pedir(opcoes.servidor, "GET", "/interno/estado")
    print(tabela(["nó", "papel", "epoch", "índice", "commit", "contas"],
                 [[resposta["no"], resposta["papel"], resposta["epoch"],
                   resposta["ultimo_indice"], resposta["indice_commit"],
                   resposta["contas"]]],
                 a_direita={2, 3, 4, 5}))
    return OK


# ------------------------------------------------------------------- entrada

def analisar(argumentos: list[str] | None = None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(
        prog="banco.cli", description="Cliente do banco distribuído.")
    analisador.add_argument("--servidor", default=SERVIDOR_POR_OMISSAO,
                            help=f"por omissão: {SERVIDOR_POR_OMISSAO}")
    comandos = analisador.add_subparsers(dest="comando", required=True)

    criar = comandos.add_parser("criar-conta", help="cria uma conta")
    criar.add_argument("conta")
    criar.add_argument("--saldo", default="0", help="saldo inicial, como 100.00")
    criar.set_defaults(funcao=criar_conta)

    ver = comandos.add_parser("saldo", help="consulta o saldo de uma conta")
    ver.add_argument("conta")
    ver.set_defaults(funcao=consultar_saldo)

    for nome, funcao, ajuda in (("depositar", depositar, "deposita numa conta"),
                                ("sacar", sacar, "saca de uma conta")):
        movimento = comandos.add_parser(nome, help=ajuda)
        movimento.add_argument("conta")
        movimento.add_argument("valor")
        movimento.set_defaults(funcao=funcao)

    transferencia = comandos.add_parser("transferir", help="transfere entre contas")
    transferencia.add_argument("de")
    transferencia.add_argument("para")
    transferencia.add_argument("valor")
    transferencia.set_defaults(funcao=transferir)

    historico = comandos.add_parser("extrato", help="movimentos de uma conta")
    historico.add_argument("conta")
    historico.set_defaults(funcao=extrato)

    comandos.add_parser("auditoria",
                        help="soma os saldos e compara com o log"
                        ).set_defaults(funcao=auditoria)
    comandos.add_parser("estado", help="estado do nó").set_defaults(funcao=estado)

    return analisador.parse_args(argumentos)


def main(argumentos: list[str] | None = None) -> int:
    opcoes = analisar(argumentos)
    try:
        return opcoes.funcao(opcoes)
    except RecusaDoBanco as recusa:
        titulo = TITULOS.get(recusa.codigo, recusa.codigo.replace("_", " "))
        # 400 é uma ordem mal escrita por quem chama; 404, 409 e 422 são o banco
        # a aplicar uma regra sua. Para quem automatiza, são casos diferentes.
        saida = USO_INCORRETO if recusa.estado_http == 400 else RECUSADO
        sugestao = SUGESTOES.get(recusa.codigo,
                                 "consulte o estado: python3 -m banco.cli estado")
        print(erro(titulo, recusa.mensagem, sugestao), file=sys.stderr)
        return saida
    except ServidorInacessivel as falha:
        if falha.respondeu:
            print(erro("o servidor não conseguiu atender",
                       f"{opcoes.servidor} {falha}",
                       "veja o terminal do servidor: o rasto do erro está lá"),
                  file=sys.stderr)
        else:
            print(erro("o servidor não respondeu",
                       f"não foi possível falar com {opcoes.servidor} ({falha})",
                       "confirme que está a correr: "
                       "python3 -m banco.servidor --id A --porta 8001"),
                  file=sys.stderr)
        return SEM_SERVIDOR


if __name__ == "__main__":
    sys.exit(main())
