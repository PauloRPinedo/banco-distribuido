import { useEffect, useState } from "react";

import { api } from "../../api/cliente.js";
import Aviso from "../../componentes/Aviso.jsx";
import CampoConta from "../../componentes/CampoConta.jsx";
import Ecra from "../../componentes/Ecra.jsx";
import { PRODUTOS, numeroVisivel, percentagem } from "../../lib/dinheiro.js";
import { guardarContaEscolhida, lerContaEscolhida } from "../../lib/sessao.js";
import useContas from "../../lib/useContas.js";

// RF-02. Lê-se do primário, que é quem o balanceador escolhe.
export default function Saldo() {
  const { contas } = useContas();
  const [conta, definirConta] = useState(lerContaEscolhida);
  const [dados, definirDados] = useState(null);
  const [erro, definirErro] = useState(null);

  useEffect(() => {
    if (!conta) return;
    guardarContaEscolhida(conta);
    definirErro(null);
    api.consultarSaldo(conta).then(definirDados).catch((falha) => {
      definirDados(null);
      definirErro(falha.message);
    });
  }, [conta]);

  return (
    <Ecra titulo="Consultar saldo" voltar>
      <div className="cartao">
        <CampoConta contas={contas} valor={conta} aoMudar={definirConta} />
      </div>
      <Aviso erro>{erro}</Aviso>
      {dados && (
        <section className="cartao resultado" aria-live="polite">
          <p className="rotulo">{numeroVisivel(dados)}</p>
          <p className="quantia">{dados.saldo}</p>
          <div className="linhas">
            <div className="linha"><span>Moeda</span><strong>{dados.moeda}</strong></div>
            <div className="linha"><span>Produto</span><strong>{PRODUTOS[dados.produto]}</strong></div>
            {dados.taxa_juros && (
              <div className="linha"><span>Juros</span><strong>{percentagem(dados.taxa_juros)} ao ano</strong></div>
            )}
            {dados.vence_em && (
              <div className="linha">
                <span>Vence a</span>
                <strong>{new Date(dados.vence_em * 1000).toLocaleDateString("pt-PT")}</strong>
              </div>
            )}
            <div className="linha"><span>Id interno</span><strong>{dados.conta}</strong></div>
          </div>
        </section>
      )}
    </Ecra>
  );
}
