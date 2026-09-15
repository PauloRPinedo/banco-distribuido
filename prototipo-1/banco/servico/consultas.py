"""As leituras: saldo, extrato e auditoria.

Separadas da escrita porque não tomam locks nenhuns nem gastam números da
sequência. Juntá-las ao aplicador só tornaria mais difícil ver que ele é a
ordem obrigatória de uma escrita e nada mais.
"""

from dataclasses import dataclass

from banco.dominio.contas import Conta, Movimento
from banco.dominio.erros import ContaInexistente
from banco.dominio.operacoes import TRANSFERENCIA


@dataclass(frozen=True)
class Auditoria:
    """RF-14: o dinheiro que existe contra o dinheiro que devia existir.

    Os dois totais vêm de cálculos independentes — a soma dos saldos e a soma
    do histórico. Se fossem o mesmo cálculo duas vezes, concordarem não
    provaria nada.
    """

    total_centavos: int
    total_esperado_centavos: int
    divergencia_centavos: int
    divergente: bool


def _movimento(linha: dict, identificador: str) -> Movimento:
    """Uma linha do histórico vista do lado desta conta.

    A mesma transferência é -25,00 para quem envia e +25,00 para quem recebe,
    por isso o sinal nasce aqui e não na tabela.

    O saldo depois do movimento sai da resposta guardada, e não de uma soma
    feita agora: recalcular linha a linha obrigaria a reprocessar o histórico
    inteiro a cada consulta, e daria um número diferente se entretanto houve
    outras operações.
    """
    e_destino = linha["conta_destino_id"] == identificador
    valor_centavos = linha["valor_centavos"] if e_destino else -linha["valor_centavos"]
    resposta = linha["resposta"]

    if linha["tipo"] == TRANSFERENCIA:
        contraparte = (linha["conta_origem_id"] if e_destino
                       else linha["conta_destino_id"])
        saldo_depois_centavos = resposta["saldos_centavos"][identificador]
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

    def __init__(self, contas, operacoes) -> None:
        self._contas = contas
        self._operacoes = operacoes

    def saldo(self, identificador: str) -> Conta:
        conta = self._contas.obter(identificador)
        if conta is None:
            raise ContaInexistente(f"a conta {identificador!r} não existe")
        return conta

    def extrato(self, identificador: str) -> list[Movimento]:
        self.saldo(identificador)  # recusa já aqui se a conta não existe
        return [_movimento(linha, identificador)
                for linha in self._operacoes.listar_por_conta(identificador)]

    def auditoria(self) -> Auditoria:
        total_centavos = self._contas.total_dos_saldos_centavos()
        total_esperado_centavos = self._operacoes.total_pelo_log_centavos()
        return Auditoria(
            total_centavos=total_centavos,
            total_esperado_centavos=total_esperado_centavos,
            divergencia_centavos=total_centavos - total_esperado_centavos,
            divergente=total_centavos != total_esperado_centavos,
        )
