import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { api } from "../api/cliente.js";
import Aviso from "../componentes/Aviso.jsx";
import Botao from "../componentes/Botao.jsx";
import Campo from "../componentes/Campo.jsx";
import Ecra from "../componentes/Ecra.jsx";

// CU-17. Este ecrã vai na primeira descarga; os outros são módulos à parte.
export default function Entrar() {
  const [email, definirEmail] = useState("");
  const [senha, definirSenha] = useState("");
  const [erro, definirErro] = useState(null);
  const [aEnviar, definirAEnviar] = useState(false);
  const navegar = useNavigate();
  const aviso = useLocation().state?.aviso;

  async function enviar(evento) {
    evento.preventDefault();
    definirErro(null);
    definirAEnviar(true);
    try {
      await api.entrar(email, senha);
      navegar("/inicio", { replace: true });
    } catch (falha) {
      // A mesma mensagem para email inexistente e senha errada (E1/E2): é o
      // servidor que a escreve assim.
      definirErro(falha.message);
    } finally {
      definirAEnviar(false);
    }
  }

  return (
    <Ecra titulo="Entrar" publico>
      <div className="capa">
        <img src="/logo.png" alt="" />
        <strong>Banco distribuído</strong>
        <p>Contas, depósitos e transferências em três nós</p>
      </div>
      <form className="cartao" onSubmit={enviar}>
        <Campo rotulo="Email" type="email" autoComplete="email" value={email}
               onChange={(e) => definirEmail(e.target.value)} required />
        <Campo rotulo="Senha" type="password" autoComplete="current-password" value={senha}
               onChange={(e) => definirSenha(e.target.value)} required />
        <Aviso>{aviso}</Aviso>
        <Aviso erro>{erro}</Aviso>
        <Botao disabled={aEnviar}>{aEnviar ? "A entrar…" : "Entrar"}</Botao>
      </form>
      <div className="ligacoes">
        <Link to="/registo">Criar utilizador</Link>
        <Link to="/termos">Termos e condições</Link>
      </div>
    </Ecra>
  );
}
