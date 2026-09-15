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

  // Os dois portáteis servem painéis idênticos contra a mesma base. Sem isto,
  // a meio da demonstração ninguém sabe qual dos ecrãs é qual.
  useEffect(() => {
    api.saude().then((estado) => definirNo(estado.no)).catch(() => definirNo(null));
  }, []);

  const { Painel } = SEPARADORES.find((separador) => separador.id === aberto);

  return (
    <div className="pagina">
      <header className="cabecalho">
        <h1>Banco distribuído</h1>
        <p className="legenda">
          Protótipo 1{no ? ` · nó ${no}` : ""}
        </p>
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
