import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api/cliente.js";
import Aviso from "../componentes/Aviso.jsx";
import Botao from "../componentes/Botao.jsx";
import Campo from "../componentes/Campo.jsx";
import Ecra from "../componentes/Ecra.jsx";
import TextoTermos from "./TextoTermos.jsx";

// O registo vai pelo log replicado (como qualquer escrita), por isso o
// utilizador existe nos três nós antes de este ecrã avançar.
export default function Registo() {
  const [nome, definirNome] = useState("");
  const [email, definirEmail] = useState("");
  const [senha, definirSenha] = useState("");
  const [aceita, definirAceita] = useState(false);
  const [verTermos, definirVerTermos] = useState(false);
  const [erro, definirErro] = useState(null);
  const [aEnviar, definirAEnviar] = useState(false);
  const navegar = useNavigate();

  async function enviar(evento) {
    evento.preventDefault();
    definirErro(null);
    definirAEnviar(true);
    try {
      await api.registar(nome, email, senha);
      await api.entrar(email, senha);
      navegar("/inicio", { replace: true });
    } catch (falha) {
      definirErro(falha.message);
    } finally {
      definirAEnviar(false);
    }
  }

  return (
    <Ecra titulo="Criar utilizador" voltar publico>
      <form className="cartao" onSubmit={enviar}>
        <Campo rotulo="Nome" autoComplete="name" value={nome}
               onChange={(e) => definirNome(e.target.value)} required />
        <Campo rotulo="Email" type="email" autoComplete="email" value={email}
               onChange={(e) => definirEmail(e.target.value)} required />
        <Campo rotulo="Senha" ajuda="6 caracteres ou mais" type="password"
               autoComplete="new-password" minLength={6} value={senha}
               onChange={(e) => definirSenha(e.target.value)} required />
        <label className="caixa">
          <input type="checkbox" checked={aceita} onChange={(e) => definirAceita(e.target.checked)} />
          <span>
            Aceito os{" "}
            <button type="button" className="botao-ligacao" onClick={() => definirVerTermos(true)}>
              termos e condições
            </button>
          </span>
        </label>
        <Aviso erro>{erro}</Aviso>
        <Botao disabled={!aceita || aEnviar}>{aEnviar ? "A criar…" : "Registar e entrar"}</Botao>
      </form>
      {/* Numa cortina, para não apagar o que já se escreveu no formulário. */}
      {verTermos && (
        <div className="cortina" role="dialog" aria-modal="true" aria-label="Termos e condições">
          <TextoTermos aoFechar={() => definirVerTermos(false)} />
        </div>
      )}
    </Ecra>
  );
}
