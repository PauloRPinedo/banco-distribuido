import { useEffect, useState } from "react";

import { api } from "../../api/cliente.js";
import Aviso from "../../componentes/Aviso.jsx";
import Ecra from "../../componentes/Ecra.jsx";

// Os três nós vistos pelo primário, uma vez por segundo. É o ecrã da
// demonstração: mata-se o primário e vê-se outro assumir com um epoch maior,
// e o morto voltar como réplica e pôr-se em dia.
export default function Cluster() {
  const [cluster, definirCluster] = useState(null);
  const [erro, definirErro] = useState(null);

  useEffect(() => {
    let ativo = true;
    async function ler() {
      try {
        const dados = await api.cluster();
        if (ativo) {
          definirCluster(dados);
          definirErro(null);
        }
      } catch (falha) {
        if (ativo) definirErro(falha.message);
      }
    }
    ler();
    const relogio = setInterval(ler, 1000);
    return () => {
      ativo = false;
      clearInterval(relogio);
    };
  }, []);

  const nos = cluster?.nos ?? [];
  const vivos = nos.filter((no) => no.vivo).length;
  const maioria = cluster?.maioria ?? 2;

  return (
    <Ecra titulo="Estado do cluster" voltar largura="larga">
      <section className="cartao resultado" aria-live="polite">
        <p className="rotulo">Visto pelo nó {cluster?.eu ?? "…"}</p>
        <p className="quantia">{vivos} de {nos.length || 3} nós de pé</p>
        {erro
          ? <Aviso erro>{erro}</Aviso>
          : vivos >= maioria
            ? <p className="selo selo-sucesso">✓ há maioria ({maioria}): o banco escreve</p>
            : <p className="selo selo-erro">sem maioria: só leituras</p>}
      </section>

      <div className="grelha grelha-de-nos">
      {nos.map((no) => {
        const papel = !no.vivo ? "em-baixo" : no.papel === "primário" ? "primario" : "replica";
        return (
          <section key={no.no} className={`cartao no-do-cluster ${papel}`}>
            <div className="titulo-com-acao">
              <h2>Nó {no.no}</h2>
              <span className={`insignia ${papel}`}>
                <span className="ponto-de-estado" />
                {no.vivo ? no.papel : "em baixo"}
              </span>
            </div>
            <p className="legenda">{no.endereco}</p>
            {no.vivo ? (
              <div className="linhas">
                <div className="linha"><span>Epoch</span><strong>{no.epoch}</strong></div>
                <div className="linha"><span>Líder conhecido</span><strong>{no.lider ?? "—"}</strong></div>
                <div className="linha"><span>Último índice</span><strong>{no.ultimo_indice}</strong></div>
                <div className="linha"><span>Confirmado até</span><strong>{no.indice_commit}</strong></div>
                <div className="linha"><span>Aplicado até</span><strong>{no.ultimo_aplicado}</strong></div>
              </div>
            ) : (
              <p className="legenda">{no.motivo}</p>
            )}
          </section>
        );
      })}
      </div>

      <section className="cartao">
        <h2>Experimentar</h2>
        <p className="legenda">
          Numa consola, na pasta <code>projeto-final</code>: <code>docker compose kill no-a</code>
          {" "}(ou o nó que for primário). Em menos de dois segundos outro nó passa a
          primário com um epoch maior, e o banco continua a escrever.{" "}
          <code>docker compose start no-a</code> trá-lo de volta como réplica, e o seu
          «aplicado até» alcança o dos outros.
        </p>
      </section>
    </Ecra>
  );
}
