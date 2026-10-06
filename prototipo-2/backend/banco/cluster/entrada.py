"""A entrada de log: a unidade de replicação.

Uma entrada é uma operação com o seu lugar na ordem total (`indice`), o mandato
em que foi escrita (`epoch`) e o instante que o primário lhe deu. É o que viaja
entre nós e o que cada nó aplica às suas tabelas — por isso tudo o que não é
determinista (instante, ids, sal do hash) já vem decidido aqui dentro.
"""

import json
from dataclasses import dataclass

from banco.cluster.operacoes_de_sistema import de_dados
from banco.dominio.operacoes import Operacao

EPOCH_INICIAL = 1


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
                    instante: float, epoch: int = EPOCH_INICIAL) -> "EntradaDeLog":
        return EntradaDeLog(indice, epoch, op_id, operacao.tipo,
                            operacao.para_dados(), instante)

    def operacao(self) -> Operacao:
        return de_dados(self.tipo, self.dados)

    def para_linha(self) -> str:
        """Uma linha JSON, sem espaços supérfluos e sempre com o mesmo formato.

        `sort_keys` não é cosmética: com as chaves em ordem fixa, os três nós
        guardam os mesmos bytes para a mesma entrada, e comparar logs é um `diff`.
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
