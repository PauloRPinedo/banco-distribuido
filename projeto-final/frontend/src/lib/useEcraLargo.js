import { useEffect, useState } from "react";

// A fronteira do tablet no estilo.css: de 768px para cima as contas do Início
// ficam em grelha e cabem mais; abaixo, uma coluna.
export const ECRA_LARGO = "(min-width: 768px)";

export default function useEcraLargo() {
  const [largo, definirLargo] = useState(() => window.matchMedia(ECRA_LARGO).matches);
  useEffect(() => {
    const consulta = window.matchMedia(ECRA_LARGO);
    const aoMudar = (evento) => definirLargo(evento.matches);
    consulta.addEventListener("change", aoMudar);
    return () => consulta.removeEventListener("change", aoMudar);
  }, []);
  return largo;
}
