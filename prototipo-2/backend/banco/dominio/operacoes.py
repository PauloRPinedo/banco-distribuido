"""As operações do banco, puras e determinísticas.

Cada operação sabe três coisas: que contas toca, se é válida, e como se aplica.
Separar `validar` de `aplicar` não é estilo — é a ordem obrigatória de uma
escrita: valida-se **antes** de gravar no log, para nunca se registar uma
operação que vai ser recusada.

`validar` recebe o instante da operação porque há regras que dependem dele (um
prazo fixo só deixa sair dinheiro depois de vencer). O instante vem de fora —
quem o decide é o primário, e é o mesmo que viaja no log — e o domínio nunca
lê o relógio: três nós a reaplicar a mesma entrada têm de chegar ao mesmo sítio.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import ClassVar

from banco.dominio.contas import Conta, Livro, Movimento, validar_id
from banco.dominio.dinheiro import MILIONESIMOS, MOEDAS, converter, formatar
from banco.dominio.erros import (ContaBloqueada, ContaDuplicada,
                                 MoedasDiferentes, SaldoInsuficiente,
                                 ValorInvalido)

CRIAR_CONTA = "criar_conta"
DEPOSITO = "deposito"
SAQUE = "saque"
TRANSFERENCIA = "transferencia"
CAMBIO = "cambio"
JUROS = "juros"
TRANSFERENCIA_EXTERNA = "transferencia_externa"
DESFECHO_EXTERNO = "desfecho_externo"

CORRENTE = "corrente"
POUPANCA = "poupanca"
PRAZO_FIXO = "prazo_fixo"
PRODUTOS = (CORRENTE, POUPANCA, PRAZO_FIXO)

SEGUNDOS_POR_DIA = 24 * 60 * 60
SEGUNDOS_POR_ANO = 365 * SEGUNDOS_POR_DIA


class Operacao:
    """Base das operações."""

    tipo: ClassVar[str]

    def contas_tocadas(self) -> tuple[str, ...]:
        """Ids das contas envolvidas, **já ordenados**.

        A ordem total dos locks nasce aqui, e não no ponto de uso. Quem adquire
        os locks percorre esta tupla e pronto: não tem de se lembrar da regra,
        e por isso não a pode esquecer. É o que torna impossível o deadlock de
        alice->bob contra bob->alice.
        """
        raise NotImplementedError

    def validar(self, livro: Livro, instante: float) -> None:
        raise NotImplementedError

    def aplicar(self, livro: Livro, indice: int, instante: float) -> dict:
        raise NotImplementedError

    def para_dados(self) -> dict:
        """Argumentos da operação, como vão para o campo `dados` do log."""
        raise NotImplementedError


def _validar_valor(valor_centavos: int) -> None:
    if not isinstance(valor_centavos, int) or isinstance(valor_centavos, bool):
        raise ValorInvalido("o valor tem de ser um inteiro de centavos")
    if valor_centavos <= 0:
        raise ValorInvalido("o valor tem de ser maior do que zero")


def _exigir_que_pode_sair(conta: Conta, instante: float) -> None:
    """RN-12: de um prazo fixo não sai dinheiro antes do vencimento."""
    if conta.produto == PRAZO_FIXO and instante < conta.vence_em:
        dia = datetime.fromtimestamp(conta.vence_em, timezone.utc).date().isoformat()
        raise ContaBloqueada(f"{conta.id} é um prazo fixo e só vence a {dia}")


def _exigir_saldo(conta: Conta, valor_centavos: int) -> None:
    if conta.saldo_centavos < valor_centavos:
        raise SaldoInsuficiente(
            f"{conta.id} tem {formatar(conta.saldo_centavos, conta.moeda)} e a "
            f"operação pede {formatar(valor_centavos, conta.moeda)}")


@dataclass(frozen=True)
class CriarConta(Operacao):
    """RF-01, e o produto da conta (RF-23/24): corrente, poupança ou prazo fixo.

    A poupança rende desde o dia em que abre. O prazo fixo rende de uma vez,
    no vencimento, e até lá não deixa sair dinheiro.
    """

    tipo: ClassVar[str] = CRIAR_CONTA
    conta: str
    saldo_inicial_centavos: int
    dono: str | None = None
    moeda: str = "BRL"
    produto: str = CORRENTE
    taxa_juros_milionesimos: int | None = None
    prazo_dias: int | None = None

    def contas_tocadas(self) -> tuple[str, ...]:
        return (self.conta,)

    def validar(self, livro: Livro, instante: float) -> None:
        validar_id(self.conta)
        if self.saldo_inicial_centavos < 0:
            raise ValorInvalido("o saldo inicial não pode ser negativo")
        if self.moeda not in MOEDAS:
            raise ValorInvalido(f"moeda desconhecida: {self.moeda!r} ({', '.join(MOEDAS)})")
        if self.produto not in PRODUTOS:
            raise ValorInvalido(f"produto desconhecido: {self.produto!r} ({', '.join(PRODUTOS)})")
        tem_taxa = self.taxa_juros_milionesimos is not None
        tem_prazo = self.prazo_dias is not None
        if self.produto == CORRENTE and (tem_taxa or tem_prazo):
            raise ValorInvalido("a conta corrente não tem taxa de juros nem prazo")
        if self.produto != CORRENTE and (not tem_taxa or self.taxa_juros_milionesimos <= 0):
            raise ValorInvalido(f"{self.produto} precisa de uma taxa de juros positiva")
        if self.produto == POUPANCA and tem_prazo:
            raise ValorInvalido("a poupança não tem prazo")
        if self.produto == PRAZO_FIXO and (not tem_prazo or self.prazo_dias <= 0):
            raise ValorInvalido("o prazo fixo precisa de um prazo em dias, maior do que zero")
        if livro.existe(self.conta):
            raise ContaDuplicada(f"a conta {self.conta!r} já existe")

    def aplicar(self, livro: Livro, indice: int, instante: float) -> dict:
        self.validar(livro, instante)
        conta = livro.criar(
            self.conta, self.saldo_inicial_centavos, instante, self.dono,
            moeda=self.moeda, produto=self.produto,
            taxa_juros_milionesimos=self.taxa_juros_milionesimos,
            ultimo_juros_em=instante if self.produto == POUPANCA else None,
            vence_em=(instante + self.prazo_dias * SEGUNDOS_POR_DIA
                      if self.produto == PRAZO_FIXO else None))
        livro.registar(self.conta, Movimento(
            indice, CRIAR_CONTA, self.saldo_inicial_centavos, None,
            conta.saldo_centavos, instante))
        return {"conta": self.conta, "saldo_centavos": conta.saldo_centavos,
                "moeda": conta.moeda}

    def para_dados(self) -> dict:
        return {"conta": self.conta,
                "saldo_inicial_centavos": self.saldo_inicial_centavos,
                "dono": self.dono, "moeda": self.moeda, "produto": self.produto,
                "taxa_juros_milionesimos": self.taxa_juros_milionesimos,
                "prazo_dias": self.prazo_dias}


@dataclass(frozen=True)
class Deposito(Operacao):
    tipo: ClassVar[str] = DEPOSITO
    conta: str
    valor_centavos: int

    def contas_tocadas(self) -> tuple[str, ...]:
        return (self.conta,)

    def validar(self, livro: Livro, instante: float) -> None:
        _validar_valor(self.valor_centavos)
        livro.obter(self.conta)

    def aplicar(self, livro: Livro, indice: int, instante: float) -> dict:
        self.validar(livro, instante)
        conta = livro.obter(self.conta)
        conta.saldo_centavos += self.valor_centavos
        livro.registar(self.conta, Movimento(
            indice, DEPOSITO, self.valor_centavos, None,
            conta.saldo_centavos, instante))
        return {"conta": self.conta, "saldo_centavos": conta.saldo_centavos,
                "moeda": conta.moeda}

    def para_dados(self) -> dict:
        return {"conta": self.conta, "valor_centavos": self.valor_centavos}


@dataclass(frozen=True)
class Saque(Operacao):
    tipo: ClassVar[str] = SAQUE
    conta: str
    valor_centavos: int

    def contas_tocadas(self) -> tuple[str, ...]:
        return (self.conta,)

    def validar(self, livro: Livro, instante: float) -> None:
        _validar_valor(self.valor_centavos)
        conta = livro.obter(self.conta)
        _exigir_que_pode_sair(conta, instante)
        _exigir_saldo(conta, self.valor_centavos)

    def aplicar(self, livro: Livro, indice: int, instante: float) -> dict:
        self.validar(livro, instante)
        conta = livro.obter(self.conta)
        conta.saldo_centavos -= self.valor_centavos
        livro.registar(self.conta, Movimento(
            indice, SAQUE, -self.valor_centavos, None,
            conta.saldo_centavos, instante))
        return {"conta": self.conta, "saldo_centavos": conta.saldo_centavos,
                "moeda": conta.moeda}

    def para_dados(self) -> dict:
        return {"conta": self.conta, "valor_centavos": self.valor_centavos}


@dataclass(frozen=True)
class Transferencia(Operacao):
    """Debita e credita numa só função, sem estado intermédio (RF-05).

    Não existe instante nenhum em que o dinheiro tenha saído de uma conta e
    ainda não tenha entrado na outra. É daqui, e só daqui, que vem a atomicidade
    da transferência — sem commit em duas fases, porque as duas contas estão
    sempre no mesmo nó.

    As duas contas têm de ter a mesma moeda (RF-19). Entre moedas é um
    `Cambio`, que leva a taxa consigo.
    """

    tipo: ClassVar[str] = TRANSFERENCIA
    de: str
    para: str
    valor_centavos: int

    def contas_tocadas(self) -> tuple[str, ...]:
        return tuple(sorted((self.de, self.para)))

    def validar(self, livro: Livro, instante: float) -> None:
        _validar_valor(self.valor_centavos)
        if self.de == self.para:
            raise ValorInvalido("a origem e o destino são a mesma conta")
        origem = livro.obter(self.de)
        destino = livro.obter(self.para)
        if origem.moeda != destino.moeda:
            raise MoedasDiferentes(
                f"{self.de} está em {origem.moeda} e {self.para} em {destino.moeda}; "
                "entre moedas é um câmbio (/transferencias/conversao)")
        _exigir_que_pode_sair(origem, instante)
        _exigir_saldo(origem, self.valor_centavos)

    def aplicar(self, livro: Livro, indice: int, instante: float) -> dict:
        self.validar(livro, instante)
        origem = livro.obter(self.de)
        destino = livro.obter(self.para)

        origem.saldo_centavos -= self.valor_centavos
        destino.saldo_centavos += self.valor_centavos

        livro.registar(self.de, Movimento(
            indice, TRANSFERENCIA, -self.valor_centavos, self.para,
            origem.saldo_centavos, instante))
        livro.registar(self.para, Movimento(
            indice, TRANSFERENCIA, self.valor_centavos, self.de,
            destino.saldo_centavos, instante))
        return {"de": self.de, "para": self.para, "moeda": origem.moeda,
                "saldos_centavos": {self.de: origem.saldo_centavos,
                                    self.para: destino.saldo_centavos}}

    def para_dados(self) -> dict:
        return {"de": self.de, "para": self.para,
                "valor_centavos": self.valor_centavos}


@dataclass(frozen=True)
class Cambio(Operacao):
    """Transferência entre contas de moedas diferentes (RF-20, RN-06).

    A taxa faz parte da operação, e não é lida aqui: quem a lê é o serviço,
    antes, e ela fica gravada com a operação. Assim repetir o `op_id` ou
    reaplicar o log usa a mesma taxa, e não a que estiver em vigor nesse dia.

    Cada moeda é auditada à parte: sai `valor_centavos` na moeda de origem e
    entra `converter(valor, taxa)` na de destino.
    """

    tipo: ClassVar[str] = CAMBIO
    de: str
    para: str
    valor_centavos: int
    taxa_milionesimos: int

    def contas_tocadas(self) -> tuple[str, ...]:
        return tuple(sorted((self.de, self.para)))

    def valor_destino_centavos(self) -> int:
        return converter(self.valor_centavos, self.taxa_milionesimos)

    def validar(self, livro: Livro, instante: float) -> None:
        _validar_valor(self.valor_centavos)
        if self.de == self.para:
            raise ValorInvalido("a origem e o destino são a mesma conta")
        if not isinstance(self.taxa_milionesimos, int) or self.taxa_milionesimos <= 0:
            raise ValorInvalido("a taxa de câmbio tem de ser positiva")
        origem = livro.obter(self.de)
        destino = livro.obter(self.para)
        if origem.moeda == destino.moeda:
            raise ValorInvalido(
                f"{self.de} e {self.para} estão ambas em {origem.moeda}; "
                "na mesma moeda é uma transferência")
        if self.valor_destino_centavos() <= 0:
            raise ValorInvalido("o valor convertido não chega a um centavo")
        _exigir_que_pode_sair(origem, instante)
        _exigir_saldo(origem, self.valor_centavos)

    def aplicar(self, livro: Livro, indice: int, instante: float) -> dict:
        self.validar(livro, instante)
        origem = livro.obter(self.de)
        destino = livro.obter(self.para)
        recebido = self.valor_destino_centavos()

        origem.saldo_centavos -= self.valor_centavos
        destino.saldo_centavos += recebido

        livro.registar(self.de, Movimento(
            indice, CAMBIO, -self.valor_centavos, self.para,
            origem.saldo_centavos, instante))
        livro.registar(self.para, Movimento(
            indice, CAMBIO, recebido, self.de, destino.saldo_centavos, instante))
        return {"de": self.de, "para": self.para,
                "valor_centavos": self.valor_centavos,
                "valor_destino_centavos": recebido,
                "taxa_milionesimos": self.taxa_milionesimos,
                "moedas": {self.de: origem.moeda, self.para: destino.moeda},
                "saldos_centavos": {self.de: origem.saldo_centavos,
                                    self.para: destino.saldo_centavos}}

    def para_dados(self) -> dict:
        return {"de": self.de, "para": self.para,
                "valor_centavos": self.valor_centavos,
                "taxa_milionesimos": self.taxa_milionesimos}


def juros_devidos(conta: Conta, ate: float) -> int:
    """Juros simples que a conta ganhou até `ate`, em centavos, para baixo.

    Poupança: desde o último crédito de juros. Prazo fixo: tudo de uma vez, da
    abertura ao vencimento, e só depois de vencer. Corrente: nada.
    """
    if conta.produto == POUPANCA:
        desde, ate = conta.ultimo_juros_em, ate
    elif conta.produto == PRAZO_FIXO and conta.ultimo_juros_em is None and ate >= conta.vence_em:
        desde, ate = conta.criada_em, conta.vence_em
    else:
        return 0
    segundos = max(0, int(ate - desde))
    return (conta.saldo_centavos * conta.taxa_juros_milionesimos * segundos
            // (MILIONESIMOS * SEGUNDOS_POR_ANO))


@dataclass(frozen=True)
class Juros(Operacao):
    """Credita os juros de uma conta até um instante (RN-13).

    O instante `ate` faz parte da operação: não há relógio escondido no
    domínio. Quem decide quando se pagam juros é um *tick* explícito
    (`POST /admin/juros`), e o valor é calculado do estado — por isso três nós
    que reapliquem a mesma entrada pagam o mesmo.
    """

    tipo: ClassVar[str] = JUROS
    conta: str
    ate: float

    def contas_tocadas(self) -> tuple[str, ...]:
        return (self.conta,)

    def validar(self, livro: Livro, instante: float) -> None:
        conta = livro.obter(self.conta)
        if juros_devidos(conta, self.ate) <= 0:
            raise ValorInvalido(f"{self.conta} não tem juros a creditar")

    def aplicar(self, livro: Livro, indice: int, instante: float) -> dict:
        self.validar(livro, instante)
        conta = livro.obter(self.conta)
        juros = juros_devidos(conta, self.ate)
        conta.saldo_centavos += juros
        conta.ultimo_juros_em = self.ate if conta.produto == POUPANCA else conta.vence_em
        livro.registar(self.conta, Movimento(
            indice, JUROS, juros, None, conta.saldo_centavos, instante))
        return {"conta": self.conta, "juros_centavos": juros,
                "saldo_centavos": conta.saldo_centavos, "moeda": conta.moeda,
                "ultimo_juros_em": conta.ultimo_juros_em}

    def para_dados(self) -> dict:
        return {"conta": self.conta, "ate": self.ate}


@dataclass(frozen=True)
class TransferenciaExterna(Operacao):
    """Primeiro passo de uma transferência para outro banco (RF-25).

    Debita já, e fica pendente: o dinheiro sai do banco nesta operação. O
    segundo passo é um `DesfechoExterno`, que confirma ou devolve. Nunca há
    instante nenhum em que o dinheiro esteja nos dois sítios.
    """

    tipo: ClassVar[str] = TRANSFERENCIA_EXTERNA
    de: str
    sistema_externo_id: str
    valor_centavos: int

    def contas_tocadas(self) -> tuple[str, ...]:
        return (self.de,)

    def validar(self, livro: Livro, instante: float) -> None:
        _validar_valor(self.valor_centavos)
        if not self.sistema_externo_id:
            raise ValorInvalido("falta o sistema externo de destino")
        origem = livro.obter(self.de)
        _exigir_que_pode_sair(origem, instante)
        _exigir_saldo(origem, self.valor_centavos)

    def aplicar(self, livro: Livro, indice: int, instante: float) -> dict:
        self.validar(livro, instante)
        origem = livro.obter(self.de)
        origem.saldo_centavos -= self.valor_centavos
        livro.registar(self.de, Movimento(
            indice, TRANSFERENCIA_EXTERNA, -self.valor_centavos,
            self.sistema_externo_id, origem.saldo_centavos, instante))
        return {"conta": self.de, "sistema_externo_id": self.sistema_externo_id,
                "valor_centavos": self.valor_centavos, "estado": "pendente",
                "saldo_centavos": origem.saldo_centavos, "moeda": origem.moeda}

    def para_dados(self) -> dict:
        return {"de": self.de, "sistema_externo_id": self.sistema_externo_id,
                "valor_centavos": self.valor_centavos}


@dataclass(frozen=True)
class DesfechoExterno(Operacao):
    """Segundo passo da transferência externa: confirma, ou devolve (RN-14).

    Confirmada, não mexe em saldo nenhum — o dinheiro já saiu no primeiro
    passo. Rejeitada, credita de volta o valor inteiro. A decisão do outro
    banco fica gravada aqui, com o seu próprio op_id: repetir o pedido não
    volta a perguntar, e por isso nunca devolve o que já foi confirmado.
    """

    tipo: ClassVar[str] = DESFECHO_EXTERNO
    conta: str
    valor_centavos: int
    confirmada: bool
    referencia_externa: str | None
    op_original: str

    def contas_tocadas(self) -> tuple[str, ...]:
        return (self.conta,)

    def devolvido_centavos(self) -> int:
        return 0 if self.confirmada else self.valor_centavos

    def validar(self, livro: Livro, instante: float) -> None:
        _validar_valor(self.valor_centavos)
        livro.obter(self.conta)

    def aplicar(self, livro: Livro, indice: int, instante: float) -> dict:
        self.validar(livro, instante)
        conta = livro.obter(self.conta)
        if not self.confirmada:
            conta.saldo_centavos += self.valor_centavos
            livro.registar(self.conta, Movimento(
                indice, DESFECHO_EXTERNO, self.valor_centavos, None,
                conta.saldo_centavos, instante))
        return {"conta": self.conta, "op_original": self.op_original,
                "estado": "confirmada" if self.confirmada else "rejeitada",
                "referencia_externa": self.referencia_externa,
                "valor_centavos": self.valor_centavos,
                "saldo_centavos": conta.saldo_centavos, "moeda": conta.moeda}

    def para_dados(self) -> dict:
        return {"conta": self.conta, "valor_centavos": self.valor_centavos,
                "confirmada": self.confirmada,
                "referencia_externa": self.referencia_externa,
                "op_original": self.op_original}


_POR_TIPO: dict[str, type[Operacao]] = {
    CRIAR_CONTA: CriarConta,
    DEPOSITO: Deposito,
    SAQUE: Saque,
    TRANSFERENCIA: Transferencia,
    CAMBIO: Cambio,
    JUROS: Juros,
    TRANSFERENCIA_EXTERNA: TransferenciaExterna,
    DESFECHO_EXTERNO: DesfechoExterno,
}


def de_dados(tipo: str, dados: dict) -> Operacao:
    """Reconstrói uma operação a partir de uma entrada do log."""
    classe = _POR_TIPO.get(tipo)
    if classe is None:
        raise ValorInvalido(f"tipo de operação desconhecido: {tipo!r}")
    return classe(**dados)


def total_esperado(operacoes: list[Operacao]) -> int:
    """Total em circulação calculado só a partir das operações, numa moeda só.

    É o lado direito da auditoria (F-06). Criar conta e depósito acrescentam
    dinheiro, saque retira, e a transferência é neutra por construção.

    Este cálculo não olha para os saldos: é justamente por ser independente que
    compará-lo com `Livro.total_centavos()` verifica alguma coisa. Somar duas
    vezes a mesma estrutura não auditaria nada.

    Cobre as operações cujo efeito se conhece sem olhar para o estado. Os
    juros e o câmbio dependem dele, e a auditoria por moeda da base
    (`RepositorioOperacoes.total_pelo_log_por_moeda`) é que os conta.
    """
    total = 0
    for operacao in operacoes:
        if isinstance(operacao, CriarConta):
            total += operacao.saldo_inicial_centavos
        elif isinstance(operacao, Deposito):
            total += operacao.valor_centavos
        elif isinstance(operacao, (Saque, TransferenciaExterna)):
            total -= operacao.valor_centavos
        elif isinstance(operacao, DesfechoExterno):
            total += operacao.devolvido_centavos()
    return total
