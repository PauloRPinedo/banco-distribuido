"""Peças que mais de um ficheiro de testes precisa.

Existe por duas razões concretas:

- **construir um `No` num sítio só.** A assinatura mudou uma vez (quando o
  armazém passou a ser injetado) e obrigou a tocar em cinco ficheiros. Da
  próxima vez toca-se aqui.
- **esperar por uma condição, nunca por um relógio.** O ROADMAP proíbe `sleep`
  de valor arbitrário nos testes: passa numa máquina e falha noutra, e quando
  falha não se sabe se o erro é do código ou do tempo.
"""

import time

from banco.cluster.no import No
from banco.persistencia.armazem_memoria import ArmazemEmMemoria


def criar_no_de_teste(caso, armazem=None, identificador="A"):
    """Um nó sobre memória, já com o `fechar` registado no `caso`."""
    no = No(identificador, armazem if armazem is not None else ArmazemEmMemoria())
    caso.addCleanup(no.fechar)
    return no


def reiniciar(caso, no):
    """Simula uma queda e um arranque: nó novo, o mesmo armazém em memória.

    É o equivalente a matar o processo e voltar a subi-lo, e só funciona porque
    o armazém em memória é a própria coisa guardada — `fechar()` não lhe mexe.
    Um armazém em ficheiro ou em PostgreSQL tem de ser **reaberto**, não
    reutilizado; quem precisa disso usa o `ContratoDoNo` de `teste_no.py`.
    """
    no.fechar()
    return criar_no_de_teste(caso, no.armazem, no.id)


def esperar_ate(condicao, limite=2.0, intervalo=0.01):
    """Espera que `condicao()` seja verdadeira, até `limite` segundos.

    Devolve `True` se aconteceu, `False` se esgotou o tempo — quem chama decide
    se isso é uma falha, e a mensagem sai do teste, não daqui.
    """
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(intervalo)
    return condicao()


def porta_livre() -> int:
    """Uma porta que o sistema diz estar livre agora.

    Há uma corrida teórica entre fechar o socket e o nó voltar a ligar-se. Vive-se
    com ela: a alternativa é fixar portas, e aí a suíte falha sempre que alguém
    tem o servidor da demonstração a correr.
    """
    import socket
    with socket.socket() as tomada:
        tomada.bind(("127.0.0.1", 0))
        return tomada.getsockname()[1]


class ClusterDeTeste:
    """Os nós e os servidores que os servem, para se poderem derrubar.

    Fechar um `No` pára o seu ciclo de replicação mas **não** fecha o socket: o
    servidor HTTP continua a responder a `/interno/replicar`, e o primário
    continua a contá-lo para o quórum. Um teste que só chame `no.fechar()` está a
    testar um nó vivo que finge estar morto — e passaria por motivo errado.
    """

    def __init__(self, nos, servidores):
        self.nos = nos
        self._servidores = servidores
        self._derrubados = set()

    def __iter__(self):
        return iter(self.nos)

    def __len__(self):
        return len(self.nos)

    def obter(self, id_do_no):
        return next(no for no in self.nos if no.id == id_do_no)

    def porta_de(self, id_do_no):
        return self._servidores[id_do_no][0].server_address[1]

    def outros(self, no):
        return [outro for outro in self.nos if outro is not no]

    def derrubar(self, no):
        """Tira o nó do ar por inteiro: ciclo, socket e tudo.

        É o equivalente em processo ao `kill -9` da demonstração — com uma
        diferença honesta, que é a de o armazém em memória sobreviver, e é
        justamente isso que permite ao nó voltar.
        """
        if no.id in self._derrubados:
            return
        self._derrubados.add(no.id)
        no.fechar()
        servidor, thread = self._servidores[no.id]
        servidor.shutdown()
        thread.join(timeout=5)
        servidor.server_close()


def criar_cluster_de_teste(caso, quantidade=3, semente=42, heartbeat_ms=30,
                           timeout_eleicao_ms=(120, 240),
                           timeout_replicacao_ms=200,
                           encaminhar_escritas=False):
    """N nós a falar por HTTP a sério, em 127.0.0.1, já com limpeza registada.

    Os tempos são muito mais curtos que os da demonstração (150 ms / [800, 1500])
    de propósito: os testes exercitam o **protocolo**, e esperar 1,5 s por cada
    eleição tornaria a suíte inutilizável. As proporções mantêm-se — o heartbeat
    continua a caber quatro vezes no timeout mais curto, que é a relação que a
    configuração valida.

    Devolve a lista de nós. Nenhum é primário à partida: arrancam todos como
    réplica (SPECS 4.2) e elegem um entre si.
    """
    import threading

    from banco.cluster.configuracao import ConfiguracaoDoCluster
    from banco.interface.servidor_http import criar_servidor
    from banco.persistencia.armazem_memoria import ArmazemEmMemoria

    ids = [chr(ord("A") + i) for i in range(quantidade)]
    portas = {id_: porta_livre() for id_ in ids}
    configuracao = ConfiguracaoDoCluster.de_dados({
        "nos": [{"id": id_, "endereco": "127.0.0.1", "porta": portas[id_]}
                for id_ in ids],
        "heartbeat_ms": heartbeat_ms,
        "timeout_eleicao_ms": list(timeout_eleicao_ms),
        "timeout_replicacao_ms": timeout_replicacao_ms,
        "semente": semente,
    })

    nos = []
    servidores = {}
    for id_ in ids:
        no = No(id_, ArmazemEmMemoria(), configuracao)
        servidor = criar_servidor(no, "127.0.0.1", portas[id_], "*",
                                  encaminhar_escritas)
        thread = threading.Thread(target=servidor.serve_forever, args=(0.005,),
                                  daemon=True)
        thread.start()
        no.arrancar()
        nos.append(no)
        servidores[id_] = (servidor, thread)

    cluster = ClusterDeTeste(nos, servidores)
    # Derrubar tudo no fim, na ordem certa. Idempotente, por isso não faz mal a
    # um nó que o teste já tenha derrubado.
    caso.addCleanup(lambda: [cluster.derrubar(no) for no in nos])
    return cluster


def esperar_por_primario(caso, nos, limite=5.0):
    """Espera que exatamente um nó se declare primário, e devolve-o.

    Ignora os nós que já não respondem: um nó derrubado pode continuar a
    lembrar-se de que era primário, e contá-lo daria um falso "dois primários".
    """
    vivos = [no for no in nos if no.replicador is None or no.replicador._thread]

    def ha_primario():
        return len(_primarios(vivos)) == 1

    if not esperar_ate(ha_primario, limite):
        papeis = {no.id: no.estado_do_no()["papel"] for no in vivos}
        caso.fail(f"não convergiu para um primário em {limite}s: {papeis}")
    return _primarios(vivos)[0]


def _primarios(nos):
    return [no for no in nos if no.estado_do_no()["papel"] == "primário"]
