import { useState } from "react";

import { api } from "../api/cliente.js";

// CU-17: iniciar sessão, e o registo que vem antes dele.
export default function Login({ aoEntrar }) {
  const [modo, definirModo] = useState("entrar");
  const [nome, definirNome] = useState("");
  const [email, definirEmail] = useState("");
  const [senha, definirSenha] = useState("");
  const [erro, definirErro] = useState(null);
  const [aEnviar, definirAEnviar] = useState(false);

  const registo = modo === "registar";

  async function enviar(evento) {
    evento.preventDefault();
    definirErro(null);
    definirAEnviar(true);
    try {
      if (registo) await api.registar(nome, email, senha);
      await api.entrar(email, senha);
      aoEntrar();
    } catch (falha) {
      // No login, a mesma mensagem para email inexistente ou senha errada
      // (E1/E2): é o servidor que a escreve assim.
      definirErro(falha.message);
    } finally {
      definirAEnviar(false);
    }
  }

  return (
    <div className="livro-e-raio">
      <section className="cartao surge">
        <p className="rotulo-de-seccao">sessão</p>
        <p className="quantia-grande">{registo ? "Criar utilizador" : "Entrar"}</p>
        <p className="legenda">
          Cada conta tem um dono. Só ele a consulta, saca dela ou transfere a
          partir dela; depositar e receber transferências fica aberto a todos.
        </p>
      </section>

      <div className="raio">
        <form className="cartao surge" onSubmit={enviar}>
          <h2>{registo ? "Registo" : "Iniciar sessão"}</h2>

          {registo && (
            <label className="campo">
              <span>Nome</span>
              <input value={nome} onChange={(e) => definirNome(e.target.value)}
                     autoComplete="name" required />
            </label>
          )}
          <label className="campo">
            <span>Email</span>
            <input type="email" value={email}
                   onChange={(e) => definirEmail(e.target.value)}
                   autoComplete="email" required />
          </label>
          <label className={erro ? "campo tem-erro" : "campo"}>
            <span>Senha{registo ? " — 6 caracteres ou mais" : ""}</span>
            <input type="password" value={senha}
                   onChange={(e) => definirSenha(e.target.value)}
                   autoComplete={registo ? "new-password" : "current-password"}
                   required />
          </label>

          {erro && <p className="erro-do-campo" role="alert">{erro}</p>}

          <div className="botoes" style={{ marginTop: "16px" }}>
            <button type="submit" className="principal" disabled={aEnviar}>
              {aEnviar ? "A enviar…" : registo ? "Registar e entrar" : "Entrar"}
            </button>
            <button type="button" onClick={() => {
              definirModo(registo ? "entrar" : "registar");
              definirErro(null);
            }}>
              {registo ? "Já tenho conta" : "Criar utilizador"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
