"""Apresentação da linha de comando.

O princípio é um só: **cor significa desvio**. A saída normal não tem cor
nenhuma, para que uma mancha de cor no ecrã projetado queira sempre dizer que
alguma coisa saiu do normal.
"""

import os
import sys

from banco.dominio.dinheiro import formatar

VERMELHO = "\033[31m"
AMARELO = "\033[33m"
VERDE = "\033[32m"
_FIM = "\033[0m"

RECUO = "  "


def ha_cor(saida=None) -> bool:
    """Cor só num terminal.

    Redirecionar para ficheiro tem de dar texto limpo: os registos da
    demonstração vão para o relatório, e sequências de escape tornam-nos
    ilegíveis. NO_COLOR é a convenção habitual para desligar à mão.
    """
    saida = saida or sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    return hasattr(saida, "isatty") and saida.isatty()


def pintar(texto: str, cor: str, saida=None) -> str:
    return f"{cor}{texto}{_FIM}" if ha_cor(saida) else texto


def dinheiro(centavos: int) -> str:
    return formatar(centavos)


def tabela(cabecalhos: list[str], linhas: list[list[str]],
           a_direita: set[int] | None = None) -> str:
    """Colunas alinhadas, sem molduras.

    Uma moldura ASCII ocupa metade da largura a desenhar caixas. Duas colunas de
    espaço separam tão bem e deixam o conteúdo respirar.
    """
    a_direita = a_direita or set()
    todas = [cabecalhos] + [[str(c) for c in linha] for linha in linhas]
    larguras = [max(len(linha[n]) for linha in todas)
                for n in range(len(cabecalhos))]

    def compor(celulas: list[str]) -> str:
        partes = []
        for n, celula in enumerate(celulas):
            partes.append(celula.rjust(larguras[n]) if n in a_direita
                          else celula.ljust(larguras[n]))
        return RECUO + "  ".join(partes).rstrip()

    saida = [compor([c.upper() for c in cabecalhos])]
    saida.extend(compor([str(c) for c in linha]) for linha in linhas)
    return "\n".join(saida)


def erro(titulo: str, detalhe: str, sugestao: str) -> str:
    """Três linhas: o que aconteceu, com que números, e o que fazer a seguir.

    A terceira é obrigatória. Um erro que não diz o passo seguinte deixa quem o
    lê exatamente onde estava.
    """
    linhas = [RECUO + pintar(f"erro: {titulo}", VERMELHO, sys.stderr)]
    if detalhe:
        linhas.append(RECUO + detalhe)
    linhas.append(RECUO + f"→ {sugestao}")
    return "\n".join(linhas)
