"""Erros que o banco levanta ao recusar uma operação.

Existe uma raiz única para a camada HTTP traduzir tudo num só sítio: cada erro
carrega o seu código e o seu estado, e a rota não precisa de saber quais
existem. Acrescentar um erro novo não obriga a mexer no servidor.
"""


class ErroDoBanco(Exception):
    """Raiz de tudo o que o banco recusa por regra."""

    codigo: str = "erro_interno"
    estado_http: int = 500

    def __init__(self, mensagem: str) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem

    def para_json(self) -> dict[str, str]:
        return {"erro": self.codigo, "mensagem": self.mensagem}


class ValorInvalido(ErroDoBanco):
    """Valor ausente, não positivo, mal formado, ou operação sem sentido."""

    codigo = "valor_invalido"
    estado_http = 400


class ContaInexistente(ErroDoBanco):
    codigo = "conta_inexistente"
    estado_http = 404


class ContaDuplicada(ErroDoBanco):
    codigo = "conta_duplicada"
    estado_http = 409


class EmailDuplicado(ErroDoBanco):
    """Um segundo utilizador com o mesmo email. Como a `ContaDuplicada`, é a
    base (`UNIQUE`) que o garante; isto só dá um 409 limpo."""

    codigo = "email_duplicado"
    estado_http = 409


class SaldoInsuficiente(ErroDoBanco):
    """A operação deixaria o saldo negativo (RF-06)."""

    codigo = "saldo_insuficiente"
    estado_http = 422


class MoedasDiferentes(ErroDoBanco):
    """Uma transferência simples entre contas de moedas diferentes (RF-19).

    Tem de ser um câmbio, com taxa; mover centavos de BRL para uma conta em
    USD sem conversão criava ou destruía dinheiro.
    """

    codigo = "moedas_diferentes"
    estado_http = 409


class ContaBloqueada(ErroDoBanco):
    """Um prazo fixo antes do vencimento não deixa sair dinheiro (RN-12)."""

    codigo = "conta_bloqueada"
    estado_http = 409
