import { useEffect, useState } from "react";

import { api } from "../../api/cliente.js";
import Aviso from "../../componentes/Aviso.jsx";
import Botao from "../../componentes/Botao.jsx";
import Ecra from "../../componentes/Ecra.jsx";

// RF-14, moeda a moeda. Os dois totais vêm de cálculos independentes — a soma
// dos saldos e a soma do histórico — e é por serem independentes que
// concordarem prova alguma coisa.
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
    <Ecra titulo="Auditoria" voltar largura="larga">
      <Aviso>
        Soma os saldos de todas as contas e, à parte, soma o histórico de
        operações. Cada moeda tem de bater sozinha.
      </Aviso>
      {auditoria && moedas.length === 0 && <p className="legenda">Ainda não há dinheiro no banco.</p>}
      <div className="grelha">
      {moedas.map((linha) => (
        <section key={linha.moeda} className="cartao resultado">
          <p className="rotulo">{linha.moeda}</p>
          <div className="linhas">
            <div className="linha"><span>Somando os saldos</span><strong>{linha.total}</strong></div>
            <div className="linha"><span>Somando o histórico</span><strong>{linha.total_esperado}</strong></div>
            <div className="linha"><span>Diferença</span><strong>{linha.divergencia}</strong></div>
          </div>
          {linha.divergencia_centavos === 0
            ? <p className="selo selo-sucesso">✓ explicado</p>
            : <p className="selo selo-erro">há dinheiro por explicar</p>}
        </section>
      ))}
      </div>
      <Aviso erro>{erro}</Aviso>
      <Botao tipo="button" disabled={aCarregar} onClick={recarregar}>
        {aCarregar ? "A somar…" : "Conferir outra vez"}
      </Botao>

      <section className="cartao">
        <h2>Juros</h2>
        <p className="legenda">
          Poupanças e prazos fixos vencidos recebem juros num tick explícito. Cada
          pagamento entra no histórico, por isso a auditoria continua a bater.
        </p>
        {juros !== null && <p className="carimbo">✓ {juros} conta(s) com juros creditados</p>}
        <Botao tipo="button" variante="secundario" onClick={creditarJuros}>Creditar juros agora</Botao>
      </section>
    </Ecra>
  );
}
