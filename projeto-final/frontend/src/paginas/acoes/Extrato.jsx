import { useEffect, useState } from "react";

import { api } from "../../api/cliente.js";
import Aviso from "../../componentes/Aviso.jsx";
import CampoConta from "../../componentes/CampoConta.jsx";
import Ecra from "../../componentes/Ecra.jsx";
import { OPERACOES } from "../../lib/dinheiro.js";
import { guardarContaEscolhida, lerContaEscolhida } from "../../lib/sessao.js";
import useContas from "../../lib/useContas.js";

const VISIVEIS_DE_INICIO = 8;

// F-05. O mais recente primeiro. O "#" é o índice no log replicado: a mesma
// ordem nos três nós.
export default function Extrato() {
  const { contas } = useContas();
  const [conta, definirConta] = useState(lerContaEscolhida);
  const [movimentos, definirMovimentos] = useState(null);
  const [todos, definirTodos] = useState(false);
  const [erro, definirErro] = useState(null);

  useEffect(() => {
    if (!conta) return;
    guardarContaEscolhida(conta);
    definirErro(null);
    definirTodos(false);
    api.consultarExtrato(conta)
      .then(({ movimentos: lista }) => definirMovimentos([...lista].reverse()))
      .catch((falha) => {
        definirMovimentos(null);
        definirErro(falha.message);
      });
  }, [conta]);

  const mostrados = movimentos && (todos ? movimentos : movimentos.slice(0, VISIVEIS_DE_INICIO));

  return (
    <Ecra titulo="Extrato" voltar largura="media">
      <div className="cartao">
        <CampoConta contas={contas} valor={conta} aoMudar={definirConta} />
      </div>
      <Aviso erro>{erro}</Aviso>
      {mostrados && (
        <div className="lista" aria-live="polite">
          {mostrados.length === 0 && <p className="legenda">Esta conta ainda não tem movimentos.</p>}
          {mostrados.map((movimento) => (
            <div className="item-da-lista" key={movimento.indice}>
              <span className="info">
                <span className="titulo">{OPERACOES[movimento.tipo] || movimento.tipo}</span>
                <span className="legenda">
                  #{movimento.indice} · {new Date(movimento.instante * 1000).toLocaleString("pt-PT")}
                  {movimento.contraparte ? ` · ${movimento.contraparte}` : ""}
                </span>
              </span>
              <span className="valores">
                <span className={movimento.valor_centavos < 0 ? "valor negativo" : "valor positivo"}>
                  {movimento.valor}
                </span>
                <span className="legenda">saldo {movimento.saldo_depois}</span>
              </span>
            </div>
          ))}
          {movimentos.length > VISIVEIS_DE_INICIO && (
            <button className="botao-expandir" type="button" onClick={() => definirTodos((v) => !v)}>
              {todos ? "Ver menos" : `Ver os ${movimentos.length} movimentos`}
            </button>
          )}
        </div>
      )}
    </Ecra>
  );
}
