"""O que sai para o cliente.

Cada valor monetário vai duas vezes: em centavos, para quem calcula, e já
formatado na moeda certa, para quem mostra. Mandar só os centavos convidava o
navegador a dividir por 100 — um float em dinheiro, que é exatamente o que o
banco proíbe, reintroduzido no último passo.
"""

from banco.dominio.contas import Conta, Movimento
from banco.dominio.dinheiro import formatar, formatar_taxa
from banco.servico.consultas import Auditoria


def de_conta(conta: Conta) -> dict:
    return {
        "conta": conta.id,
        "moeda": conta.moeda,
        "produto": conta.produto,
        "saldo_centavos": conta.saldo_centavos,
        "saldo": formatar(conta.saldo_centavos, conta.moeda),
        "taxa_juros": (None if conta.taxa_juros_milionesimos is None
                       else formatar_taxa(conta.taxa_juros_milionesimos)),
        "vence_em": conta.vence_em,
        "criada_em": conta.criada_em,
    }


def de_escrita(resposta: dict) -> dict:
    """Acrescenta o dinheiro em texto ao que o domínio devolveu.

    É uma função pura da resposta guardada, e é por isso que repetir um op_id
    devolve exatamente o mesmo corpo: a resposta guardada é a mesma, logo o
    enriquecimento também.
    """
    enriquecida = dict(resposta)
    moeda = resposta.get("moeda", "BRL")
    moedas = resposta.get("moedas", {})
    if "saldo_centavos" in resposta:
        enriquecida["saldo"] = formatar(resposta["saldo_centavos"], moeda)
    if "saldos_centavos" in resposta:
        enriquecida["saldos"] = {
            conta: formatar(centavos, moedas.get(conta, moeda))
            for conta, centavos in resposta["saldos_centavos"].items()}
    if "juros_centavos" in resposta:
        enriquecida["juros"] = formatar(resposta["juros_centavos"], moeda)
    if "taxa_milionesimos" in resposta:
        enriquecida["taxa"] = formatar_taxa(resposta["taxa_milionesimos"])
        enriquecida["valor"] = formatar(resposta["valor_centavos"],
                                        moedas[resposta["de"]])
        enriquecida["valor_destino"] = formatar(resposta["valor_destino_centavos"],
                                                moedas[resposta["para"]])
    return enriquecida


def de_movimento(movimento: Movimento, moeda: str) -> dict:
    return {
        "indice": movimento.indice,
        "tipo": movimento.tipo,
        "valor_centavos": movimento.valor_centavos,
        "valor": formatar(movimento.valor_centavos, moeda),
        "contraparte": movimento.contraparte,
        "saldo_depois_centavos": movimento.saldo_depois_centavos,
        "saldo_depois": formatar(movimento.saldo_depois_centavos, moeda),
        "instante": movimento.instante,
    }


def de_auditoria(auditoria: Auditoria) -> dict:
    """Uma reconciliação por moeda. Somar reais com dólares não dá número nenhum."""
    return {
        "divergente": auditoria.divergente,
        "moedas": [
            {
                "moeda": moeda.moeda,
                "total_centavos": moeda.total_centavos,
                "total": formatar(moeda.total_centavos, moeda.moeda),
                "total_esperado_centavos": moeda.total_esperado_centavos,
                "total_esperado": formatar(moeda.total_esperado_centavos, moeda.moeda),
                "divergencia_centavos": moeda.divergencia_centavos,
                "divergencia": formatar(moeda.divergencia_centavos, moeda.moeda),
            }
            for moeda in auditoria.moedas
        ],
    }
