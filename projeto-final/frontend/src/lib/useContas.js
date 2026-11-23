import { useCallback, useEffect, useState } from "react";

import { api } from "../api/cliente.js";

// As contas de quem tem a sessão, sempre do servidor (`GET /contas`). Não há
// cópia no navegador: depois de um failover, o que se vê é o que o novo
// primário tem.
export default function useContas() {
  const [contas, definirContas] = useState([]);
  const [aCarregar, definirACarregar] = useState(true);
  const [erro, definirErro] = useState(null);

  const recarregar = useCallback(async () => {
    definirACarregar(true);
    try {
      const { contas: lista } = await api.listarContas();
      definirContas(lista);
      definirErro(null);
    } catch (falha) {
      definirErro(falha.message);
    } finally {
      definirACarregar(false);
    }
  }, []);

  useEffect(() => {
    recarregar();
  }, [recarregar]);

  return { contas, aCarregar, erro, recarregar };
}
