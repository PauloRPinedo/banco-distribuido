import { useEffect, useState } from "react";
import { api } from "../api/cliente.js";

// CU-02/CU-03 — panel simple, pendiente el resto de mockups de 02-casos-de-uso
export default function Cuentas() {
  const [cuentaId, setCuentaId] = useState("");
  const [cuenta, setCuenta] = useState(null);
  const [error, setError] = useState(null);

  async function buscar(evento) {
    evento.preventDefault();
    setError(null);
    try {
      setCuenta(await api.consultarSaldo(cuentaId));
    } catch (err) {
      setError(err.message);
      setCuenta(null);
    }
  }

  return (
    <div className="telefono">
      <header>
        <h1>Consultar cuenta</h1>
      </header>
      <main>
        <form className="tarjeta" onSubmit={buscar}>
          <div className="campo">
            <label>Id de cuenta</label>
            <input value={cuentaId} onChange={(e) => setCuentaId(e.target.value)} required />
          </div>
          <button className="btn-confirmar" type="submit">Consultar</button>
        </form>

        {error && (
          <div className="aviso aviso-error">
            <span className="punto">●</span>
            <span>{error}</span>
          </div>
        )}

        {cuenta && (
          <div className="saldo-grande">
            <div className="etiqueta">Saldo</div>
            <div className="monto">
              {(cuenta.saldo_centavos / 100).toFixed(2)} {cuenta.moneda}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
