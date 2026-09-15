import { useEffect, useState } from "react";

import { api } from "./api/cliente.js";
import Auditoria from "./paginas/Auditoria.jsx";
import Contas from "./paginas/Contas.jsx";
import Transferir from "./paginas/Transferir.jsx";

// Sem router e sem barra lateral: CODESTYLE 7.4 diz que é um ecrã só, e não
// há mesmo para onde ir. Três separadores chegam, e poupam uma dependência.
const SEPARADORES = [
  { id: "contas", titulo: "Contas", Painel: Contas },
  { id: "transferir", titulo: "Transferir", Painel: Transferir },
  { id: "auditoria", titulo: "Auditoria", Painel: Auditoria },
];

export default function App() {
  const [aberto, definirAberto] = useState("contas");
  const [no, definirNo] = useState(null);

  // Dois nós contra a mesma base servem painéis idênticos. Sem isto, a meio da
  // demonstração ninguém sabe qual dos ecrãs é qual.
  useEffect(() => {
    api.saude().then((estado) => definirNo(estado.no)).catch(() => definirNo(null));
  }, []);

  const { Painel } = SEPARADORES.find((separador) => separador.id === aberto);

  return (
    <div className="pagina">
      {/* Cabeçalho de papel timbrado: quem emite à esquerda, quem atendeu à
          direita, e um fio duplo a fechar. */}
      <header className="cabecalho">
        <div>
          <h1>Banco distribuído</h1>
          <p className="legenda">Protótipo 1 · extrato de contas</p>
        </div>
        {no && <span className="selo-do-no">atendido pelo nó {no}</span>}
      </header>

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
        {/* A chave remonta o ecrã ao trocar de separador, e é isso que faz a
            entrada escalonada acontecer de cada vez. */}
        <Painel key={aberto} />
      </main>

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
