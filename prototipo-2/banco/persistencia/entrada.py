"""A entrada de log: a unidade de durabilidade e do extrato.

O formato é o da secção 3.3 de docs/SPECS.md e não muda entre etapas. Na etapa 1
o `epoch` é sempre 1 e ninguém o lê, mas o campo existe: mudar o formato do WAL
na etapa 2 obrigaria a converter ficheiros e a explicar duas versões na defesa.
"""

import json
from dataclasses import dataclass

from banco.dominio.operacoes import Operacao, de_dados

EPOCH_DA_ETAPA_1 = 1


@dataclass(frozen=True)
class EntradaDeLog:
    indice: int
    epoch: int
    op_id: str
    tipo: str
    dados: dict
    instante: float

    @staticmethod
    def de_operacao(indice: int, op_id: str, operacao: Operacao,
                    instante: float, epoch: int = EPOCH_DA_ETAPA_1) -> "EntradaDeLog":
        return EntradaDeLog(indice, epoch, op_id, operacao.tipo,
                            operacao.para_dados(), instante)

    def operacao(self) -> Operacao:
        return de_dados(self.tipo, self.dados)

    def para_linha(self) -> str:
        """Uma linha JSON, sem espaços supérfluos e sempre com o mesmo formato.

        `sort_keys` não é cosmética: com as chaves em ordem fixa, duas execuções
        com a mesma sequência de operações produzem ficheiros byte a byte
        iguais, e um `diff` entre os WAL de dois nós passa a ser útil na etapa 2.
        """
        return json.dumps({
            "indice": self.indice,
            "epoch": self.epoch,
            "op_id": self.op_id,
            "tipo": self.tipo,
            "dados": self.dados,
            "instante": self.instante,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def de_linha(linha: str) -> "EntradaDeLog":
        bruto = json.loads(linha)
        return EntradaDeLog(
            indice=bruto["indice"],
            epoch=bruto["epoch"],
            op_id=bruto["op_id"],
            tipo=bruto["tipo"],
            dados=bruto["dados"],
            instante=bruto["instante"],
        )
