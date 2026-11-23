#!/usr/bin/env python3
"""RNF-04 e RNF-05: débito e latência, com concorrência crescente.

As metas (SPECS, 11.3): 500 transações por segundo em local, e p99 abaixo de
200 ms. Este script mede e escreve o número real, cumpra-se ou não a meta.

Para cada nível de concorrência (1, 2, 4, 8, 16 e 32 clientes), durante
`--segundos` segundos:

- **escritas**: depósitos de 0,01, cada cliente na sua conta, cada um com um
  op_id novo. Cada um passa pelo log, pela maioria e pela aplicação;
- **leituras**: `GET /contas/<id>`, o saldo da conta do cliente.

Mede-se pelo balanceador (o caminho do painel) e diretamente ao primário (para
ver o que o balanceador acrescenta). Cada cliente tem a sua ligação HTTP,
mantida aberta. Só a biblioteca-padrão.

Uso, com o `docker compose` de pé:

    python3 provas/scripts/medir_desempenho.py                 # ~5 minutos
    python3 provas/scripts/medir_desempenho.py --segundos 3    # ensaio rápido

Escreve `provas/desempenho/medicao.md` e `provas/desempenho/medicao.json`.
"""

import argparse
import http.client
import json
import os
import platform
import statistics
import threading
import time
import urllib.parse
import uuid
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
NIVEIS = (1, 2, 4, 8, 16, 32)
META_TPS = 500
META_P99_MS = 200


class Cliente:
    """Uma ligação HTTP mantida aberta; reabre-se se o servidor a fechar."""

    def __init__(self, base: str, token: str | None = None) -> None:
        url = urllib.parse.urlparse(base)
        self._anfitriao, self._porta = url.hostname, url.port or 80
        self._token = token
        self._ligacao = None

    def pedir(self, metodo: str, caminho: str, corpo: dict | None = None) -> tuple[int, dict]:
        cabecalhos = {"Content-Type": "application/json"}
        if self._token:
            cabecalhos["Authorization"] = f"Bearer {self._token}"
        dados = json.dumps(corpo) if corpo is not None else None
        for tentativa in (1, 2):
            if self._ligacao is None:
                self._ligacao = http.client.HTTPConnection(self._anfitriao, self._porta,
                                                           timeout=10)
            try:
                self._ligacao.request(metodo, caminho, body=dados, headers=cabecalhos)
                resposta = self._ligacao.getresponse()
                conteudo = resposta.read()
                return resposta.status, json.loads(conteudo or b"null")
            except (http.client.HTTPException, ConnectionError, OSError):
                self._ligacao.close()
                self._ligacao = None
                if tentativa == 2:
                    raise
        raise AssertionError("inalcançável")


def preparar(banco: str, n_contas: int) -> tuple[str, list[str]]:
    """Um utilizador e uma conta por cliente, todas a zero."""
    email = f"medicao-{uuid.uuid4().hex[:10]}@exemplo.pt"
    anonimo = Cliente(banco)
    estado, corpo = anonimo.pedir("POST", "/auth/registo",
                                  {"nome": "Medição", "email": email, "senha": "segredo-123"})
    assert estado == 200, corpo
    estado, corpo = anonimo.pedir("POST", "/auth/login", {"email": email, "senha": "segredo-123"})
    assert estado == 200, corpo
    token = corpo["token"]
    cliente = Cliente(banco, token)
    contas = []
    for _ in range(n_contas):
        estado, corpo = cliente.pedir("POST", "/contas", {"saldo_inicial": "0.00",
                                                          "op_id": f"med-{uuid.uuid4().hex}"})
        assert estado == 200, corpo
        contas.append(corpo["conta"])
    return token, contas


def correr(base: str, token: str, contas: list[str], clientes: int, segundos: float,
           tipo: str) -> dict:
    """`clientes` fios a pedir sem parar durante `segundos`; devolve as contas."""
    latencias: list[list[float]] = [[] for _ in range(clientes)]
    erros = [0] * clientes
    comecar = threading.Barrier(clientes + 1)
    parar = threading.Event()

    def trabalhar(i: int) -> None:
        cliente = Cliente(base, token)
        conta = contas[i]
        caminho = (f"/contas/{conta}/deposito" if tipo == "escritas" else f"/contas/{conta}")
        comecar.wait()
        while not parar.is_set():
            corpo = ({"valor": "0.01", "op_id": f"m-{uuid.uuid4().hex}"}
                     if tipo == "escritas" else None)
            inicio = time.perf_counter()
            try:
                estado, _ = cliente.pedir("POST" if corpo else "GET", caminho, corpo)
            except Exception:  # noqa: BLE001 — uma falha de rede conta como erro
                estado = 0
            fim = time.perf_counter()
            if estado == 200:
                latencias[i].append(fim - inicio)
            else:
                erros[i] += 1

    fios = [threading.Thread(target=trabalhar, args=(i,)) for i in range(clientes)]
    for fio in fios:
        fio.start()
    comecar.wait()
    inicio = time.perf_counter()
    time.sleep(segundos)
    parar.set()
    for fio in fios:
        fio.join()
    duracao = time.perf_counter() - inicio

    todas = sorted(x for lista in latencias for x in lista)
    if not todas:
        return {"clientes": clientes, "ops": 0, "erros": sum(erros), "tps": 0}

    def percentil(p: float) -> float:
        return todas[min(len(todas) - 1, int(p / 100 * len(todas)))] * 1000

    return {"clientes": clientes, "ops": len(todas), "erros": sum(erros),
            "tps": len(todas) / duracao,
            "p50_ms": percentil(50), "p95_ms": percentil(95), "p99_ms": percentil(99),
            "media_ms": statistics.fmean(todas) * 1000}


def primario_direto(banco: str) -> tuple[str, str]:
    _, estado = Cliente(banco).pedir("GET", "/interno/estado")
    no = estado["no"]
    portas = {"A": 8001, "B": 8002, "C": 8003}
    return f"http://localhost:{portas[no]}", no


def maquina() -> str:
    cpu = platform.processor() or platform.machine()
    try:
        for linha in Path("/proc/cpuinfo").read_text().splitlines():
            if linha.startswith("model name"):
                cpu = linha.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    return f"{cpu}, {os.cpu_count()} núcleos lógicos, {platform.system()} {platform.release()}"


def tabela(linhas: list[dict]) -> str:
    saida = ["| Clientes | Pedidos | Erros | Por segundo | p50 | p95 | p99 |",
             "|---:|---:|---:|---:|---:|---:|---:|"]
    for r in linhas:
        if not r["ops"]:
            saida.append(f"| {r['clientes']} | 0 | {r['erros']} | 0 | — | — | — |")
            continue
        saida.append(f"| {r['clientes']} | {r['ops']} | {r['erros']} | {r['tps']:.0f} | "
                     f"{r['p50_ms']:.1f} ms | {r['p95_ms']:.1f} ms | {r['p99_ms']:.1f} ms |")
    return "\n".join(saida)


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    argumentos.add_argument("--banco", default="http://localhost:8000")
    argumentos.add_argument("--segundos", type=float, default=10.0)
    argumentos.add_argument("--saida", default=str(RAIZ / "provas" / "desempenho"))
    opcoes = argumentos.parse_args()

    token, contas = preparar(opcoes.banco, max(NIVEIS))
    direto, no = primario_direto(opcoes.banco)
    caminhos = {"balanceador": opcoes.banco, f"primário (nó {no}, direto)": direto}

    resultados: dict[str, dict[str, list[dict]]] = {}
    for nome, base in caminhos.items():
        for tipo in ("escritas", "leituras"):
            for clientes in NIVEIS:
                r = correr(base, token, contas, clientes, opcoes.segundos, tipo)
                resultados.setdefault(nome, {}).setdefault(tipo, []).append(r)
                print(f"{nome:28} {tipo:9} {clientes:2} clientes: {r['tps']:7.0f}/s"
                      + (f"  p99 {r['p99_ms']:6.1f} ms" if r["ops"] else "")
                      + (f"  erros {r['erros']}" if r["erros"] else ""), flush=True)

    pasta = Path(opcoes.saida)
    pasta.mkdir(parents=True, exist_ok=True)
    quando = datetime.now().strftime("%Y-%m-%d %H:%M")
    (pasta / "medicao.json").write_text(json.dumps(
        {"quando": quando, "maquina": maquina(), "segundos_por_nivel": opcoes.segundos,
         "resultados": resultados}, indent=2, ensure_ascii=False) + "\n")

    texto = ["# Medição de desempenho (RNF-04, RNF-05)", "",
             f"Gerado por `provas/scripts/medir_desempenho.py` em {quando}, "
             f"{opcoes.segundos:g} s por nível.", "",
             f"Máquina: {maquina()}. Os três nós, as três bases, o balanceador e o "
             "cliente correm todos nela, no `docker compose`.", "",
             f"Metas: {META_TPS} transações por segundo (RNF-04) e p99 abaixo de "
             f"{META_P99_MS} ms (RNF-05).", ""]
    for nome, por_tipo in resultados.items():
        for tipo, linhas in por_tipo.items():
            prefixo = "pelo" if nome == "balanceador" else "ao"
            texto += [f"## {tipo.capitalize()}, {prefixo} {nome}", "", tabela(linhas), ""]
    (pasta / "medicao.md").write_text("\n".join(texto))
    print(f"\nescrito em {pasta / 'medicao.md'}")


if __name__ == "__main__":
    main()
