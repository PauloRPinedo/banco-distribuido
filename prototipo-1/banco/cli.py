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
import json
import sys
from pathlib import Path

from banco.comandos import (RECUSADO, SEM_SERVIDOR, USO_INCORRETO,
                            auditoria, consultar_saldo, criar_conta, depositar,
                            ensaio, estado, extrato, falha, sacar, transferir)
from banco.interface.cliente_http import (Ligacao, RecusaDoBanco,
                                          ServidorInacessivel)
from banco.interface.formato import erro

SERVIDOR_POR_OMISSAO = "http://127.0.0.1:8001"

# O código do erro é para máquinas; o título é para quem está a ler o ecrã.
TITULOS = {
    "conta_inexistente": "essa conta não existe",
    "conta_duplicada": "essa conta já existe",
    "saldo_insuficiente": "saldo insuficiente",
    "valor_invalido": "valor inválido",
    "rota_inexistente": "o servidor não conhece esse pedido",
    "ensaio_tomado": "a sessão de ensaio está tomada",
    "particao_simulada": "esse nó está isolado por uma falha injetada",
    "nao_sou_primario": "esse nó não é o primário",
    "sem_quorum": "a maioria do cluster não confirmou",
    "somente_leitura": "o cluster está em somente leitura",
    "armazem_indisponivel": "o servidor não conseguiu gravar",
}

SUGESTOES = {
    "conta_inexistente": "crie a conta primeiro: python3 -m banco.cli "
                         "criar-conta <id> --saldo 0",
    "conta_duplicada": "escolha outro id, ou consulte a conta com: "
                       "python3 -m banco.cli saldo <id>",
    "saldo_insuficiente": "consulte o saldo com: python3 -m banco.cli saldo <id>",
    "valor_invalido": "escreva o valor com duas casas decimais, como 25.00",
    "rota_inexistente": "confirme que o servidor é da mesma etapa do cliente",
    "nao_sou_primario": "use --cluster config/cluster.json e o cliente "
                        "encontra o primário sozinho",
    "sem_quorum": "veja quantos nós estão de pé: python3 -m banco.cli estado",
    "somente_leitura": "arranque os nós em falta: python3 -m banco.cli estado",
    "armazem_indisponivel": "veja o terminal do servidor; com a base em baixo, "
                            "repita o comando quando ela voltar",
    "ensaio_tomado": "espere, ou peça-lhe: python3 -m banco.cli ensaio largar",
    "particao_simulada": "limpe a falha injetada: "
                         "python3 -m banco.cli falha limpar --no <id>",
}


def _servidores(opcoes) -> list[str]:
    """De onde sai a lista de nós a tentar.

    `--cluster` ganha a `--servidor`: quem passou um ficheiro de cluster quer
    falar com o cluster, não com um nó em particular.
    """
    if not opcoes.cluster:
        return [opcoes.servidor]
    caminho = Path(opcoes.cluster)
    if not caminho.exists():
        raise SystemExit(
            f"  erro: não existe {caminho}\n"
            f"  o ficheiro do cluster é local a cada máquina\n"
            f"  → copie o exemplo: cp config/cluster.exemplo.json {caminho}")
    bruto = json.loads(caminho.read_text(encoding="utf-8"))
    return [f"http://{no['endereco']}:{no['porta']}" for no in bruto["nos"]]


def _op_id() -> str:
    """Gerado no cliente, e não no servidor.

    É o que torna a retentativa segura: repetir depois de uma resposta perdida
    devolve o resultado guardado em vez de mover o dinheiro outra vez (RF-13).
    """
    return uuid.uuid4().hex


# ------------------------------------------------------------------- entrada

def analisar(argumentos: list[str] | None = None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(
        prog="banco.cli", description="Cliente do banco distribuído.")
    analisador.add_argument("--servidor", default=SERVIDOR_POR_OMISSAO,
                            help=f"por omissão: {SERVIDOR_POR_OMISSAO}")
    analisador.add_argument("--cluster",
                            help="ficheiro do cluster; o cliente encontra o "
                                 "primário sozinho")
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
    comandos.add_parser("estado",
                        help="estado de cada nó").set_defaults(funcao=estado)

    sessao = comandos.add_parser(
        "ensaio", help="sessão exclusiva para injetar falhas")
    sessao.add_argument("acao", choices=["tomar", "largar", "estado"])
    sessao.add_argument("--dono", default="", help="quem está a conduzir")
    sessao.add_argument("--duracao", type=int, default=300,
                        help="segundos até caducar (por omissão: 300)")
    sessao.set_defaults(funcao=ensaio)

    injecao = comandos.add_parser("falha", help="injeta uma falha num nó")
    injecao.add_argument("tipo",
                         choices=["derrubar", "isolar", "atraso", "limpar"])
    injecao.add_argument("--no", default="A", help="o nó alvo")
    injecao.add_argument("--de", default="",
                         help="ids de quem isolar, separados por vírgula")
    injecao.add_argument("--ms", type=int, default=0, help="atraso, em ms")
    injecao.set_defaults(funcao=falha)

    return analisador.parse_args(argumentos)


def main(argumentos: list[str] | None = None) -> int:
    opcoes = analisar(argumentos)
    opcoes.ligacao = Ligacao(_servidores(opcoes))
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
                       f"{opcoes.ligacao} {falha}",
                       "veja o terminal do servidor: o rasto do erro está lá"),
                  file=sys.stderr)
        else:
            print(erro("o servidor não respondeu",
                       f"não foi possível falar com {opcoes.ligacao} ({falha})",
                       "confirme que está a correr: "
                       "python3 -m banco.servidor --id A --porta 8001"),
                  file=sys.stderr)
        return SEM_SERVIDOR


if __name__ == "__main__":
    sys.exit(main())
