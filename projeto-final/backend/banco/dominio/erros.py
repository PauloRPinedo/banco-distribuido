"""Erros que o banco levanta ao recusar uma operação.

Existe uma raiz única para a camada HTTP traduzir tudo num só sítio: cada erro
carrega o seu código e o seu estado, e a rota não precisa de saber quais
existem. Acrescentar um erro novo não obriga a mexer no servidor.

Os códigos e estados são os da tabela da secção 6 de docs/SPECS.md.
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


class SaldoInsuficiente(ErroDoBanco):
    """A operação deixaria o saldo negativo (RF-06)."""

    codigo = "saldo_insuficiente"
    estado_http = 422
