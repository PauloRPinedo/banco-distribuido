"""Concorrência: ordem total dos locks, corridas e leitura consistente.

Subfase 1.5. Nenhum destes testes usa `sleep` de valor arbitrário: espera-se por
uma condição com limite de tempo, porque um `sleep(2)` passa na máquina de quem
o escreveu e falha na do colega.
"""

import tempfile
import threading
import unittest
from pathlib import Path

from banco.cluster.concorrencia import RegistoDeLocks
from banco.cluster.no import No
from banco.persistencia.armazem_memoria import ArmazemEmMemoria
from banco.dominio.erros import ErroDoBanco, SaldoInsuficiente
from banco.dominio.operacoes import CriarConta, Saque, Transferencia

LIMITE_SEGUNDOS = 10


def _correr_em_paralelo(alvos):
    """Arranca as funções ao mesmo tempo e devolve as que não terminaram.

    A barreira força a sobreposição real: sem ela, a primeira thread costuma
    acabar antes de a última arrancar, e a corrida que se quer provocar nunca
    acontece.
    """
    barreira = threading.Barrier(len(alvos))
    erros: list[BaseException] = []

    def envolver(alvo):
        def correr():
            barreira.wait()
            try:
                alvo()
            except ErroDoBanco:
                pass
            except BaseException as erro:  # noqa: BLE001 - o teste quer vê-lo
                erros.append(erro)
        return correr

    threads = [threading.Thread(target=envolver(alvo)) for alvo in alvos]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(LIMITE_SEGUNDOS)

    return [t for t in threads if t.is_alive()], erros


class TesteRegistoDeLocks(unittest.TestCase):

    def teste_o_mesmo_lock_e_devolvido_para_a_mesma_conta(self):
        registo = RegistoDeLocks()

        self.assertIs(registo._lock_de("alice"), registo._lock_de("alice"))

    def teste_conta_repetida_na_lista_nao_bloqueia_a_si_propria(self):
        # sorted(set(...)) tem de eliminar o duplicado, senão o segundo acquire
        # do mesmo lock não-reentrante bloquearia para sempre.
        registo = RegistoDeLocks()

        with registo.adquirir(["alice", "alice"]):
            pass

    def teste_locks_sao_libertados_mesmo_com_excecao(self):
        registo = RegistoDeLocks()

        try:
            with registo.adquirir(["alice"]):
                raise RuntimeError("falha a meio")
        except RuntimeError:
            pass

        with registo.adquirir(["alice"]):
            pass


class BaseComNo(unittest.TestCase):

    def setUp(self):
        # Em memória: estes testes medem contenção de locks, e um fsync por
        # operação em disco tornaria a suíte lenta sem exercitar nada de novo —
        # a durabilidade é o assunto de teste_no.py e teste_armazem.py.
        self.no = No("A", ArmazemEmMemoria())
        self.addCleanup(self.no.fechar)


class TesteDeadlock(BaseComNo):

    def teste_transferencias_cruzadas_nao_bloqueiam(self):
        # alice->bob e bob->alice ao mesmo tempo. Sem a ordem total dos locks,
        # cada thread segura um lock e espera pelo outro, para sempre.
        self.no.executar("criar-a", CriarConta("alice", 100_000))
        self.no.executar("criar-b", CriarConta("bob", 100_000))

        def ida(n):
            return lambda: self.no.executar(f"ida-{n}",
                                            Transferencia("alice", "bob", 10))

        def volta(n):
            return lambda: self.no.executar(f"volta-{n}",
                                            Transferencia("bob", "alice", 10))

        alvos = [f(n) for n in range(50) for f in (ida, volta)]
        presas, erros = _correr_em_paralelo(alvos)

        self.assertEqual(presas, [], "houve threads que não terminaram")
        self.assertEqual(erros, [])

    def teste_transferencias_cruzadas_nao_mudam_o_total(self):
        self.no.executar("criar-a", CriarConta("alice", 100_000))
        self.no.executar("criar-b", CriarConta("bob", 100_000))
        antes = self.no.auditoria()["total_centavos"]

        alvos = []
        for n in range(50):
            alvos.append(lambda n=n: self.no.executar(
                f"ida-{n}", Transferencia("alice", "bob", 10)))
            alvos.append(lambda n=n: self.no.executar(
                f"volta-{n}", Transferencia("bob", "alice", 10)))
        _correr_em_paralelo(alvos)

        self.assertEqual(self.no.auditoria()["total_centavos"], antes)


class TesteCorridaNaMesmaConta(BaseComNo):

    def teste_saldo_nunca_fica_negativo(self):
        # 100 threads a sacar 1 de um saldo de 50: exatamente 50 podem passar.
        self.no.executar("criar", CriarConta("alice", 50))

        def sacar(n):
            return lambda: self.no.executar(f"saque-{n}", Saque("alice", 1))

        _correr_em_paralelo([sacar(n) for n in range(100)])

        self.assertEqual(self.no.saldo("alice")["saldo_centavos"], 0)

    def teste_nenhuma_operacao_se_perde(self):
        self.no.executar("criar", CriarConta("alice", 100))
        aceites: list[int] = []
        trava = threading.Lock()

        def sacar(n):
            def correr():
                try:
                    self.no.executar(f"saque-{n}", Saque("alice", 1))
                except SaldoInsuficiente:
                    return
                with trava:
                    aceites.append(n)
            return correr

        _correr_em_paralelo([sacar(n) for n in range(100)])

        # Cada saque aceite tem de aparecer no saldo: 100 - aceites.
        self.assertEqual(self.no.saldo("alice")["saldo_centavos"],
                         100 - len(aceites))
        self.assertEqual(len(aceites), 100)


class TesteLeituraConsistente(BaseComNo):

    def teste_auditoria_nunca_ve_dinheiro_a_menos(self):
        # RF-07. Uma leitura feita entre o débito e o crédito de uma
        # transferência veria dinheiro desaparecido, se não fosse serializada.
        self.no.executar("criar-a", CriarConta("alice", 100_000))
        self.no.executar("criar-b", CriarConta("bob", 100_000))
        esperado = self.no.auditoria()["total_centavos"]
        vistos: list[int] = []
        parar = threading.Event()

        def ler():
            while not parar.is_set():
                vistos.append(self.no.auditoria()["total_centavos"])

        def transferir(n):
            return lambda: self.no.executar(
                f"transf-{n}", Transferencia("alice", "bob", 25))

        leitor = threading.Thread(target=ler)
        leitor.start()
        try:
            _correr_em_paralelo([transferir(n) for n in range(100)])
        finally:
            parar.set()
            leitor.join(LIMITE_SEGUNDOS)

        self.assertGreater(len(vistos), 0, "o leitor não chegou a ler nada")
        self.assertEqual(set(vistos), {esperado})


if __name__ == "__main__":
    unittest.main()
