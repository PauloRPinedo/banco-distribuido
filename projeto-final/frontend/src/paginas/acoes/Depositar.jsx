import { api } from "../../api/cliente.js";
import FormularioDeValor from "./FormularioDeValor.jsx";

export default function Depositar() {
  return <FormularioDeValor titulo="Depositar" aEnviarTexto="A depositar…" enviar={api.depositar} />;
}
