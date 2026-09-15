"""Toda a escrita do banco passa por aqui, e só por aqui.

A ordem obrigatória de uma escrita vive nesta função, uma vez.
As quatro operações são a mesma sequência de passos com um objeto diferente lá
dentro — escrevê-la quatro vezes seria dar-lhe quatro sítios para divergir.

O que torna isto possível é o domínio já dizer tudo o que é preciso saber:
`contas_tocadas()` dá a ordem dos locks, `validar()` diz se pode, `aplicar()`
faz, e `tipo` dá o nome. O serviço não decide nada — arruma.
"""

import time

from banco.dominio.contas import Livro
from banco.dominio.operacoes import (CriarConta, Deposito, Operacao, Saque,
                                     Transferencia)


def _partes(operacao: Operacao) -> tuple[str | None, str | None, int]:
    """Origem, destino e valor desta operação, como vão para a tabela.

    O dinheiro entra pelo destino e sai pela origem. Criar conta e depositar só
    têm destino, sacar só tem origem, e é essa assimetria que faz a auditoria
    somar certo sem ter de conhecer as operações uma a uma.
    """
    if isinstance(operacao, CriarConta):
        return None, operacao.conta, operacao.saldo_inicial_centavos
    if isinstance(operacao, Deposito):
        return None, operacao.conta, operacao.valor_centavos
    if isinstance(operacao, Saque):
        return operacao.conta, None, operacao.valor_centavos
    if isinstance(operacao, Transferencia):
        return operacao.de, operacao.para, operacao.valor_centavos
    raise TypeError(f"operação sem lugar na tabela: {type(operacao).__name__}")


class ServicoDeEscrita:

    def __init__(self, contas, operacoes) -> None:
        self._contas = contas
        self._operacoes = operacoes

    def aplicar(self, operacao: Operacao, op_id: str) -> dict:
        """Aplica uma operação e devolve o que o cliente vai receber.

        Os passos vão numerados, e nenhum pode trocar de lugar. O passo 5 —
        replicar e esperar pela maioria — não existe nesta etapa: há um nó só,
        e a durabilidade é o commit do PostgreSQL.
        """
        # 1. Já foi aplicada? Devolver o resultado guardado e terminar.
        guardada = self._operacoes.resposta_guardada(op_id)
        if guardada is not None:
            return guardada

        # 2. Bloquear as contas tocadas, por ordem crescente de id.
        existentes = self._contas.bloquear(operacao.contas_tocadas())

        # 2b. Voltar a perguntar, agora já serializados pelos locks. Sem isto,
        # duas retentativas simultâneas veriam ambas "ainda não aplicada" no
        # passo 1 e ambas seguiriam em frente.
        guardada = self._operacoes.resposta_guardada(op_id)
        if guardada is not None:
            return guardada

        livro = Livro()
        for identificador, conta in existentes.items():
            livro.contas[identificador] = conta
            livro.extratos[identificador] = []

        # 3. Validar. Antes de gastar um número da sequência e antes de gravar:
        # nunca se regista uma operação que vai ser recusada.
        operacao.validar(livro)

        # 4. Gravar. O número é o lugar na ordem total; pode ter saltos, porque
        # uma sequência não volta atrás quando a transação é revertida. Serve
        # para ordenar, não para contar, e para ordenar um salto é inofensivo.
        instante = time.time()
        numero = self._operacoes.proximo_numero()
        resposta = operacao.aplicar(livro, numero, instante)

        # 6. Aplicar ao estado e guardar o resultado deste op_id. Tudo na mesma
        # transação: ou as duas contas mudam, ou nenhuma muda.
        for identificador, conta in livro.contas.items():
            if identificador in existentes:
                self._contas.atualizar(conta)
            else:
                self._contas.inserir(conta)

        origem, destino, valor_centavos = _partes(operacao)
        self._operacoes.guardar(op_id, operacao.tipo, origem, destino,
                                valor_centavos, numero, instante, resposta)

        # 7. Responder ao cliente — o commit é de quem abriu a transação.
        return resposta
