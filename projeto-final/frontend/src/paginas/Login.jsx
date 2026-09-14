import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/cliente.js";

// CU-17 — ver docs/entregables/02-casos-de-uso/cu-17-iniciar-sesion.md
export default function Login() {
  const [email, setEmail] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [error, setError] = useState(null);
  const navegar = useNavigate();

  async function enviar(evento) {
    evento.preventDefault();
    setError(null);
    try {
      const { token } = await api.login(email, contrasena);
      localStorage.setItem("token", token);
      navegar("/cuentas");
    } catch (err) {
      // mismo mensaje para email inexistente o contraseña incorrecta (E1/E2)
      setError("Email o contraseña incorrectos");
    }
  }

  return (
    <div className="telefono">
      <header>
        <h1>Iniciar sesión</h1>
      </header>
      <main>
        <form className="tarjeta" onSubmit={enviar}>
          <div className="campo">
            <label>Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="campo">
            <label>Contraseña</label>
            <input type="password" value={contrasena}
                   onChange={(e) => setContrasena(e.target.value)} required />
          </div>
          {error && (
            <div className="aviso aviso-error">
              <span className="punto">●</span>
              <span>{error}</span>
            </div>
          )}
          <button className="btn-confirmar" type="submit">Entrar</button>
        </form>
      </main>
    </div>
  );
}
