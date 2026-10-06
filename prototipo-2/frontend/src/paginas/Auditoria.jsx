import { useEffect, useState } from "react";

import { api } from "../api/cliente.js";

// RF-14, moeda a moeda. Os dois totais vêm de cálculos independentes — a soma
// dos saldos e a soma do histórico — e é por serem independentes que
// concordarem prova alguma coisa. Somar reais com dólares não daria número
// nenhum, por isso cada moeda é uma reconciliação à parte.
export default function Auditoria() {
  const [auditoria, definirAuditoria] = useState(null);
  const [erro, definirErro] = useState(null);
  const [aCarregar, definirACarregar] = useState(true);
  const [juros, definirJuros] = useState(null);

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

  async function creditarJuros() {
    definirErro(null);
    try {
      const { creditadas } = await api.creditarJuros();
      definirJuros(creditadas.length);
      await recarregar();
    } catch (falha) {
      definirErro(falha.message);
    }
  }

  useEffect(() => {
    recarregar();
  }, []);

  const moedas = auditoria?.moedas ?? [];

  return (
    <div className="livro-e-raio">
      <section className="cartao surge" aria-live="polite">
        <p className="rotulo-de-seccao">total em circulação, por moeda</p>
        {aCarregar && !auditoria && <p className="quantia-grande esqueleto">R$ 0.000,00</p>}
        {auditoria && moedas.length === 0 && (
          <p className="legenda">ainda não há dinheiro no banco</p>
        )}

        {moedas.map((linha) => (
          <div key={linha.moeda} className="reconciliacao" style={{ marginTop: "32px" }}>
            <p className="rotulo-de-seccao">{linha.moeda}</p>
            <div className="lado-a-lado">
              <div>
                <p className="rotulo-de-seccao">somando os saldos</p>
                <p className="quantia-media">{linha.total}</p>
              </div>
              <span className="sinal" aria-hidden="true">=</span>
              <div>
                <p className="rotulo-de-seccao">somando o histórico</p>
                <p className="quantia-media">{linha.total_esperado}</p>
              </div>
            </div>
            <div className="veredicto">
              <div>
                <p className="rotulo-de-seccao">divergência</p>
                <p className={linha.divergencia_centavos === 0
                  ? "quantia-media" : "quantia-media negativo"}>
                  {linha.divergencia}
                </p>
              </div>
              {linha.divergencia_centavos === 0 ? (
                <p className="carimbo">✓ explicado</p>
              ) : (
                <p className="aviso fora-do-ar">há dinheiro por explicar</p>
              )}
            </div>
          </div>
        ))}

        {auditoria && (
          <p className="legenda" style={{ marginTop: "24px" }}>
            Os dois lados são calculados de maneiras diferentes e nunca se olham
            um ao outro. Um câmbio tira numa moeda e põe noutra; cada uma tem de
            bater sozinha.
          </p>
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

        <section className="cartao surge">
          <h2>Juros</h2>
          <p className="legenda">
            Os juros de poupanças e prazos fixos vencidos pagam-se num tick
            explícito, não por um relógio escondido. Cada pagamento entra no
            histórico como uma operação, por isso a auditoria continua a bater.
          </p>
          {juros !== null && (
            <p className="carimbo">✓ {juros} conta(s) com juros creditados</p>
          )}
          <div className="botoes" style={{ marginTop: "16px" }}>
            <button type="button" onClick={creditarJuros}>Creditar juros agora</button>
          </div>
        </section>
      </div>
    </div>
  );
}
