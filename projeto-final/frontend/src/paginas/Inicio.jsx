import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import Ecra from "../componentes/Ecra.jsx";
import { IconeEntrar, IconeLista, IconeOlho, IconeSair, IconeSetas } from "../componentes/Icones.jsx";
import { PRODUTOS, numeroVisivel } from "../lib/dinheiro.js";
import {
  guardarContaEscolhida, guardarPrincipal, guardarSaldosVisiveis,
  lerPrincipal, lerSaldosVisiveis,
} from "../lib/sessao.js";
import useContas from "../lib/useContas.js";
import useEcraLargo from "../lib/useEcraLargo.js";

const ATALHOS = [
  { para: "/depositar", titulo: "Depositar", Icone: IconeEntrar },
  { para: "/transferir", titulo: "Transferir", Icone: IconeSetas },
  { para: "/sacar", titulo: "Sacar", Icone: IconeSair },
  { para: "/extrato", titulo: "Extrato", Icone: IconeLista },
];

// No telemóvel, duas contas e "ver todas"; no computador cabem seis.
const VISIVEIS_NO_TELEMOVEL = 2;
const VISIVEIS_NO_COMPUTADOR = 6;
const OCULTO = "••••";

export default function Inicio() {
  const navegar = useNavigate();
  const { contas, aCarregar, erro } = useContas();
  const visiveis = useEcraLargo() ? VISIVEIS_NO_COMPUTADOR : VISIVEIS_NO_TELEMOVEL;
  const [verSaldos, definirVerSaldos] = useState(lerSaldosVisiveis);
  const [todas, definirTodas] = useState(false);
  const [principal, definirPrincipal] = useState(lerPrincipal);

  function alternarSaldos() {
    guardarSaldosVisiveis(!verSaldos);
    definirVerSaldos(!verSaldos);
  }

  function abrir(conta) {
    guardarContaEscolhida(conta.conta);
    navegar("/extrato");
  }

  function tornarPrincipal(conta) {
    guardarPrincipal(conta.conta);
    definirPrincipal(conta.conta);
  }

  const destacada = contas.find((conta) => conta.conta === principal) || contas[0] || null;
  const mostradas = todas ? contas : contas.slice(0, visiveis);

  return (
    <Ecra
      titulo="Início"
      comMenu
      largura="larga"
      acao={(
        <button className="botao-icone" type="button" aria-pressed={!verSaldos}
                aria-label={verSaldos ? "Ocultar saldos" : "Mostrar saldos"}
                onClick={alternarSaldos}>
          <IconeOlho fechado={!verSaldos} />
        </button>
      )}
    >
      <div className="topo-do-inicio">
      <section className="destaque" aria-label="Saldo disponível">
        <p className="rotulo-do-destaque">Saldo disponível</p>
        <p className="quantia-do-destaque">
          {destacada ? (verSaldos ? destacada.saldo : OCULTO) : "—"}
        </p>
        {destacada && <p className="rotulo-do-destaque">{numeroVisivel(destacada)}</p>}
      </section>

      <nav className="atalhos" aria-label="Dinheiro">
        {ATALHOS.map(({ para, titulo, Icone }) => (
          <Link key={para} className="atalho" to={para}>
            <span className="bolha"><Icone /></span>
            {titulo}
          </Link>
        ))}
      </nav>
      </div>

      <div className="bloco-de-contas">
        <div className="titulo-com-acao">
          <h2>As tuas contas</h2>
          <Link to="/contas/nova">+ Abrir conta</Link>
        </div>
        {aCarregar && contas.length === 0 && <p className="legenda">A carregar contas…</p>}
        {erro && <p className="legenda">{erro}</p>}
        {!aCarregar && !erro && contas.length === 0 && (
          <div className="vazio">
            <p>Ainda não há contas em teu nome.</p>
            <Link to="/contas/nova">Abrir a primeira</Link>
          </div>
        )}
        <div className="cartoes-de-conta">
          {mostradas.map((conta, indice) => {
            const ePrincipal = conta.conta === destacada?.conta;
            return (
              <article key={conta.conta} className={`cartao-de-conta tom-${indice % 3}`}>
                <button type="button" className="corpo-da-conta" onClick={() => abrir(conta)}>
                  <span className="topo-da-conta">
                    <span>{conta.moeda} · {PRODUTOS[conta.produto]}</span>
                    <span>{ePrincipal ? "Principal" : ""}</span>
                  </span>
                  <span className="saldo-da-conta">{verSaldos ? conta.saldo : OCULTO}</span>
                  <span className="numero-da-conta">{numeroVisivel(conta)}</span>
                </button>
                {!ePrincipal && (
                  <button type="button" className="botao-texto" onClick={() => tornarPrincipal(conta)}>
                    Usar como principal
                  </button>
                )}
              </article>
            );
          })}
        </div>
        {contas.length > visiveis && (
          <button className="botao-expandir" type="button" onClick={() => definirTodas((v) => !v)}>
            {todas ? "Ver menos" : `Ver as ${contas.length} contas`}
          </button>
        )}
      </div>
    </Ecra>
  );
}
