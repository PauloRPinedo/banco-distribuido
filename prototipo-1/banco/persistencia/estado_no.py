"""O estado de eleição do nó: `epoch` e em quem votou.

Na etapa 1 não há eleição e nada disto é usado para decidir seja o que for. O
ficheiro existe na mesma porque a etapa 2 precisa dele e porque o gravar com
fsync é o detalhe que ali passa a ser de correção, não de desempenho: um nó que
vota, cai e esquece o voto votaria outra vez no mesmo `epoch`, e dois candidatos
diferentes poderiam somar maioria.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EstadoDoNo:
    caminho: Path
    epoch: int = 1
    votou_em: str | None = None

    @staticmethod
    def carregar(caminho: Path) -> "EstadoDoNo":
        caminho = Path(caminho)
        if not caminho.exists():
            return EstadoDoNo(caminho)
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
        return EstadoDoNo(caminho, bruto["epoch"], bruto["votou_em"])

    def gravar(self) -> None:
        """Grava de forma atómica: escreve num temporário e substitui.

        Sem isto, uma queda a meio da escrita deixaria um `estado.json` truncado,
        e o nó não arrancaria por não conseguir ler o próprio epoch.
        """
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.caminho.with_suffix(".tmp")
        conteudo = json.dumps({"epoch": self.epoch, "votou_em": self.votou_em},
                              ensure_ascii=False, sort_keys=True)
        with open(temporario, "w", encoding="utf-8") as ficheiro:
            ficheiro.write(conteudo)
            ficheiro.flush()
            os.fsync(ficheiro.fileno())
        os.replace(temporario, self.caminho)
