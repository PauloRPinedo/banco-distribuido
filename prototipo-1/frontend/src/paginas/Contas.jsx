import { useState } from "react";

import { api } from "../api/cliente.js";

// Criar, consultar, depositar e sacar (RF-01 a RF-03) e o extrato (F-05).
export default function Contas() {
  const [conta, definirConta] = useState("");
  const [saldoInicial, definirSaldoInicial] = useState("");
  const [valor, definirValor] = useState("");
  const [consultada, definirConsultada] = useState(null);
  const [movimentos, definirMovimentos] = useState([]);
  const [erro, definirErro] = useState(null);

  // Toda a ação acaba por reler a conta: o saldo que se mostra é sempre o que
  // o servidor tem, e nunca um saldo calculado aqui.
  async function correr(acao) {
    definirErro(null);
    try {
      if (acao) await acao();
      definirConsultada(await api.consultarSaldo(conta));
      definirMovimentos((await api.consultarExtrato(conta)).movimentos);
    } catch (falha) {
      definirErro(falha.message);
      definirConsultada(null);
      definirMovimentos([]);
    }
  }

  return (
    <div className="colunas">
      <section className="cartao">
        <h2>Conta</h2>

        <label className="campo">
          <span>Identificador</span>
          <input
            value={conta}
            onChange={(evento) => definirConta(evento.target.value)}
            placeholder="alice"
          />
        </label>

        <label className="campo">
          <span>Saldo inicial</span>
          <input
            value={saldoInicial}
            onChange={(evento) => definirSaldoInicial(evento.target.value)}
            placeholder="100.00"
            inputMode="decimal"
          />
        </label>

        <div className="botoes">
          <button type="button" className="principal"
                  onClick={() => correr(() => api.criarConta(conta, saldoInicial))}>
            Criar
          </button>
          <button type="button" onClick={() => correr()}>
            Consultar
          </button>
        </div>

        <label className="campo">
          <span>Valor</span>
          <input
            value={valor}
            onChange={(evento) => definirValor(evento.target.value)}
            placeholder="25.00"
            inputMode="decimal"
          />
        </label>

        <div className="botoes">
          <button type="button"
                  onClick={() => correr(() => api.depositar(conta, valor))}>
            Depositar
          </button>
          <button type="button"
                  onClick={() => correr(() => api.sacar(conta, valor))}>
            Sacar
          </button>
        </div>

        {erro && <p className="aviso fora-do-ar">{erro}</p>}
      </section>

      <section className="cartao">
        <h2>Saldo</h2>

        {consultada ? (
          <>
            {/* O saldo já vem formatado do servidor. Dividir por 100 aqui
                seria pôr um float no meio do dinheiro. */}
            <p className="total">{consultada.saldo}</p>
            <p className="legenda">{consultada.conta}</p>

            <h3>Extrato</h3>
            {movimentos.length === 0 ? (
              <p className="legenda">sem movimentos</p>
            ) : (
              <table className="tabela">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Tipo</th>
                    <th>Contraparte</th>
                    <th className="direita">Valor</th>
                    <th className="direita">Saldo</th>
                  </tr>
                </thead>
                <tbody>
                  {movimentos.map((movimento) => (
                    <tr key={movimento.indice}>
                      <td>{movimento.indice}</td>
                      <td>{movimento.tipo}</td>
                      <td>{movimento.contraparte || "—"}</td>
                      <td className="direita">{movimento.valor}</td>
                      <td className="direita">{movimento.saldo_depois}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        ) : (
          <p className="legenda">consulta uma conta para ver o saldo</p>
        )}
      </section>
    </div>
  );
}
