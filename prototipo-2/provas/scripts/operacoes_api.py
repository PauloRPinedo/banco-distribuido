"""Operações de teste contra o Protótipo 2 a correr no compose.

    cd prototipo-2
    export SECRET_KEY=$(openssl rand -hex 32)
    docker compose up --build -d --wait
    python3 provas/scripts/operacoes_api.py

A `SECRET_KEY` tem de continuar exportada: o passo da queda faz
`docker compose kill/start`, e o nó tem de voltar com a mesma chave.

Só usa a biblioteca padrão. Fala com o painel (`:8080/api`), que reenvia ao
balanceador, que reenvia a um nó — o mesmo caminho que um navegador faz.

Cada passo diz o que se espera e confere o que veio. O registo completo, com
pedidos e respostas, fica em `provas/api/sessao.md`.

A secção 12 mata o primário com `docker compose kill` a meio de transferências
concorrentes e exige que outro nó assuma, que nada confirmado se perca, que o
dinheiro total não mude, e que o nó morto volte e as três bases fiquem iguais.
"""

import json
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BASE = "http://localhost:8080/api"
NOS = {"A": "http://localhost:8001", "B": "http://localhost:8002",
       "C": "http://localhost:8003"}
PASTA = Path(__file__).resolve().parents[1]
SAIDA = PASTA / "api" / "sessao.md"
PROTOTIPO = PASTA.parent

# Um sufixo por execução: correr o script duas vezes contra a mesma base não
# esbarra em contas e emails já criados.
SUFIXO = uuid.uuid4().hex[:6]

linhas: list[str] = []
resultados: list[tuple[str, str]] = []   # (estado, título)


def conta(nome: str) -> str:
    return f"{nome}-{SUFIXO}"


def op() -> str:
    return f"op-{uuid.uuid4().hex[:20]}"


def pedir(metodo: str, caminho: str, corpo: dict | None = None,
          token: str | None = None, base: str = BASE) -> tuple[int, object]:
    dados = json.dumps(corpo).encode() if corpo is not None else None
    cabecalhos = {"Content-Type": "application/json"}
    if token:
        cabecalhos["Authorization"] = f"Bearer {token}"
    pedido = urllib.request.Request(base + caminho, data=dados, method=metodo,
                                    headers=cabecalhos)
    try:
        with urllib.request.urlopen(pedido, timeout=30) as resposta:
            return resposta.status, json.loads(resposta.read() or b"null")
    except urllib.error.HTTPError as erro:
        texto = erro.read()
        try:
            return erro.code, json.loads(texto or b"null")
        except json.JSONDecodeError:
            return erro.code, texto.decode(errors="replace")[:200]
    except (urllib.error.URLError, ConnectionError) as erro:
        # Um nó a arrancar recusa ou corta a ligação: é estado 0, não um crash.
        return 0, str(erro)


def seccao(titulo: str) -> None:
    linhas.append(f"\n## {titulo}\n")


def passo(titulo: str, metodo: str, caminho: str, corpo: dict | None = None,
          token: str | None = None, esperado: int = 200, confere=None,
          base: str = BASE, lacuna: bool = False):
    """Faz um pedido, confere o estado e, se houver, uma condição sobre o corpo."""
    estado, resposta = pedir(metodo, caminho, corpo, token, base)
    certo = estado == esperado
    nota = ""
    if certo and confere is not None:
        try:
            certo = bool(confere(resposta))
        except Exception as erro:  # noqa: BLE001 — a conferência falhou, é um ✗
            certo, nota = False, f" (conferência: {erro})"
    # Uma lacuna conhecida confirma-se quando o erro esperado aparece mesmo;
    # se não aparecer, alguma coisa mudou e convém olhar.
    if lacuna:
        marca = "⚠️ lacuna confirmada" if certo else "❓ lacuna não reproduzida"
        resultados.append(("lacuna" if certo else "falha", titulo))
    else:
        marca = "✅" if certo else "❌"
        resultados.append(("ok" if certo else "falha", titulo))

    alvo = caminho if base == BASE else f"{base}{caminho}"
    linhas.append(f"**{titulo}** — {marca}{nota}\n")
    linhas.append("```http")
    linhas.append(f"{metodo} {alvo}" + (f"\n{json.dumps(corpo, ensure_ascii=False)}" if corpo else ""))
    linhas.append(f"→ {estado} (esperado {esperado}" + (", lacuna" if lacuna else "") + ")")
    # O token não fica no registo: só o princípio, para se ver que veio.
    mostrada = ({**resposta, "token": resposta["token"][:12] + "…"}
                if isinstance(resposta, dict) and "token" in resposta else resposta)
    texto = json.dumps(mostrada, ensure_ascii=False)
    linhas.append(texto if len(texto) <= 600 else texto[:600] + " …")
    linhas.append("```\n")
    return estado, resposta


def nota(texto: str) -> None:
    linhas.append(texto + "\n")


def em_paralelo(tarefas) -> list:
    resultados_ = [None] * len(tarefas)
    partida = threading.Barrier(len(tarefas))

    def correr(indice, tarefa):
        partida.wait()
        resultados_[indice] = tarefa()

    fios = [threading.Thread(target=correr, args=(i, t)) for i, t in enumerate(tarefas)]
    for fio in fios:
        fio.start()
    for fio in fios:
        fio.join(60)
    return resultados_


def compose(*argumentos: str) -> str:
    return subprocess.run(["docker", "compose", *argumentos], cwd=PROTOTIPO,
                          capture_output=True, text=True).stdout


IMPRESSAO = """
SELECT (SELECT count(*) FROM usuario) || ' utilizadores · ' ||
       (SELECT count(*) FROM conta) || ' contas · ' ||
       (SELECT count(*) FROM operacao) || ' operações · log até ' ||
       (SELECT coalesce(max(indice), 0) FROM log_replicado) || ' · md5 ' ||
       left(md5((SELECT coalesce(string_agg(id || ':' || saldo_centavos, ',' ORDER BY id), '')
                 FROM conta) ||
                (SELECT coalesce(string_agg(op_id || ':' || numero, ',' ORDER BY numero), '')
                 FROM operacao)), 12)
"""


def impressoes() -> dict[str, str]:
    """O conteúdo da base de cada nó, resumido. Três iguais = três bases iguais."""
    resultado = {}
    for no in "abc":
        saida = compose("exec", "-T", f"postgres-{no}", "psql", "-U", "banco", "-d",
                        "banco", "-At", "-c", IMPRESSAO)
        resultado[no.upper()] = saida.strip()
    return resultado


def esperar_bases_iguais(limite: float = 10.0) -> bool:
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        if len(set(impressoes().values())) == 1:
            return True
        time.sleep(0.3)
    return False


def tabela_por_no() -> str:
    linhas_ = ["| Nó | Base de dados do nó |", "|---|---|"]
    linhas_ += [f"| {no} | {texto} |" for no, texto in impressoes().items()]
    return "\n".join(linhas_)


def principal() -> int:
    inicio = time.strftime("%Y-%m-%d %H:%M:%S")
    linhas.append("# Sessão de operações de teste — Protótipo 2\n")
    linhas.append(f"Executada a {inicio}, sufixo `{SUFIXO}`, contra `{BASE}` "
                  "(painel → balanceador → nó).\n")

    # -------------------------------------------------------------- arranque
    for _ in range(60):
        if pedir("GET", "/saude")[0] == 200:
            break
        time.sleep(0.5)
    seccao("1. O cluster está de pé")
    passo("Balanceador responde", "GET", "/saude",
          confere=lambda r: r["balanceador"] == "ativo")
    for _ in range(60):  # a primeira eleição demora até um timeout de eleição
        papeis = [pedir("GET", "/interno/estado", base=b)[1] for b in NOS.values()]
        if sum(1 for p in papeis if isinstance(p, dict) and p.get("papel") == "primário") == 1:
            break
        time.sleep(0.25)
    for no, base in NOS.items():
        passo(f"Nó {no} responde", "GET", "/interno/estado", base=base,
              confere=lambda r, no=no: r["no"] == no)
    passo("Há exatamente um primário, e as réplicas sabem quem é", "GET",
          "/interno/cluster",
          confere=lambda r: sum(1 for n in r["nos"] if n.get("papel") == "primário") == 1
          and len({n.get("lider") for n in r["nos"]}) == 1)

    # -------------------------------------------------------------- sessão
    seccao("2. Registo e sessão")
    ana, rui = f"ana-{SUFIXO}@teste.pt", f"rui-{SUFIXO}@teste.pt"
    passo("Registar a Ana", "POST", "/auth/registo",
          {"nome": "Ana", "email": ana, "senha": "segredo-ana"})
    passo("Registar o Rui", "POST", "/auth/registo",
          {"nome": "Rui", "email": rui, "senha": "segredo-rui"})
    passo("Email repetido é recusado", "POST", "/auth/registo",
          {"nome": "Outra", "email": ana, "senha": "outra-senha"}, esperado=409,
          confere=lambda r: r["erro"] == "email_duplicado")
    passo("Senha errada é recusada", "POST", "/auth/login",
          {"email": ana, "senha": "errada"}, esperado=401,
          confere=lambda r: r["erro"] == "credenciais_invalidas")
    _, r = passo("Login da Ana", "POST", "/auth/login", {"email": ana, "senha": "segredo-ana"},
                 confere=lambda r: "token" in r)
    t_ana = r["token"]
    _, r = passo("Login do Rui", "POST", "/auth/login", {"email": rui, "senha": "segredo-rui"})
    t_rui = r["token"]
    passo("Abrir conta sem sessão é recusado", "POST", "/contas",
          {"conta": conta("x"), "op_id": op()}, esperado=401,
          confere=lambda r: r["erro"] == "sem_sessao")

    # -------------------------------------------------------------- contas
    seccao("3. Abrir contas: moedas e produtos")
    corrente, dolares = conta("ana-corrente"), conta("ana-dolares")
    poupanca, prazo, do_rui = conta("ana-poupanca"), conta("ana-prazo"), conta("rui")
    passo("Conta corrente em reais", "POST", "/contas",
          {"conta": corrente, "saldo_inicial": "100.00", "op_id": op()}, t_ana,
          confere=lambda r: r["saldo"] == "R$ 100,00")
    passo("Conta em dólares", "POST", "/contas",
          {"conta": dolares, "saldo_inicial": "50.00", "moeda": "USD", "op_id": op()}, t_ana,
          confere=lambda r: r["saldo"] == "US$ 50,00")
    passo("Poupança a 10 % ao ano", "POST", "/contas",
          {"conta": poupanca, "saldo_inicial": "1000.00", "produto": "poupanca",
           "taxa_juros": "0.10", "op_id": op()}, t_ana)
    passo("Prazo fixo a 12 %, 30 dias", "POST", "/contas",
          {"conta": prazo, "saldo_inicial": "500.00", "produto": "prazo_fixo",
           "taxa_juros": "0.12", "prazo_dias": 30, "op_id": op()}, t_ana)
    passo("Conta do Rui", "POST", "/contas",
          {"conta": do_rui, "saldo_inicial": "0", "op_id": op()}, t_rui)
    passo("A Ana vê só as suas quatro contas", "GET", "/contas", token=t_ana,
          confere=lambda r: sorted(c["conta"] for c in r["contas"])
          == sorted([corrente, dolares, poupanca, prazo]))

    seccao("4. Pedidos mal formados")
    passo("Dinheiro como número JSON", "POST", f"/contas/{corrente}/deposito",
          {"valor": 25.00, "op_id": op()}, esperado=400,
          confere=lambda r: r["erro"] == "valor_invalido")
    passo("Três casas decimais", "POST", f"/contas/{corrente}/deposito",
          {"valor": "1.005", "op_id": op()}, esperado=400)
    passo("Id de conta com espaços", "POST", "/contas",
          {"conta": "Ana Silva", "op_id": op()}, t_ana, esperado=400)
    passo("Conta repetida", "POST", "/contas",
          {"conta": corrente, "saldo_inicial": "1.00", "op_id": op()}, t_ana, esperado=409,
          confere=lambda r: r["erro"] == "conta_duplicada")
    passo("Moeda desconhecida", "POST", "/contas",
          {"conta": conta("euros"), "moeda": "EUR", "op_id": op()}, t_ana, esperado=400)
    passo("Conta corrente com taxa de juros", "POST", "/contas",
          {"conta": conta("estranha"), "taxa_juros": "0.10", "op_id": op()}, t_ana,
          esperado=400)
    passo("op_id curto demais", "POST", f"/contas/{corrente}/deposito",
          {"valor": "1.00", "op_id": "curto"}, esperado=400)

    # -------------------------------------------------------------- movimentos
    seccao("5. Depósitos, saques e transferências")
    passo("O Rui deposita na conta da Ana (depositar é aberto)", "POST",
          f"/contas/{corrente}/deposito", {"valor": "5.00", "op_id": op()}, t_rui,
          confere=lambda r: r["saldo_centavos"] == 10500)
    passo("Saque de 10,00", "POST", f"/contas/{corrente}/saque",
          {"valor": "10.00", "op_id": op()}, t_ana,
          confere=lambda r: r["saldo_centavos"] == 9500)
    passo("Saque maior que o saldo", "POST", f"/contas/{corrente}/saque",
          {"valor": "9999.00", "op_id": op()}, t_ana, esperado=422,
          confere=lambda r: "tem R$ 95,00" in r["mensagem"])
    passo("Saque de prazo fixo antes de vencer", "POST", f"/contas/{prazo}/saque",
          {"valor": "1.00", "op_id": op()}, t_ana, esperado=409,
          confere=lambda r: r["erro"] == "conta_bloqueada")
    transf = {"de": corrente, "para": do_rui, "valor": "25.00", "op_id": op()}
    _, primeira = passo("Transferência de 25,00 para o Rui", "POST", "/transferencias",
                        transf, t_ana,
                        confere=lambda r: r["saldos_centavos"] == {corrente: 7000, do_rui: 2500})
    passo("A mesma transferência repetida devolve o mesmo corpo", "POST",
          "/transferencias", transf, t_ana, confere=lambda r: r == primeira)
    passo("O mesmo op_id com outro valor devolve o guardado", "POST", "/transferencias",
          {**transf, "valor": "70.00"}, t_ana, confere=lambda r: r == primeira)
    passo("O Rui só recebeu uma vez", "GET", f"/contas/{do_rui}", token=t_rui,
          confere=lambda r: r["saldo_centavos"] == 2500)

    seccao("6. Dono da conta")
    passo("O Rui não consulta a conta da Ana", "GET", f"/contas/{corrente}", token=t_rui,
          esperado=403, confere=lambda r: r["erro"] == "proibido")
    passo("O Rui não vê o extrato da Ana", "GET", f"/contas/{corrente}/extrato",
          token=t_rui, esperado=403)
    passo("O Rui não saca da conta da Ana", "POST", f"/contas/{corrente}/saque",
          {"valor": "1.00", "op_id": op()}, t_rui, esperado=403)
    passo("O Rui não transfere a partir da conta da Ana", "POST", "/transferencias",
          {"de": corrente, "para": do_rui, "valor": "1.00", "op_id": op()}, t_rui,
          esperado=403)
    passo("O Rui não repete um op_id da Ana para ler a resposta dela", "POST",
          "/transferencias", transf, t_rui, esperado=403)

    # -------------------------------------------------------------- moedas
    seccao("7. Moedas e câmbio")
    passo("Transferência simples entre moedas é recusada", "POST", "/transferencias",
          {"de": dolares, "para": corrente, "valor": "1.00", "op_id": op()}, t_ana,
          esperado=409, confere=lambda r: r["erro"] == "moedas_diferentes")
    passo("Taxa USD→BRL em vigor", "GET", "/taxas/USD/BRL",
          confere=lambda r: r["taxa"] == "5.430000")
    cambio = {"de": dolares, "para": corrente, "valor": "10.00", "op_id": op()}
    _, c1 = passo("Câmbio de 10,00 USD", "POST", "/transferencias/conversao", cambio, t_ana,
                  confere=lambda r: r["valor_destino"] == "R$ 54,30")
    passo("Registar uma taxa nova, 6,00", "POST", "/admin/taxas",
          {"moeda_origem": "USD", "moeda_destino": "BRL", "taxa": "6.00"}, t_ana,
          confere=lambda r: r["taxa_milionesimos"] == 6_000_000)
    passo("O câmbio repetido mantém a taxa de então", "POST", "/transferencias/conversao",
          cambio, t_ana, confere=lambda r: r == c1)
    passo("Um câmbio novo usa a taxa nova", "POST", "/transferencias/conversao",
          {**cambio, "op_id": op()}, t_ana,
          confere=lambda r: r["valor_destino_centavos"] == 6000)
    passo("Autotransferência entre moedas", "POST", "/transferencias/autotransferencia",
          {"de": dolares, "para": corrente, "valor": "1.00", "op_id": op()}, t_ana,
          confere=lambda r: r["valor_destino_centavos"] == 600)
    passo("Autotransferência para conta alheia é recusada", "POST",
          "/transferencias/autotransferencia",
          {"de": corrente, "para": do_rui, "valor": "1.00", "op_id": op()}, t_ana,
          esperado=403)

    # -------------------------------------------------------------- externa
    seccao("8. Transferência para outro banco")
    nota("O compose usa o `GatewayExternoSimulado`: confirma cerca de 85 % das vezes, "
         "ao acaso. Envia-se até aparecer uma confirmação e uma rejeição.")
    passo("Bancos disponíveis", "GET", "/sistemas-externos",
          confere=lambda r: r["sistemas"][0]["id"] == "banco-externo")
    vistos: dict[str, dict] = {}
    for tentativa in range(1, 31):
        pedido = {"de": corrente, "sistema_externo_id": "banco-externo",
                  "valor": "1.00", "op_id": op()}
        estado, resposta = pedir("POST", "/transferencias/externa", pedido, t_ana)
        if estado == 200 and resposta["estado"] not in vistos:
            vistos[resposta["estado"]] = pedido
            passo(f"Envio {tentativa}: {resposta['estado']} (repetido para registo)",
                  "POST", "/transferencias/externa", pedido, t_ana,
                  confere=lambda r, e=resposta["estado"]: r["estado"] == e)
        if len(vistos) == 2:
            break
    nota(f"Foram precisos {tentativa} envios para ver os dois desfechos. A repetição de "
         "cada um devolveu o desfecho gravado, sem voltar a perguntar ao outro banco.")
    passo("Banco desconhecido", "POST", "/transferencias/externa",
          {"de": corrente, "sistema_externo_id": "nao-existe", "valor": "1.00",
           "op_id": op()}, t_ana, esperado=404)
    passo("Sem saldo, nem chega ao outro banco", "POST", "/transferencias/externa",
          {"de": corrente, "sistema_externo_id": "banco-externo", "valor": "99999.00",
           "op_id": op()}, t_ana, esperado=422)

    # -------------------------------------------------------------- juros
    seccao("9. Juros")
    passo("Tick de juros", "POST", "/admin/juros", token=t_ana,
          confere=lambda r: isinstance(r["creditadas"], list))
    nota("A poupança abriu há segundos: os juros devidos ainda não chegam a um "
         "centavo, por isso a lista sai vazia. O cálculo ao longo de um ano e o "
         "prazo fixo vencido estão provados em `tests/unitarios/teste_produtos.py`, "
         "onde o instante é um argumento e não é preciso esperar.")

    # -------------------------------------------------------------- concorrência
    seccao("10. Concorrência")
    paralelos = em_paralelo([
        (lambda: pedir("POST", f"/contas/{do_rui}/deposito",
                       {"valor": "1.00", "op_id": op()}))
        for _ in range(20)])
    aceites = sum(1 for estado, _ in paralelos if estado == 200)
    passo(f"20 depósitos de 1,00 ao mesmo tempo ({aceites} aceites): nenhum se perde",
          "GET", f"/contas/{do_rui}", token=t_rui,
          confere=lambda r: aceites == 20 and r["saldo_centavos"] == 2500 + 2000)
    pequena = conta("rui-pequena")
    pedir("POST", "/contas", {"conta": pequena, "saldo_inicial": "10.00", "op_id": op()}, t_rui)
    saques = em_paralelo([
        (lambda: pedir("POST", f"/contas/{pequena}/saque",
                       {"valor": "1.00", "op_id": op()}, t_rui))
        for _ in range(20)])
    contagem = {200: 0, 422: 0}
    for estado, _ in saques:
        contagem[estado] = contagem.get(estado, 0) + 1
    passo(f"20 saques de 1,00 sobre 10,00 ao mesmo tempo: {contagem[200]} aceites, "
          f"{contagem[422]} recusados", "GET", f"/contas/{pequena}", token=t_rui,
          confere=lambda r: contagem[200] == 10 and contagem[422] == 10
          and r["saldo_centavos"] == 0)

    # -------------------------------------------------------------- consultas
    seccao("11. Extrato e auditoria")
    passo("Extrato da conta corrente da Ana", "GET", f"/contas/{corrente}/extrato",
          token=t_ana, confere=lambda r: r["movimentos"][0]["tipo"] == "criar_conta")
    passo("Auditoria: cada moeda bate", "GET", "/auditoria",
          confere=lambda r: r["divergente"] is False
          and {m["moeda"] for m in r["moedas"]} >= {"BRL", "USD"})

    # -------------------------------------------------------------- falha
    seccao("12. Replicação e queda do primário a meio de transferências")
    nota("Antes da queda, as três bases têm de ser iguais — cada escrita acima foi "
         "confirmada pela maioria e aplicada nos três nós:")
    esperar_bases_iguais()
    nota(tabela_por_no())
    _, estado_antes = pedir("GET", "/interno/estado")
    lider, epoch = estado_antes["no"], estado_antes["epoch"]
    _, auditoria_antes = pedir("GET", "/auditoria")
    totais_antes = {m["moeda"]: m["total_centavos"] for m in auditoria_antes["moedas"]}

    # Três clientes a transferir 0,01 da Ana para o Rui sem parar; cada um repete
    # o mesmo op_id até alguém confirmar, como um cliente real faria.
    parar = threading.Event()
    confirmadas: list[str] = []
    falhadas_em_voo: list[int] = []

    def cliente(n):
        numero = 0
        while not parar.is_set():
            numero += 1
            pedido = {"de": corrente, "para": do_rui, "valor": "0.01",
                      "op_id": f"op-carga-{SUFIXO}-{n}-{numero:04d}"}
            for _ in range(60):
                estado, _ = pedir("POST", "/transferencias", pedido, t_ana)
                if estado == 200:
                    confirmadas.append(pedido["op_id"])
                    break
                falhadas_em_voo.append(estado)
                time.sleep(0.1)

    fios = [threading.Thread(target=cliente, args=(n,)) for n in range(3)]
    for fio in fios:
        fio.start()
    time.sleep(1.0)
    nota(f"`docker compose kill no-{lider.lower()}` — o primário (nó {lider}, epoch "
         f"{epoch}) morre a meio de transferências concorrentes, sem fechar nada.")
    inicio = time.monotonic()
    compose("kill", f"no-{lider.lower()}")
    novo = None
    while time.monotonic() - inicio < 15:
        for no, base in NOS.items():
            if no == lider:
                continue
            estado, r = pedir("GET", "/interno/estado", base=base)
            if estado == 200 and r.get("papel") == "primário":
                novo = no
                break
        if novo:
            break
        time.sleep(0.05)
    demorou = time.monotonic() - inicio
    time.sleep(1.5)
    parar.set()
    for fio in fios:
        fio.join(30)

    nota(f"O nó **{novo}** passou a primário **{demorou:.2f} s** depois do `kill`. "
         f"Durante a transição, {len(falhadas_em_voo)} tentativas receberam um erro "
         f"(`{sorted(set(falhadas_em_voo))}`) e foram repetidas com o mesmo op_id; "
         f"{len(confirmadas)} transferências foram confirmadas no total.")
    passo("Outro nó é primário, com epoch maior", "GET", "/interno/estado",
          confere=lambda r: r["no"] == novo and r["no"] != lider and r["epoch"] > epoch)
    passo("Eleito em menos de 2 s (RNF-03)", "GET", "/saude",
          confere=lambda r: demorou < 2.0)
    passo("A sessão da Ana continua válida no novo primário", "GET", "/contas",
          token=t_ana, confere=lambda r: len(r["contas"]) == 4)
    passo("Cada transferência confirmada ao cliente está lá", "GET",
          "/contas/" + do_rui, token=t_rui,
          confere=lambda r: r["saldo_centavos"] >= 2500 + 2000 + len(set(confirmadas)))
    passo("A transferência do início, repetida, devolve o mesmo corpo", "POST",
          "/transferencias", transf, t_ana, confere=lambda r: r == primeira)
    passo("O novo primário aceita escritas", "POST", f"/contas/{corrente}/deposito",
          {"valor": "1.00", "op_id": op()})
    passo("O dinheiro total não mudou com a queda", "GET", "/auditoria",
          confere=lambda r: r["divergente"] is False and
          {m["moeda"]: m["total_centavos"] for m in r["moedas"]}
          == {**totais_antes, "BRL": totais_antes["BRL"] + 100})

    nota(f"`docker compose start no-{lider.lower()}` — o nó morto volta.")
    compose("start", f"no-{lider.lower()}")
    voltou = {}
    for _ in range(80):
        estado, r = pedir("GET", "/interno/estado", base=NOS[lider])
        if estado == 200:
            voltou = r
            _, atual = pedir("GET", "/interno/estado")
            if r["papel"] == "réplica" and r["ultimo_aplicado"] >= atual["indice_commit"]:
                break
        time.sleep(0.25)
    passo(f"O nó {lider} voltou como réplica e pôs-se em dia", "GET", "/interno/estado",
          base=NOS[lider], confere=lambda r: r["papel"] == "réplica" and r["lider"] == novo)
    nota("E as três bases voltam a ser iguais — incluindo o que aconteceu enquanto "
         f"o nó {lider} estava morto:")
    iguais = esperar_bases_iguais()
    nota(tabela_por_no())
    passo("Impressão digital igual nas três bases", "GET", "/saude",
          confere=lambda r: iguais)

    # -------------------------------------------------------------- resumo
    ok = sum(1 for e, _ in resultados if e == "ok")
    falhas = [t for e, t in resultados if e == "falha"]
    lacunas = sum(1 for e, _ in resultados if e == "lacuna")
    resumo = (f"**{ok} passos certos, {len(falhas)} falhados, {lacunas} lacunas "
              f"confirmadas**, de {len(resultados)}.")
    linhas.insert(2, resumo + "\n")
    if falhas:
        linhas.insert(3, "Falhados:\n" + "\n".join(f"- {t}" for t in falhas) + "\n")

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text("\n".join(linhas), encoding="utf-8")
    print(resumo)
    for titulo in falhas:
        print("  ✗", titulo)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(principal())
