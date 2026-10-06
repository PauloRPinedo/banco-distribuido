"""Três nós no mesmo processo, com uma rede falsa e as tabelas em memória.

É o protocolo inteiro — eleição, replicação, heartbeat, fencing — sem HTTP nem
PostgreSQL. A rede falsa substitui o `pedir_ao_no` do replicador: em vez de um
pedido HTTP, chama diretamente `replicar` ou `votar` do nó de destino. Um nó
"em baixo" é um nó que a rede deixou de alcançar e que parou o seu ciclo — tal
como um processo morto, mas sem esperar por timeouts de rede.

O `AplicadorEmMemoria` faz o papel do `AplicadorPostgres`: aplica cada entrada
confirmada a um `Livro`. Os dois têm o mesmo contrato, e os testes de integração
(`tests/integracao/teste_cluster.py`) correm o mesmo protocolo contra três bases
de dados a sério.
"""

import time

from banco.cluster import replicacao
from banco.cluster.armazem_memoria import ArmazemEmMemoria
from banco.cluster.cliente_interno import Resposta
from banco.cluster.configuracao import ConfiguracaoDoCluster
from banco.cluster.eleicao import PedidoDeVoto
from banco.cluster.entrada import EntradaDeLog
from banco.cluster.no import No
from banco.cluster.operacoes_de_sistema import move_dinheiro
from banco.dominio.contas import Livro
from banco.dominio.erros import ErroDoBanco

# Tempos curtos para a suíte correr depressa, na mesma proporção dos da
# demonstração (heartbeat bem abaixo do timeout de eleição mais curto).
TEMPOS = {"heartbeat_ms": 20, "timeout_eleicao_ms": [100, 200],
          "timeout_replicacao_ms": 150, "semente": 7}


class AplicadorEmMemoria:

    def __init__(self) -> None:
        self.livro = Livro()
        self.respostas: dict[str, dict] = {}
        self.ultimo = 0

    def ultimo_aplicado(self) -> int:
        return self.ultimo

    def resposta_guardada(self, op_id: str) -> dict | None:
        return self.respostas.get(op_id)

    def aplicar(self, entrada: EntradaDeLog) -> dict:
        if entrada.indice <= self.ultimo:
            return self.respostas.get(entrada.op_id, {})
        operacao = entrada.operacao()
        if entrada.op_id in self.respostas and move_dinheiro(operacao):
            resposta = self.respostas[entrada.op_id]
        else:
            try:
                resposta = operacao.aplicar(self.livro, entrada.indice, entrada.instante)
            except ErroDoBanco as erro:
                resposta = erro.para_json()
            self.respostas[entrada.op_id] = resposta
        self.ultimo = entrada.indice
        return resposta

    def saldo(self, conta: str) -> int:
        return self.livro.obter(conta).saldo_centavos


class RedeFalsa:
    """Encaminha os RPCs do protocolo para os nós vivos deste processo."""

    def __init__(self) -> None:
        self.nos: dict[str, No] = {}
        self.em_baixo: set[str] = set()

    def pedir(self, par, caminho: str, corpo: dict | None = None,
              prazo_ms: int = 500, metodo: str = "POST") -> Resposta:
        destino = self.nos.get(par.id)
        if destino is None or par.id in self.em_baixo:
            return Resposta(False, motivo="em baixo")
        try:
            if caminho == "/interno/replicar":
                entradas = [EntradaDeLog(**e) for e in corpo["entradas"]]
                resposta = destino.replicar(
                    corpo["epoch"], corpo["id_lider"], corpo["indice_anterior"],
                    corpo["epoch_anterior"], entradas, corpo["commit_lider"])
            elif caminho == "/interno/votar":
                resposta = destino.votar(PedidoDeVoto(**corpo))
            elif caminho == "/interno/estado":
                resposta = destino.estado_do_no()
            else:
                return Resposta(False, motivo=f"rota desconhecida {caminho}")
        except ErroDoBanco:
            # Uma partição injetada: a mensagem perde-se.
            return Resposta(False, motivo="partição")
        return Resposta(True, 200, resposta)


class ClusterEmMemoria:

    def __init__(self, teste, ids=("A", "B", "C")) -> None:
        self.teste = teste
        self.configuracao = ConfiguracaoDoCluster.de_dados({
            "nos": [{"id": i, "endereco": f"no-{i.lower()}", "porta": 8001} for i in ids],
            **TEMPOS})
        self.rede = RedeFalsa()
        original = replicacao.pedir_ao_no
        replicacao.pedir_ao_no = self.rede.pedir
        teste.addCleanup(setattr, replicacao, "pedir_ao_no", original)

        # O "disco" de cada nó: sobrevive a derrubar e reiniciar o nó.
        self.armazens = {i: ArmazemEmMemoria() for i in ids}
        self.aplicadores = {i: AplicadorEmMemoria() for i in ids}
        for i in ids:
            self._ligar(i)
        teste.addCleanup(self.parar_tudo)

    def _ligar(self, id_do_no: str) -> No:
        no = No(id_do_no, self.armazens[id_do_no], self.aplicadores[id_do_no],
                self.configuracao)
        self.rede.nos[id_do_no] = no
        self.rede.em_baixo.discard(id_do_no)
        no.arrancar()
        return no

    @property
    def nos(self) -> list[No]:
        return [no for i, no in self.rede.nos.items() if i not in self.rede.em_baixo]

    def no(self, id_do_no: str) -> No:
        return self.rede.nos[id_do_no]

    def derrubar(self, no: No) -> None:
        """Como um `kill -9`: deixa de responder e de bater o coração."""
        self.rede.em_baixo.add(no.id)
        no.replicador.parar()

    def reiniciar(self, id_do_no: str) -> No:
        """Um processo novo sobre o mesmo disco."""
        return self._ligar(id_do_no)

    def esperar_primario(self, entre=None, limite: float = 3.0) -> No:
        candidatos = entre if entre is not None else self.nos
        fim = time.monotonic() + limite
        while time.monotonic() < fim:
            primarios = [no for no in candidatos if no.eleicao.sou_primario()
                         and no.id not in self.rede.em_baixo]
            if len(primarios) == 1:
                return primarios[0]
            time.sleep(0.01)
        self.teste.fail(f"nenhum primário único em {limite}s")

    def esperar(self, condicao, limite: float = 3.0) -> bool:
        fim = time.monotonic() + limite
        while time.monotonic() < fim:
            if condicao():
                return True
            time.sleep(0.01)
        return False

    def outros(self, no: No) -> list[No]:
        return [outro for outro in self.nos if outro.id != no.id]

    def parar_tudo(self) -> None:
        for no in self.rede.nos.values():
            if no.replicador is not None:
                no.replicador.parar()
