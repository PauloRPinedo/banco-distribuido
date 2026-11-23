import { api } from "../../api/cliente.js";
import FormularioDeValor from "./FormularioDeValor.jsx";

export default function Sacar() {
  return (
    <FormularioDeValor
      titulo="Sacar"
      aEnviarTexto="A sacar…"
      enviar={api.sacar}
      nota="Um prazo fixo não deixa sacar antes do vencimento, e nenhuma conta fica negativa."
    />
  );
}
