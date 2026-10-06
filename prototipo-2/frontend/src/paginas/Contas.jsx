import { useEffect, useRef, useState } from "react";

import { api, criarIntencao } from "../api/cliente.js";

// Criar, consultar, depositar e sacar (RF-01 a RF-03) e o extrato (F-05).
//
// O ecrã está partido em duas metades com pesos diferentes de propósito: o
// extrato é o documento e ocupa a coluna larga; abrir e movimentar são os
// controlos e vivem num raio estreito ao lado. Antes eram dois cartões iguais,
// e por isso nada parecia mais importante do que o resto.
const PRODUTOS = { corrente: "corrente", poupanca: "poupança", prazo_fixo: "prazo fixo" };

// "0.100000" -> "10 %". Só para mostrar: a taxa com que se calcula é a do
// servidor, em milionésimos inteiros.
function percentagem(taxa) {
  const [inteiros, decimais = ""] = taxa.split(".");
  const centesimos = `${inteiros}${decimais.padEnd(6, "0")}`.replace(/^0+(?=\d)/, "");
  const parte = centesimos.padStart(5, "0");
  const inteira = parte.slice(0, -4).replace(/^0+(?=\d)/, "");
  const fracao = parte.slice(-4).replace(/0+$/, "");
  return `${inteira}${fracao ? "," + fracao : ""} %`;
}

export default function Contas() {
  const [conta, definirConta] = useState("");
  const [saldoInicial, definirSaldoInicial] = useState("");
  const [moeda, definirMoeda] = useState("BRL");
  const [produto, definirProduto] = useState("corrente");
  const [taxaJuros, definirTaxaJuros] = useState("");
  const [prazoDias, definirPrazoDias] = useState("");
  const [valor, definirValor] = useState("");

  const [consultada, definirConsultada] = useState(null);
  const [movimentos, definirMovimentos] = useState([]);
  const [aCarregar, definirACarregar] = useState(false);

  const [erroConta, definirErroConta] = useState(null);
  const [erroValor, definirErroValor] = useState(null);
  const [confirmado, definirConfirmado] = useState(null);

  // As contas de quem tem a sessão, vindas do servidor (`GET /contas`).
  const [minhas, definirMinhas] = useState([]);

  // Uma intenção por botão: repetir "Depositar" com o mesmo valor depois de
  // uma falha de rede reutiliza o op_id, e o dinheiro não entra duas vezes.
  const intencoes = useRef({
    abrir: criarIntencao(), depositar: criarIntencao(), sacar: criarIntencao(),
  }).current;

  function recarregarMinhas() {
    return api.listarContas()
      .then((lista) => definirMinhas(lista.contas.map((c) => c.conta)))
      .catch(() => definirMinhas([]));
  }

  useEffect(() => {
    recarregarMinhas();
  }, []);

  // Toda a ação acaba por reler a conta: o saldo que se mostra é sempre o que
  // o servidor tem, e nunca um saldo calculado aqui.
  async function correr(acao, { onde, aoConfirmar } = {}) {
    const falharEm = onde === "valor" ? definirErroValor : definirErroConta;
    definirErroConta(null);
    definirErroValor(null);
    definirConfirmado(null);
    definirACarregar(true);
    let resultado = null;
    let recusada = false;
    try {
      resultado = acao ? await acao() : null;
    } catch (falha) {
      // A operação foi recusada (sem saldo, prazo fixo, ...), mas a conta
      // continua lá: mostra-se o erro e relê-se a conta, em vez de a esconder
      // e obrigar a escolhê-la outra vez.
      falharEm(falha.message);
      recusada = true;
    }
    try {
      const dados = await api.consultarSaldo(conta);
      const extrato = await api.consultarExtrato(conta);
      definirConsultada(dados);
      definirMovimentos(extrato.movimentos);
      recarregarMinhas();
      if (!recusada && aoConfirmar) definirConfirmado(aoConfirmar(resultado, dados));
    } catch (falha) {
      // Só aqui a conta deixa de se mostrar: ela própria não se consegue ler.
      // Se a operação já tinha sido recusada, fica a mensagem dessa recusa.
      if (!recusada) falharEm(falha.message);
      definirConsultada(null);
      definirMovimentos([]);
    } finally {
      definirACarregar(false);
    }
  }

  function escolher(identificador) {
    definirConta(identificador);
    definirErroConta(null);
    definirErroValor(null);
    definirConfirmado(null);
    definirACarregar(true);
    Promise.all([api.consultarSaldo(identificador), api.consultarExtrato(identificador)])
      .then(([dados, extrato]) => {
        definirConsultada(dados);
        definirMovimentos(extrato.movimentos);
      })
      .catch((falha) => {
        definirErroConta(falha.message);
        definirConsultada(null);
        definirMovimentos([]);
      })
      .finally(() => definirACarregar(false));
  }

  const temConta = Boolean(consultada);

  return (
    <div className="livro-e-raio">
      {/* ------------------------------------------------ o documento ---- */}
      <section className="cartao surge" aria-live="polite">
        {aCarregar && !consultada ? (
          <>
            <p className="rotulo-de-seccao">a consultar</p>
            <p className="quantia-grande esqueleto">R$ 0.000,00</p>
          </>
        ) : consultada ? (
          <>
            <p className="rotulo-de-seccao">
              saldo de {consultada.conta} · {consultada.moeda} · {PRODUTOS[consultada.produto]}
              {consultada.taxa_juros && ` · ${percentagem(consultada.taxa_juros)} ao ano`}
              {consultada.vence_em && ` · vence a ${new Date(consultada.vence_em * 1000).toLocaleDateString("pt-PT")}`}
            </p>
            {/* Já vem formatado do servidor. Dividir por 100 aqui seria pôr um
                float no meio do dinheiro, que é o que o banco proíbe. */}
            <p className="quantia-grande">{consultada.saldo}</p>
            {confirmado && <p className="carimbo">✓ {confirmado}</p>}

            <div className="rolavel" style={{ marginTop: "40px" }}>
              {movimentos.length === 0 ? (
                <p className="legenda">ainda sem movimentos nesta conta</p>
              ) : (
                <table className="razao">
                  <caption>extrato</caption>
                  <thead>
                    <tr>
                      <th scope="col">#</th>
                      <th scope="col">operação</th>
                      <th scope="col">contraparte</th>
                      <th scope="col" className="direita">valor</th>
                      <th scope="col" className="direita">saldo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {movimentos.map((movimento) => (
                      <tr key={movimento.indice}>
                        <td className="indice">{movimento.indice}</td>
                        <td>
                          <span className="tipo-de-operacao">
                            {movimento.tipo.replace("_", " ")}
                          </span>
                        </td>
                        <td>{movimento.contraparte || "—"}</td>
                        <td className={
                          movimento.valor_centavos < 0 ? "direita negativo" : "direita"
                        }>
                          {movimento.valor}
                        </td>
                        <td className="direita">{movimento.saldo_depois}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        ) : (
          <div className="vazio">
            <p className="titulo">Nenhuma conta aberta</p>
            <p>
              Escreve um identificador no raio ao lado e abre uma conta, ou
              escolhe uma das tuas.
            </p>
          </div>
        )}
      </section>

      {/* ---------------------------------------------------- o raio ----- */}
      <div className="raio">
        <section className="cartao surge">
          <h2>Conta</h2>

          {minhas.length > 0 && (
            <>
              <p className="rotulo-de-seccao">as tuas contas</p>
              <div className="pastilhas">
                {minhas.map((identificador) => (
                  <button
                    key={identificador}
                    type="button"
                    className={
                      identificador === consultada?.conta
                        ? "pastilha escolhida"
                        : "pastilha"
                    }
                    onClick={() => escolher(identificador)}
                  >
                    {identificador}
                  </button>
                ))}
              </div>
            </>
          )}

          <label className={erroConta ? "campo tem-erro" : "campo"}>
            <span>Identificador</span>
            <input
              value={conta}
              onChange={(evento) => definirConta(evento.target.value)}
              placeholder="alice"
              autoComplete="off"
              spellCheck="false"
            />
          </label>

          <label className="campo">
            <span>Saldo inicial — só ao abrir</span>
            <input
              value={saldoInicial}
              onChange={(evento) => definirSaldoInicial(evento.target.value)}
              placeholder="100.00"
              inputMode="decimal"
            />
          </label>

          <div className="par">
            <label className="campo" style={{ marginBottom: 0 }}>
              <span>Moeda</span>
              <select value={moeda} onChange={(e) => definirMoeda(e.target.value)}>
                <option>BRL</option><option>USD</option><option>PEN</option>
              </select>
            </label>
            <label className="campo" style={{ marginBottom: 0 }}>
              <span>Produto</span>
              <select value={produto} onChange={(e) => definirProduto(e.target.value)}>
                <option value="corrente">corrente</option>
                <option value="poupanca">poupança</option>
                <option value="prazo_fixo">prazo fixo</option>
              </select>
            </label>
          </div>

          {produto !== "corrente" && (
            <label className="campo" style={{ marginTop: "16px" }}>
              <span>Taxa de juros ao ano — "0.10" é 10 %</span>
              <input value={taxaJuros} onChange={(e) => definirTaxaJuros(e.target.value)}
                     placeholder="0.10" inputMode="decimal" />
            </label>
          )}
          {produto === "prazo_fixo" && (
            <label className="campo">
              <span>Prazo em dias</span>
              <input value={prazoDias} onChange={(e) => definirPrazoDias(e.target.value)}
                     placeholder="30" inputMode="numeric" />
            </label>
          )}

          {erroConta && <p className="erro-do-campo" role="alert">{erroConta}</p>}

          <div className="botoes" style={{ marginTop: "16px" }}>
            <button
              type="button"
              className="principal"
              disabled={!conta || aCarregar}
              onClick={() =>
                correr(() => api.criarConta(conta, saldoInicial, {
                  moeda,
                  produto,
                  taxa_juros: produto === "corrente" ? "" : taxaJuros,
                  prazo_dias: produto === "prazo_fixo" ? Number(prazoDias) || "" : "",
                }, intencoes.abrir), {
                  aoConfirmar: () => "conta aberta",
                })
              }
            >
              Abrir conta
            </button>
            <button type="button" disabled={!conta || aCarregar}
                    onClick={() => correr()}>
              Consultar
            </button>
          </div>
        </section>

        <section className="cartao surge">
          <h2>Movimentar</h2>
          <p className="legenda">
            {temConta
              ? `sobre ${consultada.conta}`
              : "escolhe ou consulta uma conta primeiro"}
          </p>

          <label className={erroValor ? "campo heroi tem-erro" : "campo heroi"}
                 style={{ marginTop: "16px" }}>
            <span>Valor</span>
            <input
              value={valor}
              onChange={(evento) => definirValor(evento.target.value)}
              placeholder="25.00"
              inputMode="decimal"
              disabled={!temConta}
            />
          </label>

          {erroValor && <p className="erro-do-campo" role="alert">{erroValor}</p>}

          <div className="botoes">
            <button
              type="button"
              disabled={!temConta || !valor || aCarregar}
              onClick={() =>
                correr(() => api.depositar(conta, valor, intencoes.depositar), {
                  onde: "valor",
                  aoConfirmar: () => `depósito de ${valor} confirmado`,
                })
              }
            >
              Depositar
            </button>
            <button
              type="button"
              disabled={!temConta || !valor || aCarregar}
              onClick={() =>
                correr(() => api.sacar(conta, valor, intencoes.sacar), {
                  onde: "valor",
                  aoConfirmar: () => `saque de ${valor} confirmado`,
                })
              }
            >
              Sacar
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
