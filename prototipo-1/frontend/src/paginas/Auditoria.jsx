import { useEffect, useState } from "react";

import { api } from "../api/cliente.js";

// RF-14. Os dois totais vêm de cálculos independentes — a soma dos saldos e a
// soma do histórico — e é por serem independentes que concordarem prova
// alguma coisa. Por isso o ecrã é uma reconciliação, com os dois lados à vista,
// e não um número solitário.
export default function Auditoria() {
  const [auditoria, definirAuditoria] = useState(null);
  const [erro, definirErro] = useState(null);
  const [aCarregar, definirACarregar] = useState(true);

  async function recarregar() {
    definirErro(null);
    definirACarregar(true);
    try {
      definirAuditoria(await api.auditoria());
    } catch (falha) {
      definirErro(falha.message);
      definirAuditoria(null);
    } finally {
      definirACarregar(false);
    }
  }

  useEffect(() => {
    recarregar();
  }, []);

  const certo = auditoria && !auditoria.divergente;

  return (
    <div className="livro-e-raio">
      <section className="cartao surge" aria-live="polite">
        <p className="rotulo-de-seccao">total em circulação</p>
        <p className={aCarregar ? "quantia-grande esqueleto" : "quantia-grande"}>
          {auditoria ? auditoria.total : "R$ 0.000,00"}
        </p>

        {auditoria && (
          <div className="reconciliacao" style={{ marginTop: "40px" }}>
            <div className="lado-a-lado">
              <div>
                <p className="rotulo-de-seccao">somando os saldos</p>
                <p className="quantia-media">{auditoria.total}</p>
                <p className="legenda">o que as contas dizem que existe</p>
              </div>
              <span className="sinal" aria-hidden="true">=</span>
              <div>
                <p className="rotulo-de-seccao">somando o histórico</p>
                <p className="quantia-media">{auditoria.total_esperado}</p>
                <p className="legenda">o que as operações dizem que devia existir</p>
              </div>
            </div>

            <div className="veredicto">
              <div>
                <p className="rotulo-de-seccao">divergência</p>
                <p className={
                  certo ? "quantia-media" : "quantia-media negativo"
                }>
                  {auditoria.divergencia}
                </p>
              </div>
              {certo ? (
                <p className="carimbo">✓ o dinheiro está todo explicado</p>
              ) : (
                <p className="aviso fora-do-ar">há dinheiro por explicar</p>
              )}
            </div>

            <p className="legenda">
              Os dois lados são calculados de maneiras diferentes e nunca se
              olham um ao outro. Somar duas vezes a mesma estrutura não auditaria
              nada.
            </p>
          </div>
        )}

        {erro && <p className="aviso fora-do-ar" role="alert">{erro}</p>}
      </section>

      <div className="raio">
        <section className="cartao surge">
          <h2>Conferir</h2>
          <p className="legenda">
            A auditoria lê o estado no momento em que se pede. Correr outra vez
            depois de uma transferência é a maneira mais direta de ver que o
            total não mudou.
          </p>
          <div className="botoes" style={{ marginTop: "16px" }}>
            <button type="button" className="principal" onClick={recarregar}
                    disabled={aCarregar}>
              {aCarregar ? "A somar…" : "Conferir outra vez"}
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}
