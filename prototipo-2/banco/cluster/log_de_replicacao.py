"""O log visto pelo protocolo: índices, epochs e o prefixo confirmado.

É uma camada fina por cima do armazém. Existe para separar duas perguntas que se
confundem com facilidade:

- **o armazém** sabe guardar e devolver entradas;
- **este módulo** sabe quais entradas podem entrar, quais têm de sair, e até onde
  o log está confirmado.

A regra que não se negoceia está em `truncar_divergentes`: nunca se apaga abaixo
do `indice_commit`. Uma entrada confirmada já foi prometida a um cliente, e
apagá-la é dinheiro a desaparecer — a única coisa que este projeto inteiro existe
para impedir.
"""

import threading

from banco.persistencia.armazem import ArmazemDeLog
from banco.persistencia.entrada import EntradaDeLog


class LogDeReplicacao:

    def __init__(self, armazem: ArmazemDeLog) -> None:
        self._armazem = armazem
        self._lock = threading.RLock()
        self._ultimo_indice = armazem.ultimo_indice()
        self._ultimo_epoch = armazem.ultimo_epoch()
        self._indice_commit = armazem.ler_estado().indice_commit

    # ------------------------------------------------------------- o que sei

    @property
    def ultimo_indice(self) -> int:
        with self._lock:
            return self._ultimo_indice

    @property
    def ultimo_epoch(self) -> int:
        with self._lock:
            return self._ultimo_epoch

    @property
    def indice_commit(self) -> int:
        with self._lock:
            return self._indice_commit

    def ler_desde(self, indice: int) -> list[EntradaDeLog]:
        return self._armazem.ler_desde(indice)

    def epoch_em(self, indice: int) -> int:
        """O epoch da entrada nesse índice; 0 se não existir ou se for o zero.

        Devolve 0 em vez de None porque quem pergunta é o protocolo, e ali o
        índice 0 significa "antes do princípio do log" — um caso normal, não uma
        ausência a tratar.
        """
        if indice <= 0:
            return 0
        with self._lock:
            return self._armazem.epoch_em(indice) or 0

    def corresponde(self, indice_anterior: int, epoch_anterior: int) -> bool:
        """O meu log encaixa no que o líder diz ter antes desta entrada?

        É a verificação de consistência da replicação: se o par concorda comigo no
        índice e no epoch da entrada anterior, então concordamos em tudo o que
        vem antes — e daí para trás não é preciso comparar nada.
        """
        with self._lock:
            if indice_anterior == 0:
                return True
            if indice_anterior > self._ultimo_indice:
                return False
            return self._armazem.epoch_em(indice_anterior) == epoch_anterior

    # -------------------------------------------------------- o que acontece

    def acrescentar(self, entrada: EntradaDeLog) -> None:
        """Escreve uma entrada própria. Só o primário chama isto."""
        with self._lock:
            self._armazem.acrescentar(entrada)
            self._ultimo_indice = entrada.indice
            self._ultimo_epoch = entrada.epoch

    def acrescentar_do_lider(self, entradas: list[EntradaDeLog]) -> None:
        """Aceita um lote do líder, truncando o que diverge.

        As entradas que já tenho iguais não se reescrevem: repetir um índice
        chocaria com a chave primária do armazém. As que tenho **diferentes**
        têm de sair antes, e é aí que a regra do `indice_commit` se aplica.
        """
        if not entradas:
            return
        with self._lock:
            primeira = entradas[0].indice
            if primeira <= self._ultimo_indice:
                self.truncar_divergentes(primeira)
            novas = [e for e in entradas if e.indice > self._ultimo_indice]
            if not novas:
                return
            self._armazem.acrescentar_muitas(novas)
            self._ultimo_indice = novas[-1].indice
            self._ultimo_epoch = novas[-1].epoch

    def truncar_divergentes(self, desde: int) -> None:
        """Apaga do índice `desde` para a frente.

        Levanta se isso apagasse algo confirmado. Não é uma defesa contra o
        protocolo — o protocolo garante que não acontece — é a rede que apanha um
        erro **nosso** antes de ele virar dinheiro perdido, e num sítio onde a
        mensagem diz logo o que se passou.
        """
        with self._lock:
            if desde <= self._indice_commit:
                raise ValueError(
                    f"truncar a partir de {desde} apagaria entradas confirmadas "
                    f"(commit está em {self._indice_commit}): isto é um erro de "
                    f"protocolo, não uma situação normal")
            if desde > self._ultimo_indice:
                return
            self._armazem.truncar_a_partir_de(desde)
            self._ultimo_indice = self._armazem.ultimo_indice()
            self._ultimo_epoch = self._armazem.ultimo_epoch()

    def confirmar_ate(self, indice: int) -> None:
        """Avança o prefixo confirmado. Nunca recua, nunca passa do que tenho.

        O limite pelo `ultimo_indice` importa numa réplica: o líder anuncia o seu
        `indice_commit`, que pode estar à frente do que esta réplica já recebeu.
        Confirmar o que ainda não se tem seria dizer que se guardou o que não se
        guardou.
        """
        with self._lock:
            alvo = min(indice, self._ultimo_indice)
            if alvo <= self._indice_commit:
                return
            self._armazem.gravar_commit(alvo)
            self._indice_commit = alvo
