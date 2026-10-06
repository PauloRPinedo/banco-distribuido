"""As leituras: saldo, extrato, auditoria, taxas e sistemas externos.

Separadas da escrita porque não tomam locks nenhuns nem gastam números da
sequência. Juntá-las ao aplicador só tornaria mais difícil ver que ele é a
ordem obrigatória de uma escrita e nada mais.
"""

from dataclasses import dataclass

from banco.dominio.contas import Conta, Movimento
from banco.dominio.erros import ContaInexistente
from banco.dominio.operacoes import CAMBIO, TRANSFERENCIA, TRANSFERENCIA_EXTERNA


@dataclass(frozen=True)
class AuditoriaDeMoeda:
    """RF-14, numa moeda: o dinheiro que existe contra o que devia existir.

    Os dois totais vêm de cálculos independentes — a soma dos saldos e a soma
    do histórico. Se fossem o mesmo cálculo duas vezes, concordarem não
    provaria nada.
    """

    moeda: str
    total_centavos: int
    total_esperado_centavos: int

    @property
    def divergencia_centavos(self) -> int:
        return self.total_centavos - self.total_esperado_centavos


@dataclass(frozen=True)
class Auditoria:
    moedas: list[AuditoriaDeMoeda]

    @property
    def divergente(self) -> bool:
        return any(moeda.divergencia_centavos != 0 for moeda in self.moedas)


def _movimento(linha: dict, identificador: str) -> Movimento:
    """Uma linha do histórico vista do lado desta conta.

    A mesma transferência é -25,00 para quem envia e +25,00 para quem recebe,
    por isso o sinal nasce aqui e não na tabela. Num câmbio, quem recebe vê o
    valor já convertido.

    O saldo depois do movimento sai da resposta guardada, e não de uma soma
    feita agora: recalcular linha a linha obrigaria a reprocessar o histórico
    inteiro a cada consulta.
    """
    e_destino = linha["conta_destino_id"] == identificador
    resposta = linha["resposta"]

    if e_destino and linha["tipo"] == CAMBIO:
        valor_centavos = linha["valor_destino_centavos"]
    elif e_destino:
        valor_centavos = linha["valor_centavos"]
    else:
        valor_centavos = -linha["valor_centavos"]

    if linha["tipo"] in (TRANSFERENCIA, CAMBIO):
        contraparte = (linha["conta_origem_id"] if e_destino
                       else linha["conta_destino_id"])
        saldo_depois_centavos = resposta["saldos_centavos"][identificador]
    elif linha["tipo"] == TRANSFERENCIA_EXTERNA:
        contraparte = linha["sistema_externo_id"]
        saldo_depois_centavos = resposta["saldo_centavos"]
    else:
        contraparte = None
        saldo_depois_centavos = resposta["saldo_centavos"]

    return Movimento(
        indice=linha["numero"],
        tipo=linha["tipo"],
        valor_centavos=valor_centavos,
        contraparte=contraparte,
        saldo_depois_centavos=saldo_depois_centavos,
        instante=linha["instante"],
    )


class ServicoDeConsultas:

    def __init__(self, contas, operacoes, taxas=None, sistemas=None) -> None:
        self._contas = contas
        self._operacoes = operacoes
        self._taxas = taxas
        self._sistemas = sistemas

    def saldo(self, identificador: str) -> Conta:
        conta = self._contas.obter(identificador)
        if conta is None:
            raise ContaInexistente(f"a conta {identificador!r} não existe")
        return conta

    def contas_do_dono(self, usuario_id: str) -> list[Conta]:
        return self._contas.listar_do_dono(usuario_id)

    def extrato(self, identificador: str) -> list[Movimento]:
        self.saldo(identificador)  # recusa já aqui se a conta não existe
        # Uma devolução confirmada não move dinheiro: não é uma linha de extrato.
        return [_movimento(linha, identificador)
                for linha in self._operacoes.listar_por_conta(identificador)
                if not (linha["tipo"] == "desfecho_externo"
                        and linha["valor_centavos"] == 0)]

    def taxa(self, moeda_origem: str, moeda_destino: str, instante: float) -> int | None:
        return self._taxas.taxa_vigente(moeda_origem, moeda_destino, instante)

    def sistema_ativo(self, sistema_externo_id: str) -> bool:
        return self._sistemas.ativo(sistema_externo_id)

    def sistemas_externos(self) -> list[dict]:
        return self._sistemas.listar()

    def contas_com_juros(self) -> list[str]:
        return self._contas.listar_com_juros()

    def auditoria(self) -> Auditoria:
        saldos = self._contas.total_dos_saldos_por_moeda()
        esperado = self._operacoes.total_pelo_log_por_moeda()
        return Auditoria([
            AuditoriaDeMoeda(moeda, saldos.get(moeda, 0), esperado.get(moeda, 0))
            for moeda in sorted(set(saldos) | set(esperado))
        ])
