import { useState } from "react";

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
  const { Painel } = SEPARADORES.find((separador) => separador.id === aberto);

  return (
    <div className="pagina">
      <header className="cabecalho">
        <h1>Banco distribuído</h1>
        <p className="legenda">Protótipo 1 — um nó só</p>
      </header>

      <nav className="separadores">
        {SEPARADORES.map(({ id, titulo }) => (
          <button
            key={id}
            type="button"
            className={id === aberto ? "separador aberto" : "separador"}
            onClick={() => definirAberto(id)}
          >
            {titulo}
          </button>
        ))}
      </nav>

      <main>
        <Painel />
      </main>
    </div>
  );
}
