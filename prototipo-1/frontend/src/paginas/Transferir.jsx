import { useState } from "react";

import { api } from "../api/cliente.js";

// RF-04 e RF-05: ou as duas contas mudam, ou nenhuma muda.
export default function Transferir() {
  const [de, definirDe] = useState("");
  const [para, definirPara] = useState("");
  const [valor, definirValor] = useState("");
  const [feita, definirFeita] = useState(null);
  const [erro, definirErro] = useState(null);

  async function enviar(evento) {
    evento.preventDefault();
    definirErro(null);
    try {
      definirFeita(await api.transferir(de, para, valor));
    } catch (falha) {
      definirErro(falha.message);
      definirFeita(null);
    }
  }

  return (
    <div className="colunas">
      <form className="cartao" onSubmit={enviar}>
        <h2>Transferir</h2>

        <label className="campo">
          <span>De</span>
          <input value={de} onChange={(evento) => definirDe(evento.target.value)}
                 placeholder="alice" required />
        </label>

        <label className="campo">
          <span>Para</span>
          <input value={para} onChange={(evento) => definirPara(evento.target.value)}
                 placeholder="bob" required />
        </label>

        <label className="campo">
          <span>Valor</span>
          <input value={valor} onChange={(evento) => definirValor(evento.target.value)}
                 placeholder="25.00" inputMode="decimal" required />
        </label>

        <div className="botoes">
          <button type="submit" className="principal">Transferir</button>
        </div>

        {erro && <p className="aviso fora-do-ar">{erro}</p>}
      </form>

      <section className="cartao">
        <h2>Resultado</h2>
        {feita ? (
          <>
            <p className="aviso carimbo">transferência confirmada</p>
            <table className="tabela">
              <tbody>
                {Object.entries(feita.saldos).map(([conta, saldo]) => (
                  <tr key={conta}>
                    <td>{conta}</td>
                    <td className="direita">{saldo}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : (
          <p className="legenda">ainda não foi feita nenhuma transferência</p>
        )}
      </section>
    </div>
  );
}
