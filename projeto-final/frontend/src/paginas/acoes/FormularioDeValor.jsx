import { useRef, useState } from "react";

import { criarIntencao } from "../../api/cliente.js";
import Aviso from "../../componentes/Aviso.jsx";
import Botao from "../../componentes/Botao.jsx";
import Campo from "../../componentes/Campo.jsx";
import CampoConta from "../../componentes/CampoConta.jsx";
import Ecra from "../../componentes/Ecra.jsx";
import { guardarContaEscolhida, lerContaEscolhida } from "../../lib/sessao.js";
import useContas from "../../lib/useContas.js";

// Depositar e sacar: uma conta, um valor, e o saldo que ficou. O valor vai
// como texto; quem o converte em centavos é o servidor.
export default function FormularioDeValor({ titulo, aEnviarTexto, enviar, nota }) {
  const { contas, recarregar } = useContas();
  const [conta, definirConta] = useState(lerContaEscolhida);
  const [valor, definirValor] = useState("");
  const [resultado, definirResultado] = useState(null);
  const [erro, definirErro] = useState(null);
  const [aEnviar, definirAEnviar] = useState(false);
  const intencao = useRef(criarIntencao()).current;

  async function aoEnviar(evento) {
    evento.preventDefault();
    definirErro(null);
    definirResultado(null);
    definirAEnviar(true);
    try {
      const resposta = await enviar(conta, valor.trim(), intencao);
      guardarContaEscolhida(conta);
      definirResultado(resposta);
      recarregar();
    } catch (falha) {
      definirErro(falha.message);
    } finally {
      definirAEnviar(false);
    }
  }

  return (
    <Ecra titulo={titulo} voltar>
      {nota && <Aviso>{nota}</Aviso>}
      <form className="cartao" onSubmit={aoEnviar}>
        <CampoConta contas={contas} valor={conta} aoMudar={definirConta} />
        <Campo rotulo="Valor" inputMode="decimal" placeholder="25.00" value={valor}
               onChange={(e) => definirValor(e.target.value)} required />
        <Aviso erro>{erro}</Aviso>
        <Botao disabled={aEnviar || !conta}>{aEnviar ? aEnviarTexto : titulo}</Botao>
      </form>
      {resultado && (
        <section className="cartao resultado" aria-live="polite">
          <p className="rotulo">Saldo depois</p>
          <p className="quantia">{resultado.saldo}</p>
          <p className="carimbo">✓ confirmado pela maioria dos nós</p>
        </section>
      )}
    </Ecra>
  );
}
