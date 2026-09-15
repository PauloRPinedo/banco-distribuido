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


class SaldoInsuficiente(ErroDoBanco):
    """A operação deixaria o saldo negativo (RF-06)."""

    codigo = "saldo_insuficiente"
    estado_http = 422


class ArmazemIndisponivel(ErroDoBanco):
    """O armazém do log não conseguiu gravar: disco cheio, base em baixo.

    É 503 e não 500 de propósito. O banco está de pé e o estado está correto —
    apenas não pôde tornar a operação durável, e uma operação que não é durável
    não se aplica. O cliente pode repetir com o mesmo `op_id` quando o problema
    passar, e a distinção diz-lhe que vale a pena tentar outra vez.
    """

    codigo = "armazem_indisponivel"
    estado_http = 503


class NaoSouPrimario(ErroDoBanco):
    """Escrita enviada a uma réplica.

    Traz o primário provável no corpo para o cliente saber a quem perguntar a
    seguir, em vez de tentar os nós às cegas.
    """

    codigo = "nao_sou_primario"
    estado_http = 409

    def __init__(self, mensagem: str, primario_provavel: str | None = None) -> None:
        super().__init__(mensagem)
        self.primario_provavel = primario_provavel

    def para_json(self) -> dict[str, str]:
        corpo = super().para_json()
        if self.primario_provavel:
            corpo["primario_provavel"] = self.primario_provavel
        return corpo


class SemQuorum(ErroDoBanco):
    """A maioria não confirmou a tempo.

    A entrada fica **gravada e por confirmar**: quem decide o destino dela é o
    primário seguinte. Repetir com o mesmo `op_id` é seguro, e é o que se deve
    fazer — daí ser 503 e não um erro definitivo.
    """

    codigo = "sem_quorum"
    estado_http = 503


class SomenteLeitura(ErroDoBanco):
    """O nó não vê a maioria há mais de um timeout de eleição.

    Continua a responder a saldo, extrato e auditoria: o que sabe continua
    correto. Recusa escritas porque não tem a quem replicá-las, e confirmar uma
    escrita que só existe num nó é exatamente o que RNF-02 proíbe.
    """

    codigo = "somente_leitura"
    estado_http = 503


class ParticaoSimulada(ErroDoBanco):
    """Este nó está isolado de quem enviou a mensagem (F-10, RF-16).

    Existe só por causa da injeção de falhas. Numa partição real a mensagem
    perde-se e ninguém responde nada; aqui responde-se 503 porque um socket local
    não se pode fazer desaparecer, e do lado de quem chama o efeito é o mesmo —
    o `cliente_interno` trata ambos como "este par não contou para o quórum".
    """

    codigo = "particao_simulada"
    estado_http = 503
