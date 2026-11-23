import { useRef, useState } from "react";
import { Link } from "react-router-dom";

import { api, criarIntencao } from "../../api/cliente.js";
import Aviso from "../../componentes/Aviso.jsx";
import Botao from "../../componentes/Botao.jsx";
import Campo from "../../componentes/Campo.jsx";
import Ecra from "../../componentes/Ecra.jsx";
import { PRODUTOS, numeroVisivel } from "../../lib/dinheiro.js";
import { guardarContaEscolhida } from "../../lib/sessao.js";

// RF-01, RF-19 e RF-23/24. O número (agência 0001 e dígito verificador)
// sorteia-o o primário; o dono é quem tem a sessão.
export default function AbrirConta() {
  const [moeda, definirMoeda] = useState("BRL");
  const [produto, definirProduto] = useState("corrente");
  const [taxaJuros, definirTaxaJuros] = useState("");
  const [prazoDias, definirPrazoDias] = useState("");
  const [saldoInicial, definirSaldoInicial] = useState("");
  const [aberta, definirAberta] = useState(null);
  const [erro, definirErro] = useState(null);
  const [aEnviar, definirAEnviar] = useState(false);
  // Carregar outra vez depois de uma falha de rede não abre duas contas.
  const intencao = useRef(criarIntencao()).current;

  async function enviar(evento) {
    evento.preventDefault();
    definirErro(null);
    definirAberta(null);
    definirAEnviar(true);
    try {
      const resposta = await api.criarConta(saldoInicial, {
        moeda,
        produto,
        taxa_juros: produto === "corrente" ? "" : taxaJuros,
        prazo_dias: produto === "prazo_fixo" ? Number(prazoDias) || "" : "",
      }, intencao);
      guardarContaEscolhida(resposta.conta);
      definirAberta(resposta);
    } catch (falha) {
      definirErro(falha.message);
    } finally {
      definirAEnviar(false);
    }
  }

  return (
    <Ecra titulo="Abrir conta" voltar>
      <form className="cartao" onSubmit={enviar}>
        <div className="par">
          <Campo rotulo="Moeda">
            <select value={moeda} onChange={(e) => definirMoeda(e.target.value)}>
              <option>BRL</option><option>USD</option><option>PEN</option>
            </select>
          </Campo>
          <Campo rotulo="Produto">
            <select value={produto} onChange={(e) => definirProduto(e.target.value)}>
              {Object.entries(PRODUTOS).map(([id, nome]) => <option key={id} value={id}>{nome}</option>)}
            </select>
          </Campo>
        </div>
        {produto !== "corrente" && (
          <Campo rotulo="Taxa de juros ao ano" ajuda={'"0.10" é 10 % ao ano'} inputMode="decimal"
                 placeholder="0.10" value={taxaJuros}
                 onChange={(e) => definirTaxaJuros(e.target.value)} required />
        )}
        {produto === "prazo_fixo" && (
          <Campo rotulo="Prazo em dias" ajuda="Até ao vencimento não se pode sacar"
                 inputMode="numeric" placeholder="30" value={prazoDias}
                 onChange={(e) => definirPrazoDias(e.target.value)} required />
        )}
        <Campo rotulo="Saldo inicial" inputMode="decimal" placeholder="0.00" value={saldoInicial}
               onChange={(e) => definirSaldoInicial(e.target.value)} />
        <Aviso erro>{erro}</Aviso>
        <Botao disabled={aEnviar}>{aEnviar ? "A abrir…" : "Abrir conta"}</Botao>
      </form>

      {aberta && (
        <section className="cartao resultado" aria-live="polite">
          <p className="rotulo">Conta aberta</p>
          <p className="quantia">{aberta.saldo}</p>
          <p className="numero-grande">{numeroVisivel(aberta)}</p>
          <p className="legenda">
            É este número que dás a quem te quiser transferir. A conta já está
            nos três nós.
          </p>
          <Link className="botao-secundario como-botao" to="/inicio">Ir para o início</Link>
        </section>
      )}
    </Ecra>
  );
}
