"""As recusas do protocolo.

Herdam de `ErroDoBanco` para saírem pelo mesmo tratador e com a mesma forma
`{"erro", "mensagem"}` que o resto da API. O balanceador lê duas delas:
`nao_sou_primario` (409, com o endereço do primário provável) e as 503.
"""

from banco.dominio.erros import ErroDoBanco


class NaoSouPrimario(ErroDoBanco):
    """Este nó é réplica. Diz, se souber, quem é o primário."""

    codigo = "nao_sou_primario"
    estado_http = 409

    def __init__(self, mensagem: str, primario_provavel: str | None = None) -> None:
        super().__init__(mensagem)
        self.primario_provavel = primario_provavel

    def para_json(self) -> dict:
        return {**super().para_json(), "primario_provavel": self.primario_provavel}


class SemQuorum(ErroDoBanco):
    """A escrita não chegou à maioria a tempo. Repetir com o mesmo `op_id`.

    A entrada pode ficar gravada no log por confirmar e vir a ser confirmada
    mais tarde; é por isso que a repetição tem de levar o mesmo `op_id`.
    """

    codigo = "sem_quorum"
    estado_http = 503


class SomenteLeitura(ErroDoBanco):
    """O primário não fala com a maioria há mais de um timeout de eleição."""

    codigo = "somente_leitura"
    estado_http = 503


class ParticaoSimulada(ErroDoBanco):
    """Mensagem descartada por uma partição injetada com /admin/falha."""

    codigo = "particao_simulada"
    estado_http = 503


class ArmazemIndisponivel(ErroDoBanco):
    """A base do nó não respondeu. Sem log durável não se confirma nada."""

    codigo = "armazem_indisponivel"
    estado_http = 503
