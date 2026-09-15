import { useState } from "react";

import { api } from "../api/cliente.js";
import { guardarContaVista, lerContasVistas } from "../contas-vistas.js";

// Criar, consultar, depositar e sacar (RF-01 a RF-03) e o extrato (F-05).
//
// O ecrã está partido em duas metades com pesos diferentes de propósito: o
// extrato é o documento e ocupa a coluna larga; abrir e movimentar são os
// controlos e vivem num raio estreito ao lado. Antes eram dois cartões iguais,
// e por isso nada parecia mais importante do que o resto.
export default function Contas() {
  const [conta, definirConta] = useState("");
  const [saldoInicial, definirSaldoInicial] = useState("");
  const [valor, definirValor] = useState("");

  const [consultada, definirConsultada] = useState(null);
  const [movimentos, definirMovimentos] = useState([]);
  const [aCarregar, definirACarregar] = useState(false);

  const [erroConta, definirErroConta] = useState(null);
  const [erroValor, definirErroValor] = useState(null);
  const [confirmado, definirConfirmado] = useState(null);

  const [vistas, definirVistas] = useState(lerContasVistas);

  // Toda a ação acaba por reler a conta: o saldo que se mostra é sempre o que
  // o servidor tem, e nunca um saldo calculado aqui.
  async function correr(acao, { onde, aoConfirmar } = {}) {
    const falharEm = onde === "valor" ? definirErroValor : definirErroConta;
    definirErroConta(null);
    definirErroValor(null);
    definirConfirmado(null);
    definirACarregar(true);
    try {
      const resultado = acao ? await acao() : null;
      const dados = await api.consultarSaldo(conta);
      const extrato = await api.consultarExtrato(conta);
      definirConsultada(dados);
      definirMovimentos(extrato.movimentos);
      definirVistas(guardarContaVista(conta));
      if (aoConfirmar) definirConfirmado(aoConfirmar(resultado, dados));
    } catch (falha) {
      falharEm(falha.message);
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
        definirVistas(guardarContaVista(identificador));
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
            <p className="rotulo-de-seccao">saldo de {consultada.conta}</p>
            {/* Já vem formatado do servidor. Dividir por 100 aqui seria pôr um
                float no meio do dinheiro, que é o que SPECS 3.1 proíbe. */}
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
              consulta uma que já exista.
            </p>
          </div>
        )}
      </section>

      {/* ---------------------------------------------------- o raio ----- */}
      <div className="raio">
        <section className="cartao surge">
          <h2>Conta</h2>

          {vistas.length > 0 && (
            <>
              <p className="rotulo-de-seccao">vistas neste navegador</p>
              <div className="pastilhas">
                {vistas.map((identificador) => (
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

          {erroConta && <p className="erro-do-campo" role="alert">{erroConta}</p>}

          <div className="botoes" style={{ marginTop: "16px" }}>
            <button
              type="button"
              className="principal"
              disabled={!conta || aCarregar}
              onClick={() =>
                correr(() => api.criarConta(conta, saldoInicial), {
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
                correr(() => api.depositar(conta, valor), {
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
                correr(() => api.sacar(conta, valor), {
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
