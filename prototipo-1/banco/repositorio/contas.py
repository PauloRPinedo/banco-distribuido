"""Leitura e escrita da tabela `conta`.

Não conhece regras de negócio: traduz linhas em `Conta` e `Conta` em linhas.
Quem decide se uma operação é válida é o domínio.
"""

from banco.dominio.contas import Conta
from banco.dominio.erros import ContaDuplicada


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
                    "SELECT id, saldo_centavos, criada_em FROM conta "
                    "WHERE id = %s FOR UPDATE",
                    (identificador,),
                )
                linha = cursor.fetchone()
                if linha is not None:
                    encontradas[linha["id"]] = Conta(
                        linha["id"], linha["saldo_centavos"], linha["criada_em"])
        return encontradas

    def obter(self, identificador: str) -> Conta | None:
        """Leitura sem lock, para as consultas."""
        with self._conexao.cursor() as cursor:
            cursor.execute(
                "SELECT id, saldo_centavos, criada_em FROM conta WHERE id = %s",
                (identificador,),
            )
            linha = cursor.fetchone()
        if linha is None:
            return None
        return Conta(linha["id"], linha["saldo_centavos"], linha["criada_em"])

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
                    "INSERT INTO conta (id, saldo_centavos, criada_em) "
                    "VALUES (%s, %s, %s)",
                    (conta.id, conta.saldo_centavos, conta.criada_em),
                )
        except psycopg2.errors.UniqueViolation:
            raise ContaDuplicada(f"a conta {conta.id!r} já existe") from None

    def atualizar(self, conta: Conta) -> None:
        with self._conexao.cursor() as cursor:
            cursor.execute(
                "UPDATE conta SET saldo_centavos = %s WHERE id = %s",
                (conta.saldo_centavos, conta.id),
            )

    def total_dos_saldos_centavos(self) -> int:
        """O lado esquerdo da auditoria (RF-14): quanto dinheiro existe agora."""
        with self._conexao.cursor() as cursor:
            # O cast é preciso: SUM() sobre BIGINT devolve `numeric`, que chega
            # ao Python como Decimal. Devolver um Decimal daqui espalharia-o
            # por toda a camada de cima, onde só devem circular inteiros.
            cursor.execute(
                "SELECT COALESCE(SUM(saldo_centavos), 0)::BIGINT AS total FROM conta")
            return cursor.fetchone()["total"]
