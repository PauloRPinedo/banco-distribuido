"""O nó deste processo, e os serviços que falam com ele e com a base.

O `No` é um só por processo: guarda o papel, o epoch, o log e a ligação aos
pares. Cria-se no arranque da aplicação (`app.py`), e não ao importar este
módulo, para que importar a API não exija uma base de dados.

Com `CLUSTER_CONFIG` a apontar para o ficheiro do cluster, o nó é um de três e
arranca como réplica. Sem ele, é um banco de um nó só, que manda sempre — é o
modo dos testes que não estudam o cluster.
"""

import os
import threading
from contextlib import contextmanager
from pathlib import Path

from banco.cluster import No
from banco.cluster.armazem_postgres import ArmazemPostgres
from banco.cluster.configuracao import ConfiguracaoDoCluster
from banco.integracoes import GatewayExternoFalso, GatewayExternoSimulado
from banco.repositorio import (RepositorioContas, RepositorioOperacoes,
                               RepositorioSistemasExternos,
                               RepositorioTaxaCambio, RepositorioUsuarios,
                               obter_conexao)
from banco.servico import (AplicadorPostgres, ServicoAutenticacao,
                           ServicoDeConsultas, ServicoDeEscrita)

_lock = threading.Lock()
_no: No | None = None


def no_do_processo() -> No:
    global _no
    with _lock:
        if _no is None:
            _no = _criar_no()
        return _no


def fechar_no_do_processo() -> None:
    """Para o nó e esquece-o: o próximo arranque da aplicação cria outro."""
    global _no
    with _lock:
        if _no is not None:
            _no.fechar()
            _no = None


def _criar_no() -> No:
    no_id = os.environ.get("NO_ID", "A")
    caminho = os.environ.get("CLUSTER_CONFIG")
    configuracao = ConfiguracaoDoCluster.de_ficheiro(Path(caminho)) if caminho else None
    return No(no_id, ArmazemPostgres(no_id, obter_conexao()),
              AplicadorPostgres(no_id, obter_conexao), configuracao)


@contextmanager
def servico_de_escrita():
    """Para as rotas que fazem mais do que uma escrita (externa, juros)."""
    yield ServicoDeEscrita(no_do_processo(), obter_conexao)


def obter_servico_de_escrita():
    yield ServicoDeEscrita(no_do_processo(), obter_conexao)


def obter_servico_de_autenticacao():
    conexao = obter_conexao()
    try:
        yield ServicoAutenticacao(RepositorioUsuarios(conexao),
                                  ServicoDeEscrita(no_do_processo(), obter_conexao))
    finally:
        conexao.close()


def obter_servico_de_consultas():
    """As leituras não escrevem nada, por isso não há nada para confirmar."""
    conexao = obter_conexao()
    try:
        yield ServicoDeConsultas(RepositorioContas(conexao),
                                 RepositorioOperacoes(conexao),
                                 RepositorioTaxaCambio(conexao),
                                 RepositorioSistemasExternos(conexao))
    finally:
        conexao.close()


def obter_gateway():
    """O outro banco. `BANCO_GATEWAY=confirma` ou `rejeita` torna-o determinista.

    Lido a cada pedido, e não no arranque, para os testes poderem trocar de
    resposta sem reiniciar o servidor.
    """
    escolha = os.environ.get("BANCO_GATEWAY", "simulado")
    if escolha == "confirma":
        return GatewayExternoFalso(confirmar_sempre=True)
    if escolha == "rejeita":
        return GatewayExternoFalso(confirmar_sempre=False)
    return GatewayExternoSimulado()
