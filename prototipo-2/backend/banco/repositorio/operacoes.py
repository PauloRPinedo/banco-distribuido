"""Leitura e escrita da tabela `operacao`.

A tabela faz dois trabalhos ao mesmo tempo: é o histórico que alimenta o
extrato e a auditoria, e é a tabela de deduplicação por `op_id`. São o mesmo
facto — "esta operação aconteceu" — e separá-los em duas tabelas daria dois
sítios a poder divergir.
"""

import json

TIPOS_QUE_ACRESCENTAM = ("criar_conta", "deposito", "juros", "desfecho_externo")
TIPOS_QUE_RETIRAM = ("saque", "transferencia_externa")


class RepositorioOperacoes:

    def __init__(self, conexao) -> None:
        self._conexao = conexao

    def resposta_guardada(self, op_id: str) -> dict | None:
        """A resposta que este `op_id` já recebeu, ou None se é a primeira vez.

        Metade da deduplicação; a outra metade — devolvê-la sem
        voltar a aplicar nada — é do serviço.
        """
        with self._conexao.cursor() as cursor:
            cursor.execute("SELECT resposta FROM operacao WHERE op_id = %s", (op_id,))
            linha = cursor.fetchone()
        return None if linha is None else linha["resposta"]

    def guardar(self, op_id: str, tipo: str, numero: int, instante: float,
                resposta: dict, *, valor_centavos: int, origem: str | None = None,
                destino: str | None = None, moeda_origem: str | None = None,
                moeda_destino: str | None = None, taxa_milionesimos: int | None = None,
                valor_destino_centavos: int | None = None,
                sistema_externo_id: str | None = None,
                referencia_externa: str | None = None) -> None:
        with self._conexao.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO operacao (op_id, numero, tipo, conta_origem_id,
                                      conta_destino_id, valor_centavos,
                                      moeda_origem, moeda_destino,
                                      taxa_milionesimos, valor_destino_centavos,
                                      sistema_externo_id, referencia_externa,
                                      resposta, instante)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (op_id, numero, tipo, origem, destino, valor_centavos,
                 moeda_origem, moeda_destino, taxa_milionesimos,
                 valor_destino_centavos, sistema_externo_id, referencia_externa,
                 json.dumps(resposta), instante),
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
                       valor_centavos, valor_destino_centavos,
                       sistema_externo_id, resposta, instante
                FROM operacao
                WHERE conta_origem_id = %(id)s OR conta_destino_id = %(id)s
                ORDER BY numero
                """,
                {"id": identificador},
            )
            return cursor.fetchall()

    def total_pelo_log_por_moeda(self) -> dict[str, int]:
        """O lado direito da auditoria (RF-14): quanto dinheiro devia existir.

        Entra dinheiro ao criar conta, depositar, pagar juros e devolver uma
        transferência externa rejeitada; sai ao sacar e ao enviar para outro
        banco; a transferência é neutra. O câmbio tira numa moeda e põe noutra.

        Não olha para os saldos — é por ser independente deles que compará-lo
        com a soma dos saldos verifica alguma coisa. Da tabela `conta` só lê a
        moeda, que nunca muda depois de a conta abrir.
        """
        with self._conexao.cursor() as cursor:
            cursor.execute(
                """
                SELECT moeda, COALESCE(SUM(delta), 0)::BIGINT AS total FROM (
                    SELECT c.moeda, o.valor_centavos AS delta
                      FROM operacao o JOIN conta c ON c.id = o.conta_destino_id
                     WHERE o.tipo IN %(entram)s
                    UNION ALL
                    SELECT c.moeda, -o.valor_centavos
                      FROM operacao o JOIN conta c ON c.id = o.conta_origem_id
                     WHERE o.tipo IN %(saem)s
                    UNION ALL
                    SELECT o.moeda_origem, -o.valor_centavos
                      FROM operacao o WHERE o.tipo = 'cambio'
                    UNION ALL
                    SELECT o.moeda_destino, o.valor_destino_centavos
                      FROM operacao o WHERE o.tipo = 'cambio'
                ) AS movimentos
                GROUP BY moeda
                """,
                {"entram": TIPOS_QUE_ACRESCENTAM, "saem": TIPOS_QUE_RETIRAM},
            )
            return {linha["moeda"]: linha["total"] for linha in cursor.fetchall()}
