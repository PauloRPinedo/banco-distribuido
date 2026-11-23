"""O segundo passo de uma transferência externa, e quem o termina se ficar a meio.

O primeiro passo (o débito) e o segundo (o desfecho) são escritas separadas no
log. Entre os dois, o processo pode morrer, o primário mudar, ou o outro banco
não responder. O débito fica confirmado e o desfecho por gravar: o dinheiro já
saiu da conta e ninguém sabe ainda se o outro banco o aceitou.

Termina-se de duas formas, ambas com o mesmo `concluir`:

- o cliente repete o pedido com o mesmo op_id;
- a reconciliação, que o primário corre sozinho a cada `BANCO_RECONCILIAR_S`
  segundos (30 por omissão; 0 desliga), ou que se chama em
  `POST /admin/externas/reconciliar`.

Perguntar de novo ao outro banco é seguro porque ele deduplica pelo op_id.
Gravar o desfecho duas vezes também: tem op_id próprio, `<op_id>-desfecho`, e o
segundo a chegar recebe a resposta do primeiro.
"""

import logging
import os
import threading
import time

from banco.api.dependencias import (no_do_processo, obter_gateway,
                                    obter_servico_de_consultas,
                                    servico_de_escrita)
from banco.api.respostas import de_escrita
from banco.dominio.operacoes import DesfechoExterno
from banco.servico.erros import OutroBancoIndisponivel

registo = logging.getLogger("banco.externas")


def concluir(gateway, de: str, sistema_externo_id: str, valor_centavos: int,
             op_id: str) -> dict:
    """Pergunta ao outro banco e grava o desfecho. O débito já está confirmado."""
    id_do_desfecho = f"{op_id}-desfecho"
    with servico_de_escrita() as servico:
        guardado = servico.ja_aplicada(id_do_desfecho)
    if guardado is not None:
        return de_escrita(guardado)

    try:
        decisao = gateway.confirmar(sistema_externo_id, valor_centavos, op_id)
    except Exception as erro:
        raise OutroBancoIndisponivel(
            f"o débito ficou feito e {sistema_externo_id} não respondeu ({erro}); "
            "repetir com o mesmo op_id, ou esperar pela reconciliação") from erro

    with servico_de_escrita() as servico:
        resposta = servico.aplicar(
            DesfechoExterno(de, valor_centavos, decisao["confirmada"],
                            decisao["referencia_externa"], op_id),
            id_do_desfecho)
    return de_escrita(resposta)


def reconciliar(idade_minima_s: float) -> dict:
    """Termina os débitos sem desfecho com mais de `idade_minima_s` segundos.

    A idade mínima deixa em paz os pedidos que ainda estão à espera do outro
    banco. Um débito cujo banco continua sem responder fica para a próxima vez.
    """
    consultas_gen = obter_servico_de_consultas()
    consultas = next(consultas_gen)
    try:
        pendentes = consultas.externas_pendentes(time.time() - idade_minima_s)
    finally:
        consultas_gen.close()

    gateway = obter_gateway()
    concluidas, por_concluir = [], []
    for linha in pendentes:
        try:
            concluidas.append(concluir(gateway, linha["conta_origem_id"],
                                       linha["sistema_externo_id"],
                                       linha["valor_centavos"], linha["op_id"]))
        except OutroBancoIndisponivel:
            por_concluir.append(linha["op_id"])
    return {"concluidas": concluidas, "por_concluir": por_concluir}


class Reconciliador:
    """Um fio que, só no primário, chama `reconciliar` de tempos a tempos."""

    def __init__(self) -> None:
        self.intervalo_s = float(os.environ.get("BANCO_RECONCILIAR_S", "30"))
        self._parar = threading.Event()
        self._fio = threading.Thread(target=self._correr, name="reconciliador",
                                     daemon=True)

    def arrancar(self) -> None:
        if self.intervalo_s > 0:
            self._fio.start()

    def parar(self) -> None:
        self._parar.set()
        if self._fio.is_alive():
            self._fio.join(timeout=5)

    def _correr(self) -> None:
        while not self._parar.wait(self.intervalo_s):
            try:
                if no_do_processo().e_primario():
                    feito = reconciliar(self.intervalo_s)
                    if feito["concluidas"] or feito["por_concluir"]:
                        registo.warning("reconciliação: %d concluídas, %d por concluir",
                                        len(feito["concluidas"]),
                                        len(feito["por_concluir"]))
            except Exception:
                # Sem maioria, ou o primário mudou a meio: tenta-se na próxima.
                registo.exception("reconciliação falhou; tenta-se outra vez")
