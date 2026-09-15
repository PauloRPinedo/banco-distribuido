import { useEffect, useState } from "react";

import { api } from "../api/cliente.js";

// RF-14. Os dois totais vêm de cálculos independentes: a soma dos saldos e a
// soma do histórico. Divergirem é dinheiro criado ou destruído, e é a única
// coisa que este projeto não admite (RNF-01).
export default function Auditoria() {
  const [auditoria, definirAuditoria] = useState(null);
  const [erro, definirErro] = useState(null);

  async function recarregar() {
    definirErro(null);
    try {
      definirAuditoria(await api.auditoria());
    } catch (falha) {
      definirErro(falha.message);
      definirAuditoria(null);
    }
  }

  useEffect(() => {
    recarregar();
  }, []);

  return (
    <div className="colunas">
      <section className="cartao destaque">
        <h2>Total em circulação</h2>
        <p className="total">{auditoria ? auditoria.total : "—"}</p>
        <div className="botoes">
          <button type="button" onClick={recarregar}>Recarregar</button>
        </div>
        {erro && <p className="aviso fora-do-ar">{erro}</p>}
      </section>

      <section className="cartao">
        <h2>Conferência</h2>
        {auditoria && (
          <>
            <table className="tabela">
              <tbody>
                <tr>
                  <td>soma dos saldos</td>
                  <td className="direita">{auditoria.total}</td>
                </tr>
                <tr>
                  <td>soma do histórico</td>
                  <td className="direita">{auditoria.total_esperado}</td>
                </tr>
                <tr>
                  <td>divergência</td>
                  <td className="direita">{auditoria.divergencia}</td>
                </tr>
              </tbody>
            </table>

            <p className={auditoria.divergente ? "aviso fora-do-ar" : "aviso carimbo"}>
              {auditoria.divergente
                ? "há dinheiro por explicar"
                : "o dinheiro está todo explicado"}
            </p>
          </>
        )}
      </section>
    </div>
  );
}
