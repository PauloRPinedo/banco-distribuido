import { lazy, Suspense, useEffect } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";

import Carregamento from "./componentes/Carregamento.jsx";
import { lerToken } from "./lib/sessao.js";
import Entrar from "./paginas/Entrar.jsx";

// O ecrã de entrada vai na primeira descarga; cada um dos outros é um módulo à
// parte, que o navegador só pede quando se abre essa rota.
const Registo = lazy(() => import("./paginas/Registo.jsx"));
const Termos = lazy(() => import("./paginas/Termos.jsx"));
const Inicio = lazy(() => import("./paginas/Inicio.jsx"));
const AbrirConta = lazy(() => import("./paginas/acoes/AbrirConta.jsx"));
const Saldo = lazy(() => import("./paginas/acoes/Saldo.jsx"));
const Depositar = lazy(() => import("./paginas/acoes/Depositar.jsx"));
const Sacar = lazy(() => import("./paginas/acoes/Sacar.jsx"));
const Extrato = lazy(() => import("./paginas/acoes/Extrato.jsx"));
const Transferir = lazy(() => import("./paginas/acoes/Transferir.jsx"));
const Auditoria = lazy(() => import("./paginas/acoes/Auditoria.jsx"));
const Cluster = lazy(() => import("./paginas/acoes/Cluster.jsx"));

// Sem token, volta-se à entrada. Quem decide se o token vale é o servidor:
// um 401 em qualquer pedido termina a sessão (ver api/cliente.js).
function ComSessao({ children }) {
  return lerToken() ? children : <Navigate to="/entrar" replace />;
}

const PRIVADAS = [
  ["/inicio", Inicio],
  ["/contas/nova", AbrirConta],
  ["/saldo", Saldo],
  ["/depositar", Depositar],
  ["/sacar", Sacar],
  ["/extrato", Extrato],
  ["/transferir", Transferir],
  ["/auditoria", Auditoria],
  ["/cluster", Cluster],
];

export default function App() {
  const navegar = useNavigate();

  useEffect(() => {
    const aoTerminar = () => navegar("/entrar", { replace: true });
    window.addEventListener("banco:sessao-terminada", aoTerminar);
    return () => window.removeEventListener("banco:sessao-terminada", aoTerminar);
  }, [navegar]);

  return (
    <Suspense fallback={<Carregamento />}>
      <Routes>
        <Route path="/" element={<Navigate to={lerToken() ? "/inicio" : "/entrar"} replace />} />
        <Route path="/entrar" element={<Entrar />} />
        <Route path="/registo" element={<Registo />} />
        <Route path="/termos" element={<Termos />} />
        {PRIVADAS.map(([caminho, Pagina]) => (
          <Route key={caminho} path={caminho} element={<ComSessao><Pagina /></ComSessao>} />
        ))}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
