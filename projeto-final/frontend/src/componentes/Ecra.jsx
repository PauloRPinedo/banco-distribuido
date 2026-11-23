import { useEffect, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";

import { ouvirLeituraDeReplica } from "../api/cliente.js";
import { terminarSessao } from "../lib/sessao.js";
import Aviso from "./Aviso.jsx";
import {
  IconeCartao, IconeCasa, IconeEntrar, IconeEscudo, IconeLista, IconeMais, IconeMenu,
  IconeNos, IconeSair, IconeSetas, IconeTerminar,
} from "./Icones.jsx";

// Os destinos da aplicação, numa só lista: o menu do telemóvel e a barra
// lateral do computador mostram os mesmos, pela mesma ordem.
const DINHEIRO = [
  { titulo: "Abrir conta", texto: "Corrente, poupança ou prazo fixo, em BRL, USD ou PEN", para: "/contas/nova", Icone: IconeMais },
  { titulo: "Depositar", texto: "Pôr dinheiro numa conta", para: "/depositar", Icone: IconeEntrar },
  { titulo: "Sacar", texto: "Só o dono da conta", para: "/sacar", Icone: IconeSair },
  { titulo: "Transferir", texto: "Entre as tuas contas, para outra pessoa ou outro banco", para: "/transferir", Icone: IconeSetas },
  { titulo: "Extrato", texto: "Os movimentos de uma conta", para: "/extrato", Icone: IconeLista },
];

const MAIS = [
  { titulo: "Consultar saldo", texto: "O detalhe de uma conta", para: "/saldo", Icone: IconeCartao },
  { titulo: "Auditoria", texto: "O total do banco bate com o histórico?", para: "/auditoria", Icone: IconeEscudo },
  { titulo: "Estado do cluster", texto: "Os três nós, e quem é o primário", para: "/cluster", Icone: IconeNos },
];

// Ecrã largo, sessão iniciada: a marca, a navegação inteira e sair.
function BarraLateral({ aoSair }) {
  const ligacao = ({ titulo, para, Icone }) => (
    <NavLink key={para} to={para} end
             className={({ isActive }) => `item-lateral${isActive ? " ativo" : ""}`}>
      <Icone />
      <span>{titulo}</span>
    </NavLink>
  );
  return (
    <aside className="barra-lateral">
      <Link className="marca-lateral" to="/inicio">
        <img src="/logo.png" alt="" />
        <span>
          <strong>Banco distribuído</strong>
          <small>Três nós, uma só conta</small>
        </span>
      </Link>
      <nav aria-label="Navegação">
        {ligacao({ titulo: "Início", para: "/inicio", Icone: IconeCasa })}
        <p className="grupo-de-menu">Dinheiro</p>
        {DINHEIRO.map(ligacao)}
        <p className="grupo-de-menu">Mais</p>
        {MAIS.map(ligacao)}
      </nav>
      <button className="item-lateral sair" type="button" onClick={aoSair}>
        <IconeTerminar />
        <span>Sair</span>
      </button>
    </aside>
  );
}

// Ecrã largo, sem sessão: a metade da marca, ao lado do formulário.
function PainelDaMarca() {
  return (
    <section className="painel-da-marca" aria-hidden="true">
      <img src="/logo.png" alt="" />
      <h2>Banco distribuído</h2>
      <p>Contas, depósitos e transferências em três nós.</p>
      <ul>
        <li>Cada escrita é confirmada pela maioria antes de responder</li>
        <li>Se o primário cair, outro nó assume em menos de dois segundos</li>
        <li>Repetir uma operação nunca a duplica</li>
      </ul>
    </section>
  );
}

// A moldura de todos os ecrãs. No telemóvel: cabeçalho com o logótipo, voltar
// ou menu, e uma ação à direita (o olho do Início). No computador: a barra
// lateral (ou a marca, sem sessão) e o conteúdo ao lado.
//
// `publico` — entrada, registo e termos: sem barra lateral.
// `largura` — "estreita" (formulários), "media" (listas) ou "larga" (grelhas).
export default function Ecra({
  titulo, voltar = false, comMenu = false, acao = null, publico = false,
  largura = "estreita", children,
}) {
  const navegar = useNavigate();
  const [aberto, definirAberto] = useState(false);
  const [mais, definirMais] = useState(false);
  const [replica, definirReplica] = useState(null);
  useEffect(() => ouvirLeituraDeReplica(definirReplica), []);

  function sair() {
    terminarSessao();
    navegar("/entrar");
  }

  function linha({ titulo, texto, para }) {
    return (
      <Link key={para} className="item-de-menu" to={para} onClick={() => definirAberto(false)}>
        <strong>{titulo}</strong>
        <span>{texto}</span>
      </Link>
    );
  }

  return (
    <div className={publico ? "app app-publica" : "app app-privada"}>
      {publico ? <PainelDaMarca /> : <BarraLateral aoSair={sair} />}
      <div className={`pagina largura-${largura}`}>
        <div className="cabecalho">
          <header>
            <div className="lado-do-cabecalho">
              {voltar && (
                <button className="botao-icone voltar" type="button" aria-label="Voltar"
                        onClick={() => navegar(-1)}>
                  ←
                </button>
              )}
              {comMenu && (
                <button className="botao-icone abrir-menu" type="button"
                        aria-label={aberto ? "Fechar menu" : "Abrir menu"}
                        aria-expanded={aberto} aria-controls="menu-da-app"
                        onClick={() => definirAberto((valor) => !valor)}>
                  <IconeMenu />
                </button>
              )}
            </div>
            <div className="marca-e-titulo">
              <img className="logotipo" src="/logo.png" alt="" />
              <h1>{titulo}</h1>
            </div>
            <div className="lado-do-cabecalho direita">{acao}</div>
          </header>
          {comMenu && aberto && (
            <nav className="menu" id="menu-da-app" aria-label="Opções">
              <p className="grupo-de-menu">Dinheiro</p>
              {DINHEIRO.map(linha)}
              <button className="item-de-menu" type="button" onClick={() => definirMais((v) => !v)}>
                <strong>{mais ? "Ver menos" : "Ver mais"}</strong>
                <span>Saldo, auditoria e o estado do cluster</span>
              </button>
              {mais && (
                <>
                  <p className="grupo-de-menu">Mais</p>
                  {MAIS.map(linha)}
                </>
              )}
              <button className="item-de-menu sair" type="button" onClick={sair}>
                <strong>Sair</strong>
                <span>Terminar a sessão neste aparelho</span>
              </button>
            </nav>
          )}
        </div>
        <main>
          {replica && (
            <Aviso erro>
              O banco está sem primário. Estes dados vêm do nó {replica} e podem estar
              atrasados; as operações ficam paradas até haver maioria.
            </Aviso>
          )}
          {children}
        </main>
      </div>
    </div>
  );
}
