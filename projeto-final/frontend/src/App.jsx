import { Navigate, Route, Routes } from "react-router-dom";
import Login from "./paginas/Login.jsx";
import Cuentas from "./paginas/Cuentas.jsx";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<Login />} />
      <Route path="/cuentas" element={<Cuentas />} />
    </Routes>
  );
}
