"""Aplicar uma entrada confirmada do log às tabelas deste nó.

É a mesma função no primário e nas réplicas, e é por isso que três nós com o
mesmo log confirmado têm as mesmas tabelas. Cada entrada aplica-se numa
transação, que avança também `estado_do_no.ultimo_aplicado`: se o processo
cair a meio, ou a entrada ficou toda aplicada e o ponteiro avançou, ou nada
aconteceu e ela volta a ser aplicada no arranque.

O dinheiro entra pelo destino e sai pela origem (ver `_colunas`). É essa
assimetria que faz a auditoria somar certo sem conhecer as operações uma a uma.
"""

import logging

from banco.cluster.entrada import EntradaDeLog
from banco.cluster.operacoes_de_sistema import (Noop, RegistarTaxa,
                                                RegistarUsuario)
from banco.dominio.contas import Livro
from banco.dominio.erros import ErroDoBanco
from banco.dominio.operacoes import (Cambio, CriarConta, Deposito,
                                     DesfechoExterno, Juros, Operacao, Saque,
                                     Transferencia, TransferenciaExterna)
from banco.repositorio import (RepositorioContas, RepositorioOperacoes,
                               RepositorioTaxaCambio, RepositorioUsuarios)

registo = logging.getLogger("banco.aplicador")


def _colunas(operacao: Operacao, resposta: dict) -> dict:
    """O que esta operação escreve nas colunas da tabela `operacao`.

    O dinheiro entra pelo destino e sai pela origem. É essa assimetria que faz a
    auditoria somar certo sem conhecer as operações uma a uma: criar conta,
    depósito, juros e devolução externa só têm destino; saque e transferência
    externa só têm origem; transferência e câmbio têm as duas.
    """
    if isinstance(operacao, CriarConta):
        return {"destino": operacao.conta, "valor_centavos": operacao.saldo_inicial_centavos}
    if isinstance(operacao, Deposito):
        return {"destino": operacao.conta, "valor_centavos": operacao.valor_centavos}
    if isinstance(operacao, Saque):
        return {"origem": operacao.conta, "valor_centavos": operacao.valor_centavos}
    if isinstance(operacao, Transferencia):
        return {"origem": operacao.de, "destino": operacao.para,
                "valor_centavos": operacao.valor_centavos}
    if isinstance(operacao, Cambio):
        return {"origem": operacao.de, "destino": operacao.para,
                "valor_centavos": operacao.valor_centavos,
                "moeda_origem": resposta["moedas"][operacao.de],
                "moeda_destino": resposta["moedas"][operacao.para],
                "taxa_milionesimos": operacao.taxa_milionesimos,
                "valor_destino_centavos": resposta["valor_destino_centavos"]}
    if isinstance(operacao, Juros):
        return {"destino": operacao.conta, "valor_centavos": resposta["juros_centavos"]}
    if isinstance(operacao, TransferenciaExterna):
        return {"origem": operacao.de, "valor_centavos": operacao.valor_centavos,
                "sistema_externo_id": operacao.sistema_externo_id}
    if isinstance(operacao, DesfechoExterno):
        # Confirmada não devolve nada: o valor na tabela é o que voltou a entrar.
        return {"destino": operacao.conta,
                "valor_centavos": operacao.devolvido_centavos(),
                "referencia_externa": operacao.referencia_externa}
    raise TypeError(f"operação sem lugar na tabela: {type(operacao).__name__}")


class AplicadorPostgres:

    def __init__(self, no_id: str, obter_conexao) -> None:
        self.no_id = no_id
        self._obter_conexao = obter_conexao

    def ultimo_aplicado(self) -> int:
        conexao = self._obter_conexao()
        try:
            with conexao.cursor() as cursor:
                cursor.execute("SELECT ultimo_aplicado FROM estado_do_no WHERE no_id = %s",
                               (self.no_id,))
                linha = cursor.fetchone()
            return linha["ultimo_aplicado"] if linha else 0
        finally:
            conexao.close()

    def resposta_guardada(self, op_id: str) -> dict | None:
        conexao = self._obter_conexao()
        try:
            return RepositorioOperacoes(conexao).resposta_guardada(op_id)
        finally:
            conexao.close()

    def aplicar(self, entrada: EntradaDeLog) -> dict:
        conexao = self._obter_conexao()
        try:
            with conexao.cursor() as cursor:
                # O lock da linha do nó serializa quem aplica: o primário e o
                # RPC de replicação nunca aplicam a mesma entrada duas vezes.
                cursor.execute("SELECT ultimo_aplicado FROM estado_do_no "
                               "WHERE no_id = %s FOR UPDATE", (self.no_id,))
                linha = cursor.fetchone()
                if linha is not None and entrada.indice <= linha["ultimo_aplicado"]:
                    conexao.rollback()
                    return RepositorioOperacoes(conexao).resposta_guardada(entrada.op_id) or {}

                cursor.execute("SAVEPOINT entrada")
                try:
                    resposta = self._aplicar(conexao, entrada)
                except ErroDoBanco as erro:
                    # Não devia acontecer: o primário validou contra o mesmo
                    # estado. Se acontecer, acontece igual nos três nós (o
                    # estado é o mesmo), por isso recusar aqui é determinista:
                    # nada muda, o ponteiro avança, e o log não fica preso.
                    cursor.execute("ROLLBACK TO SAVEPOINT entrada")
                    registo.warning("nó %s: entrada %s recusada ao aplicar: %s",
                                    self.no_id, entrada.indice, erro.mensagem)
                    resposta = erro.para_json()

                cursor.execute("UPDATE estado_do_no SET ultimo_aplicado = %s "
                               "WHERE no_id = %s", (entrada.indice, self.no_id))
            conexao.commit()
            return resposta
        except Exception:
            conexao.rollback()
            raise
        finally:
            conexao.close()

    def _aplicar(self, conexao, entrada: EntradaDeLog) -> dict:
        operacao = entrada.operacao()
        if isinstance(operacao, Noop):
            return {}
        if isinstance(operacao, RegistarUsuario):
            RepositorioUsuarios(conexao).inserir({
                **operacao.para_dados(), "criado_em": entrada.instante})
            return operacao.aplicar(Livro(), entrada.indice, entrada.instante)
        if isinstance(operacao, RegistarTaxa):
            RepositorioTaxaCambio(conexao).registar(
                operacao.moeda_origem, operacao.moeda_destino,
                operacao.taxa_milionesimos, entrada.instante)
            return operacao.aplicar(Livro(), entrada.indice, entrada.instante)

        operacoes = RepositorioOperacoes(conexao)
        guardada = operacoes.resposta_guardada(entrada.op_id)
        if guardada is not None:
            return guardada  # o mesmo op_id em dois índices: aplica-se uma vez só

        contas = RepositorioContas(conexao)
        existentes = contas.bloquear(operacao.contas_tocadas())
        livro = Livro()
        for identificador, conta in existentes.items():
            livro.contas[identificador] = conta
            livro.extratos[identificador] = []
        resposta = operacao.aplicar(livro, entrada.indice, entrada.instante)

        for identificador, conta in livro.contas.items():
            if identificador in existentes:
                contas.atualizar(conta)
            else:
                contas.inserir(conta)
        # O número da operação é o índice no log: a ordem total é a mesma nos
        # três nós, e o extrato sai igual em qualquer um.
        operacoes.guardar(entrada.op_id, operacao.tipo, entrada.indice,
                          entrada.instante, resposta, **_colunas(operacao, resposta))
        return resposta
