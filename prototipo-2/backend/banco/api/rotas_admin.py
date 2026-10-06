"""Rotas de operação do banco: taxas de câmbio, juros e sistemas externos.

Exigem sessão, mas não um papel de administrador — não há papéis neste
protótipo. É uma simplificação assumida e escrita no README.
"""

import time

from fastapi import APIRouter, Depends

from banco.api.dependencias import (obter_servico_de_consultas,
                                    obter_servico_de_escrita,
                                    servico_de_escrita)
from banco.api.pedidos import PedidoDeTaxa, em_milionesimos
from banco.api.respostas import de_escrita
from banco.api.seguranca import usuario_autenticado
from banco.dominio.dinheiro import MOEDAS, formatar_taxa
from banco.dominio.erros import ValorInvalido
from banco.dominio.operacoes import Juros
from banco.servico.erros import TaxaIndisponivel

router = APIRouter()


@router.get("/taxas/{moeda_origem}/{moeda_destino}")
def consultar_taxa(moeda_origem: str, moeda_destino: str,
                   consultas=Depends(obter_servico_de_consultas)) -> dict:
    taxa = consultas.taxa(moeda_origem, moeda_destino, time.time())
    if taxa is None:
        raise TaxaIndisponivel(f"não há taxa de {moeda_origem} para {moeda_destino}")
    return {"moeda_origem": moeda_origem, "moeda_destino": moeda_destino,
            "taxa_milionesimos": taxa, "taxa": formatar_taxa(taxa)}


@router.post("/admin/taxas")
def registar_taxa(pedido: PedidoDeTaxa,
                  usuario_id: str = Depends(usuario_autenticado),
                  servico=Depends(obter_servico_de_escrita)) -> dict:
    """Uma taxa nova vale a partir do instante da sua entrada no log; as
    anteriores ficam no histórico. Passa pelo log como qualquer escrita, por
    isso os três nós fazem os mesmos câmbios.
    """
    if pedido.moeda_origem not in MOEDAS or pedido.moeda_destino not in MOEDAS:
        raise ValorInvalido(f"moedas conhecidas: {', '.join(MOEDAS)}")
    if pedido.moeda_origem == pedido.moeda_destino:
        raise ValorInvalido("a taxa é entre duas moedas diferentes")
    taxa = em_milionesimos(pedido.taxa)
    resposta = servico.registar_taxa(pedido.moeda_origem, pedido.moeda_destino, taxa)
    return {**resposta, "taxa": formatar_taxa(taxa)}


@router.post("/admin/juros")
def creditar_juros(usuario_id: str = Depends(usuario_autenticado),
                   consultas=Depends(obter_servico_de_consultas)) -> dict:
    """O *tick* de juros (RN-13), chamado à mão ou por um cron.

    Cada conta é uma operação `Juros` na sua própria transação, com op_id
    `juros-<conta>-<instante>`: repetir o mesmo tick não paga duas vezes, e
    uma conta que falhe não impede as outras.
    """
    ate = time.time()
    creditadas = []
    for conta in consultas.contas_com_juros():
        try:
            with servico_de_escrita() as servico:
                resposta = servico.aplicar(Juros(conta, ate), f"juros-{conta}-{int(ate)}")
            creditadas.append(de_escrita(resposta))
        except ValorInvalido:
            continue  # ainda sem juros a creditar (prazo fixo por vencer, etc.)
    return {"ate": ate, "creditadas": creditadas}


@router.get("/sistemas-externos")
def listar_sistemas_externos(consultas=Depends(obter_servico_de_consultas)) -> dict:
    return {"sistemas": consultas.sistemas_externos()}
