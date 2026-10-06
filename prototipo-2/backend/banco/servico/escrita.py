"""Toda a escrita do banco passa por aqui, e só por aqui.

Este serviço decide **se** uma escrita pode acontecer; quem a faz acontecer é o
`No` (`banco/cluster/no.py`): grava-a no log, replica-a, espera pela maioria e
manda o `Aplicador` aplicá-la às tabelas. A ordem completa:

0. **Dono** — as contas de onde sai dinheiro são de quem pede? (aqui)
1. **Já aplicada?** — devolve-se a resposta guardada (no `No`)
2. **Validar** contra o estado atual, com o instante da operação (aqui, chamado
   pelo `No` dentro do seu lock de escrita)
3. **Gravar no log** deste nó, de forma durável (no `No`)
4. **Replicar e esperar pela maioria** — sem ela, `sem_quorum` (no `No`)
5. **Confirmar** e **aplicar** às tabelas (no `No`, pelo `Aplicador`)
6. **Responder**
"""

import uuid

from banco.autenticacao import calcular_hash
from banco.cluster.operacoes_de_sistema import RegistarTaxa, RegistarUsuario
from banco.dominio.contas import Livro
from banco.dominio.operacoes import Operacao
from banco.repositorio import RepositorioContas, RepositorioUsuarios
from banco.servico.erros import EmailDuplicado, SemPermissao


class ServicoDeEscrita:

    def __init__(self, no, obter_conexao) -> None:
        self._no = no
        self._obter_conexao = obter_conexao

    def ja_aplicada(self, op_id: str) -> dict | None:
        """A resposta guardada deste op_id, sem aplicar nada."""
        return self._no.aplicador.resposta_guardada(op_id)

    def aplicar(self, operacao: Operacao, op_id: str, usuario_id: str | None = None,
                exige_dono: tuple[str, ...] = ()) -> dict:
        """Aplica uma operação de dinheiro e devolve o que o cliente vai receber.

        `exige_dono` são as contas que só o seu dono pode movimentar (a origem
        de um saque ou de uma transferência); um depósito não exige nada.
        """
        # 0. Lê-se sem lock: o dono de uma conta nunca muda. Vem antes da
        # deduplicação, para que repetir o op_id de outra pessoa não devolva a
        # resposta dela.
        if exige_dono:
            with self._ligacao() as conexao:
                contas = RepositorioContas(conexao)
                for identificador in exige_dono:
                    conta = contas.obter(identificador)
                    if conta is not None and conta.dono != usuario_id:
                        raise SemPermissao(f"a conta {identificador!r} não te pertence")

        return self._no.executar(
            op_id, operacao, verificar=lambda instante: self._validar(operacao, instante))

    def registar_usuario(self, nome: str, email: str, senha: str) -> dict:
        """O utilizador também passa pelo log: senão só existiria no primário,
        e depois de um failover não conseguiria entrar.

        O id e o hash (com o sal aleatório) calculam-se aqui, no primário, e
        vão nos dados da entrada: as réplicas guardam exatamente os mesmos.
        """
        operacao = RegistarUsuario(str(uuid.uuid4()), nome, email, calcular_hash(senha))

        def verificar(_instante: float) -> None:
            with self._ligacao() as conexao:
                if RepositorioUsuarios(conexao).procurar_por_email(email) is not None:
                    raise EmailDuplicado(f"o email {email!r} já está registado")

        return self._no.executar(f"registo-{operacao.id}", operacao, verificar)

    def registar_taxa(self, moeda_origem: str, moeda_destino: str,
                      taxa_milionesimos: int) -> dict:
        """Uma taxa nova vale a partir do instante da entrada, igual em todos os nós."""
        operacao = RegistarTaxa(moeda_origem, moeda_destino, taxa_milionesimos)
        return self._no.executar(f"taxa-{uuid.uuid4().hex[:24]}", operacao)

    def _validar(self, operacao: Operacao, instante: float) -> None:
        """As regras do domínio contra o estado atual das contas tocadas."""
        with self._ligacao() as conexao:
            contas = RepositorioContas(conexao)
            livro = Livro()
            for identificador in operacao.contas_tocadas():
                conta = contas.obter(identificador)
                if conta is not None:
                    livro.contas[identificador] = conta
                    livro.extratos[identificador] = []
            operacao.validar(livro, instante)

    def _ligacao(self):
        return _Ligacao(self._obter_conexao)


class _Ligacao:
    """Uma ligação de leitura que se fecha sempre, mesmo com erro."""

    def __init__(self, obter_conexao) -> None:
        self._obter_conexao = obter_conexao

    def __enter__(self):
        self._conexao = self._obter_conexao()
        return self._conexao

    def __exit__(self, *_) -> None:
        self._conexao.close()
