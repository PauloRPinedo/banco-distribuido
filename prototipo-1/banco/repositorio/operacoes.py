"""Leitura e escrita da tabela `operacao`.

A tabela faz dois trabalhos ao mesmo tempo: é o histórico que alimenta o
extrato e a auditoria, e é a tabela de deduplicação por `op_id`. São o mesmo
facto — "esta operação aconteceu" — e separá-los em duas tabelas daria dois
sítios a poder divergir.
"""

import json

TIPOS_QUE_ACRESCENTAM = ("criar_conta", "deposito")


class RepositorioOperacoes:

    def __init__(self, conexao) -> None:
        self._conexao = conexao

    def resposta_guardada(self, op_id: str) -> dict | None:
        """A resposta que este `op_id` já recebeu, ou None se é a primeira vez.

        Metade da deduplicação de SPECS 3.3; a outra metade — devolvê-la sem
        voltar a aplicar nada — é do serviço.
        """
        with self._conexao.cursor() as cursor:
            cursor.execute("SELECT resposta FROM operacao WHERE op_id = %s", (op_id,))
            linha = cursor.fetchone()
        return None if linha is None else linha["resposta"]

    def proximo_numero(self) -> int:
        """O próximo lugar na ordem total das operações (o `indice` de SPECS 3.3)."""
        with self._conexao.cursor() as cursor:
            cursor.execute("SELECT nextval('operacao_numero') AS numero")
            return cursor.fetchone()["numero"]

    def guardar(self, op_id: str, tipo: str, conta_origem_id: str | None,
                conta_destino_id: str | None, valor_centavos: int, numero: int,
                instante: float, resposta: dict) -> None:
        with self._conexao.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO operacao (op_id, numero, tipo, conta_origem_id,
                                      conta_destino_id, valor_centavos,
                                      resposta, instante)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (op_id, numero, tipo, conta_origem_id, conta_destino_id,
                 valor_centavos, json.dumps(resposta), instante),
            )

    def listar_por_conta(self, identificador: str) -> list[dict]:
        """As operações que tocaram esta conta, pela ordem em que aconteceram.

        Ordena por `numero` e não por `instante`: dois instantes podem empatar,
        a ordem total não.
        """
        with self._conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT numero, tipo, conta_origem_id, conta_destino_id,
                       valor_centavos, resposta, instante
                FROM operacao
                WHERE conta_origem_id = %(id)s OR conta_destino_id = %(id)s
                ORDER BY numero
                """,
                {"id": identificador},
            )
            return cursor.fetchall()

    def total_pelo_log_centavos(self) -> int:
        """O lado direito da auditoria (RF-14): quanto dinheiro devia existir.

        Criar conta e depósito acrescentam, saque retira, e a transferência é
        neutra por construção. Este cálculo não olha para os saldos — é por ser
        independente deles que compará-lo com a soma dos saldos verifica alguma
        coisa.
        """
        with self._conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(SUM(
                    CASE
                        WHEN tipo IN %(acrescentam)s THEN valor_centavos
                        WHEN tipo = 'saque' THEN -valor_centavos
                        ELSE 0
                    END
                ), 0)::BIGINT AS total
                FROM operacao
                """,
                {"acrescentam": TIPOS_QUE_ACRESCENTAM},
            )
            return cursor.fetchone()["total"]
