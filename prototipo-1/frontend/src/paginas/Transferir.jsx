import { useState } from "react";

import { api } from "../api/cliente.js";
import { guardarContaVista } from "../contas-vistas.js";

// RF-04 e RF-05: ou as duas contas mudam, ou nenhuma muda.
//
// O ecrã mostra a direção do dinheiro em vez de a deixar implícita em dois
// campos de texto empilhados, e o sucesso ganha carimbo — o verde da paleta
// existe só para isto e até agora estava por usar.
export default function Transferir() {
  const [de, definirDe] = useState("");
  const [para, definirPara] = useState("");
  const [valor, definirValor] = useState("");
  const [feita, definirFeita] = useState(null);
  const [erro, definirErro] = useState(null);
  const [aEnviar, definirAEnviar] = useState(false);

  async function enviar(evento) {
    evento.preventDefault();
    definirErro(null);
    definirAEnviar(true);
    try {
      const resultado = await api.transferir(de, para, valor);
      definirFeita({ ...resultado, valor });
      guardarContaVista(de);
      guardarContaVista(para);
    } catch (falha) {
      definirErro(falha.message);
      definirFeita(null);
    } finally {
      definirAEnviar(false);
    }
  }

  const completo = de && para && valor;

  return (
    <div className="livro-e-raio">
      {/* ------------------------------------------------ o comprovativo - */}
      <section className="cartao surge" aria-live="polite">
        {feita ? (
          <>
            <p className="rotulo-de-seccao">transferência</p>
            <p className="quantia-grande">{feita.saldos[feita.de]}</p>
            <p className="legenda">saldo de {feita.de} depois da operação</p>
            <p className="carimbo">✓ confirmada</p>

            <div className="rolavel" style={{ marginTop: "40px" }}>
              <table className="razao">
                <caption>as duas contas, depois</caption>
                <thead>
                  <tr>
                    <th scope="col">conta</th>
                    <th scope="col">papel</th>
                    <th scope="col" className="direita">saldo</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>{feita.de}</td>
                    <td><span className="tipo-de-operacao">origem</span></td>
                    <td className="direita">{feita.saldos[feita.de]}</td>
                  </tr>
                  <tr>
                    <td>{feita.para}</td>
                    <td><span className="tipo-de-operacao">destino</span></td>
                    <td className="direita">{feita.saldos[feita.para]}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <p className="legenda" style={{ marginTop: "16px" }}>
              As duas mudaram na mesma transação. Não houve instante nenhum em
              que o dinheiro tivesse saído de uma e ainda não tivesse entrado na
              outra.
            </p>
          </>
        ) : (
          <div className="vazio">
            <p className="titulo">Nenhuma transferência feita</p>
            <p>
              Preenche a origem, o destino e o valor no raio ao lado. O
              comprovativo aparece aqui.
            </p>
          </div>
        )}
      </section>

      {/* ---------------------------------------------------- o raio ----- */}
      <div className="raio">
        <form className="cartao surge" onSubmit={enviar}>
          <h2>Transferir</h2>

          <div className="percurso" style={{ marginTop: "16px" }}>
            <label className="campo" style={{ marginBottom: 0 }}>
              <span>De</span>
              <input value={de} onChange={(e) => definirDe(e.target.value)}
                     placeholder="alice" autoComplete="off" spellCheck="false"
                     required />
            </label>
            <span className="seta" aria-hidden="true">→</span>
            <label className="campo" style={{ marginBottom: 0 }}>
              <span>Para</span>
              <input value={para} onChange={(e) => definirPara(e.target.value)}
                     placeholder="bob" autoComplete="off" spellCheck="false"
                     required />
            </label>
          </div>

          <label className={erro ? "campo heroi tem-erro" : "campo heroi"}
                 style={{ marginTop: "24px" }}>
            <span>Valor</span>
            <input value={valor} onChange={(e) => definirValor(e.target.value)}
                   placeholder="25.00" inputMode="decimal" required />
          </label>

          {erro && <p className="erro-do-campo" role="alert">{erro}</p>}

          <div className="botoes" style={{ marginTop: "16px" }}>
            <button type="submit" className="principal"
                    disabled={!completo || aEnviar}>
              {aEnviar ? "A confirmar…" : "Transferir"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
