"""Leitura e escrita da tabela `conta`.

Não conhece regras de negócio: traduz linhas em `Conta` e `Conta` em linhas.
Quem decide se uma operação é válida é o domínio.
"""

from banco.dominio.contas import Conta
from banco.dominio.erros import ContaDuplicada


# `usuario_id` sai como texto: o domínio compara donos como strings, e um
# `UUID` do driver nunca seria igual ao `usuario_id` que vem no token.
_COLUNAS = ("id, usuario_id::text AS dono, saldo_centavos, criada_em, moeda, "
            "produto, taxa_juros_milionesimos, ultimo_juros_em, vence_em")


def _conta(linha: dict) -> Conta:
    return Conta(linha["id"], linha["saldo_centavos"], linha["criada_em"],
                 linha["dono"], moeda=linha["moeda"], produto=linha["produto"],
                 taxa_juros_milionesimos=linha["taxa_juros_milionesimos"],
                 ultimo_juros_em=linha["ultimo_juros_em"],
                 vence_em=linha["vence_em"])


class RepositorioContas:

    def __init__(self, conexao) -> None:
        self._conexao = conexao

    def bloquear(self, identificadores: tuple[str, ...]) -> dict[str, Conta]:
        """Bloqueia as contas pela ordem recebida e devolve as que existem.

        É o passo 2 da ordem obrigatória de uma escrita. Os identificadores chegam
        já ordenados de `Operacao.contas_tocadas()`, e é essa ordem total que
        torna impossível o deadlock de alice->bob contra bob->alice: duas
        transferências cruzadas pedem os mesmos dois locks pela mesma ordem, e
        a segunda espera em vez de cruzar com a primeira.

        Uma conta por comando, e não um `IN ... ORDER BY ... FOR UPDATE`: assim
        a ordem está à vista no código em vez de depender de o planeador do
        PostgreSQL ordenar antes de bloquear, que é verdade mas não é uma
        garantia escrita em lado nenhum.

        Devolve só as que existem. Quem falta é o domínio que recusa, com
        `ContaInexistente`, ao validar.
        """
        encontradas: dict[str, Conta] = {}
        with self._conexao.cursor() as cursor:
            for identificador in identificadores:
                cursor.execute(
                    f"SELECT {_COLUNAS} FROM conta WHERE id = %s FOR UPDATE",
                    (identificador,),
                )
                linha = cursor.fetchone()
                if linha is not None:
                    encontradas[linha["id"]] = _conta(linha)
        return encontradas

    def obter(self, identificador: str) -> Conta | None:
        """Leitura sem lock, para as consultas."""
        with self._conexao.cursor() as cursor:
            cursor.execute(
                f"SELECT {_COLUNAS} FROM conta WHERE id = %s", (identificador,))
            linha = cursor.fetchone()
        return None if linha is None else _conta(linha)

    def listar_do_dono(self, usuario_id: str) -> list[Conta]:
        """As contas de um utilizador, pela ordem em que foram abertas."""
        with self._conexao.cursor() as cursor:
            cursor.execute(
                f"SELECT {_COLUNAS} FROM conta WHERE usuario_id = %s "
                "ORDER BY criada_em, id",
                (usuario_id,),
            )
            return [_conta(linha) for linha in cursor.fetchall()]

    def inserir(self, conta: Conta) -> None:
        """Insere uma conta nova.

        `INSERT` e não `INSERT ... ON CONFLICT DO UPDATE`: com o id vindo do
        cliente, um *upsert* faria de "criar a conta alice outra vez" um
        comando que repõe o saldo da alice. Dinheiro destruído pela via mais
        simples possível, que é exatamente o que RNF-01 proíbe.

        A chave primária é a garantia verdadeira contra duas criações
        simultâneas — a validação do domínio só chega para dar um 409 limpo no
        caso sequencial.
        """
        import psycopg2.errors

        try:
            with self._conexao.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO conta (id, usuario_id, saldo_centavos, criada_em,
                                       moeda, produto, taxa_juros_milionesimos,
                                       ultimo_juros_em, vence_em)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (conta.id, conta.dono, conta.saldo_centavos, conta.criada_em,
                     conta.moeda, conta.produto, conta.taxa_juros_milionesimos,
                     conta.ultimo_juros_em, conta.vence_em),
                )
        except psycopg2.errors.UniqueViolation:
            raise ContaDuplicada(f"a conta {conta.id!r} já existe") from None

    def atualizar(self, conta: Conta) -> None:
        """Só o que uma operação pode mudar: o saldo e o último crédito de juros."""
        with self._conexao.cursor() as cursor:
            cursor.execute(
                "UPDATE conta SET saldo_centavos = %s, ultimo_juros_em = %s "
                "WHERE id = %s",
                (conta.saldo_centavos, conta.ultimo_juros_em, conta.id),
            )

    def listar_com_juros(self) -> list[str]:
        """As contas que podem ter juros a receber — o alvo do *tick* de juros."""
        with self._conexao.cursor() as cursor:
            cursor.execute("SELECT id FROM conta WHERE produto <> 'corrente' ORDER BY id")
            return [linha["id"] for linha in cursor.fetchall()]

    def total_dos_saldos_por_moeda(self) -> dict[str, int]:
        """O lado esquerdo da auditoria (RF-14): quanto dinheiro existe agora.

        Por moeda: somar reais com dólares não daria número nenhum com sentido.
        """
        with self._conexao.cursor() as cursor:
            # O cast é preciso: SUM() sobre BIGINT devolve `numeric`, que chega
            # ao Python como Decimal, e daqui para cima só circulam inteiros.
            cursor.execute(
                "SELECT moeda, COALESCE(SUM(saldo_centavos), 0)::BIGINT AS total "
                "FROM conta GROUP BY moeda")
            return {linha["moeda"]: linha["total"] for linha in cursor.fetchall()}
