// Habla siempre con el balanceador (/api en desarrollo, ver vite.config.js;
// en producción, Nginx reenvía /api al balanceador — ver nginx.conf).
const BASE = "/api";

function opId() {
  return crypto.randomUUID();
}

async function peticion(ruta, { metodo = "GET", cuerpo, token } = {}) {
  const cabeceras = { "Content-Type": "application/json" };
  if (metodo !== "GET") cabeceras["X-Op-Id"] = opId();
  if (token) cabeceras["Authorization"] = `Bearer ${token}`;

  const respuesta = await fetch(`${BASE}${ruta}`, {
    method: metodo,
    headers: cabeceras,
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
  });

  const datos = await respuesta.json().catch(() => null);
  if (!respuesta.ok) {
    throw new Error(datos?.detail?.mensagem || datos?.detail || "error de red");
  }
  return datos;
}

export const api = {
  login: (email, contrasena) =>
    peticion("/auth/login", { metodo: "POST", cuerpo: { email, contrasena } }),
  crearCuenta: (usuario_id, moneda, saldo_inicial_centavos) =>
    peticion("/cuentas", { metodo: "POST", cuerpo: { usuario_id, moneda, saldo_inicial_centavos } }),
  consultarSaldo: (cuentaId) => peticion(`/cuentas/${cuentaId}`),
  consultarExtracto: (cuentaId) => peticion(`/cuentas/${cuentaId}/extracto`),
  depositar: (cuentaId, montoCentavos) =>
    peticion(`/cuentas/${cuentaId}/deposito`, { metodo: "POST", cuerpo: { monto_centavos: montoCentavos } }),
  transferir: (origenId, destinoId, montoCentavos) =>
    peticion("/transferencias", {
      metodo: "POST",
      cuerpo: { cuenta_origen_id: origenId, cuenta_destino_id: destinoId, monto_centavos: montoCentavos },
    }),
};
