import { numeroVisivel } from "../lib/dinheiro.js";
import Campo from "./Campo.jsx";

// Escolher uma das contas de quem tem a sessão. `contas` vem de useContas().
export default function CampoConta({ rotulo = "Conta", contas, valor, aoMudar, excluir = "" }) {
  const escolhiveis = contas.filter((conta) => conta.conta !== excluir);
  if (escolhiveis.length === 0) {
    return <p className="legenda">Primeiro abre uma conta.</p>;
  }
  const conhecida = escolhiveis.some((conta) => conta.conta === valor);
  return (
    <Campo rotulo={rotulo}>
      <select value={conhecida ? valor : ""} onChange={(e) => aoMudar(e.target.value)} required>
        <option value="">Escolhe uma conta</option>
        {escolhiveis.map((conta) => (
          <option key={conta.conta} value={conta.conta}>
            {conta.moeda} · {numeroVisivel(conta)} · {conta.saldo}
          </option>
        ))}
      </select>
    </Campo>
  );
}
