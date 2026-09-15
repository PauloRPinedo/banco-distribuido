"""O que sai para o cliente.

Cada valor monetário vai duas vezes: em centavos, para quem calcula, e já
formatado, para quem mostra. Mandar só os centavos convidava o navegador a
dividir por 100 — um float em dinheiro, que é exatamente o que SPECS 3.1
proíbe, reintroduzido no último passo.
"""

from banco.dominio.contas import Conta, Movimento
from banco.dominio.dinheiro import formatar
from banco.servico.consultas import Auditoria


def de_conta(conta: Conta) -> dict:
    return {
        "conta": conta.id,
        "saldo_centavos": conta.saldo_centavos,
        "saldo": formatar(conta.saldo_centavos),
        "criada_em": conta.criada_em,
    }


def de_escrita(resposta: dict) -> dict:
    """Acrescenta o dinheiro em texto ao que o domínio devolveu.

    É uma função pura da resposta guardada, e é por isso que repetir um op_id
    devolve exatamente o mesmo corpo: a resposta guardada é a mesma, logo o
    enriquecimento também.
    """
    enriquecida = dict(resposta)
    if "saldo_centavos" in resposta:
        enriquecida["saldo"] = formatar(resposta["saldo_centavos"])
    if "saldos_centavos" in resposta:
        enriquecida["saldos"] = {
            conta: formatar(centavos)
            for conta, centavos in resposta["saldos_centavos"].items()}
    return enriquecida


def de_movimento(movimento: Movimento) -> dict:
    return {
        "indice": movimento.indice,
        "tipo": movimento.tipo,
        "valor_centavos": movimento.valor_centavos,
        "valor": formatar(movimento.valor_centavos),
        "contraparte": movimento.contraparte,
        "saldo_depois_centavos": movimento.saldo_depois_centavos,
        "saldo_depois": formatar(movimento.saldo_depois_centavos),
        "instante": movimento.instante,
    }


def de_auditoria(auditoria: Auditoria) -> dict:
    return {
        "total_centavos": auditoria.total_centavos,
        "total": formatar(auditoria.total_centavos),
        "total_esperado_centavos": auditoria.total_esperado_centavos,
        "total_esperado": formatar(auditoria.total_esperado_centavos),
        "divergencia_centavos": auditoria.divergencia_centavos,
        "divergencia": formatar(auditoria.divergencia_centavos),
        "divergente": auditoria.divergente,
    }
