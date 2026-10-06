import { useEffect, useState } from "react";

import { api, sessao } from "./api/cliente.js";
import Auditoria from "./paginas/Auditoria.jsx";
import Cluster from "./paginas/Cluster.jsx";
import Contas from "./paginas/Contas.jsx";
import Login from "./paginas/Login.jsx";
import Transferir from "./paginas/Transferir.jsx";

// Sem router: é um ecrã só. Sem sessão mostra-se o login; com sessão, três
// separadores chegam, e poupam uma dependência.
const SEPARADORES = [
  { id: "contas", titulo: "Contas", Painel: Contas },
  { id: "transferir", titulo: "Transferir", Painel: Transferir },
  { id: "auditoria", titulo: "Auditoria", Painel: Auditoria },
  { id: "cluster", titulo: "Cluster", Painel: Cluster },
];

export default function App() {
  const [autenticado, definirAutenticado] = useState(() => Boolean(sessao.token()));
  const [aberto, definirAberto] = useState("contas");
  const [no, definirNo] = useState(null);

  // Um 401 em qualquer pedido termina a sessão; o cliente avisa por evento.
  useEffect(() => {
    const aoTerminar = () => definirAutenticado(false);
    window.addEventListener("banco:sessao-terminada", aoTerminar);
    return () => window.removeEventListener("banco:sessao-terminada", aoTerminar);
  }, []);

  // O balanceador manda tudo ao primário. O selo diz qual é, e em que epoch:
  // depois de um failover, muda sozinho.
  useEffect(() => {
    api.estadoDoNo()
      .then((estado) => definirNo(`${estado.no} · ${estado.papel} · epoch ${estado.epoch}`))
      .catch(() => definirNo(null));
    const relogio = setInterval(() => {
      api.estadoDoNo()
        .then((estado) => definirNo(`${estado.no} · ${estado.papel} · epoch ${estado.epoch}`))
        .catch(() => definirNo(null));
    }, 3000);
    return () => clearInterval(relogio);
  }, [aberto, autenticado]);

  const { Painel } = SEPARADORES.find((separador) => separador.id === aberto);

  return (
    <div className="pagina">
      <header className="cabecalho">
        <div>
          <h1>Banco distribuído</h1>
          <p className="legenda">Protótipo 2 · três nós atrás de um balanceador</p>
        </div>
        <div className="botoes">
          {no && <span className="selo-do-no">nó {no}</span>}
          {autenticado && (
            <button type="button" onClick={() => sessao.terminar()}>Sair</button>
          )}
        </div>
      </header>

      {autenticado ? (
        <>
          <nav className="separadores">
            {SEPARADORES.map(({ id, titulo }) => (
              <button
                key={id}
                type="button"
                className={id === aberto ? "separador aberto" : "separador"}
                aria-current={id === aberto ? "page" : undefined}
                onClick={() => definirAberto(id)}
              >
                {titulo}
              </button>
            ))}
          </nav>
          <main>
            <Painel key={aberto} />
          </main>
        </>
      ) : (
        <main>
          <Login aoEntrar={() => definirAutenticado(true)} />
        </main>
      )}

      <footer className="rodape">
        <p>Trabalho de Computação Distribuída · ICMC-USP, campus São Carlos</p>
        <p>
          Jefferson Daniel Flores Montenegro · Cristhian Jesus Maylle Briceño ·
          Paulo Sebastian Rojo Pinedo
        </p>
      </footer>
    </div>
  );
}
