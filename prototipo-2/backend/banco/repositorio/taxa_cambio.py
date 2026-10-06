"""Leitura e escrita da tabela `taxa_cambio` — RF-20.

Uma taxa nova não apaga a anterior: acrescenta uma linha com o instante a
partir do qual vale. Assim pode sempre saber-se que taxa valia num momento
passado, e é a que ficou gravada em cada câmbio.
"""


class RepositorioTaxaCambio:

    def __init__(self, conexao) -> None:
        self._conexao = conexao

    def taxa_vigente(self, moeda_origem: str, moeda_destino: str,
                     instante: float) -> int | None:
        """A taxa, em milionésimos, mais recente que já valia em `instante`."""
        with self._conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT taxa_milionesimos FROM taxa_cambio
                WHERE moeda_origem = %s AND moeda_destino = %s
                  AND vigente_desde <= %s
                ORDER BY vigente_desde DESC
                LIMIT 1
                """,
                (moeda_origem, moeda_destino, instante),
            )
            linha = cursor.fetchone()
        return None if linha is None else linha["taxa_milionesimos"]

    def registar(self, moeda_origem: str, moeda_destino: str,
                 taxa_milionesimos: int, vigente_desde: float) -> None:
        with self._conexao.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO taxa_cambio (moeda_origem, moeda_destino,
                                         taxa_milionesimos, vigente_desde)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (moeda_origem, moeda_destino, vigente_desde) DO NOTHING
                """,
                (moeda_origem, moeda_destino, taxa_milionesimos, vigente_desde),
            )
