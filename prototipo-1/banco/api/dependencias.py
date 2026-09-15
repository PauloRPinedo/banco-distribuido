"""Uma ligação por pedido, e a transação que a acompanha.

É aqui que a atomicidade de RF-05 acontece: o débito, o crédito e o registo da
operação correm todos dentro da mesma transação, e ou confirmam juntos ou são
revertidos juntos. Não há commit em duas fases porque não é preciso — as duas
contas estão sempre no mesmo nó.
"""

from banco.repositorio import (RepositorioContas, RepositorioOperacoes,
                               obter_conexao)
from banco.servico import ServicoDeConsultas, ServicoDeEscrita


def obter_servico_de_escrita():
    conexao = obter_conexao()
    try:
        yield ServicoDeEscrita(RepositorioContas(conexao),
                               RepositorioOperacoes(conexao))
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def obter_servico_de_consultas():
    """As leituras não escrevem nada, por isso não há nada para confirmar."""
    conexao = obter_conexao()
    try:
        yield ServicoDeConsultas(RepositorioContas(conexao),
                                 RepositorioOperacoes(conexao))
    finally:
        conexao.close()
