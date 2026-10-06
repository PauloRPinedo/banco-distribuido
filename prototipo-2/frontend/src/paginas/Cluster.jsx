import { useEffect, useState } from "react";

import { api } from "../api/cliente.js";

// Os três nós, vistos pelo primário, uma vez por segundo. É o ecrã da
// demonstração: mata-se o primário (`docker compose kill no-x`) e vê-se outro
// assumir com um epoch maior, e o morto voltar como réplica e pôr-se em dia.
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

  return (
    <div className="pilha">
      <section className="cartao surge">
        <p className="rotulo-de-seccao">cluster · visto pelo nó {cluster?.eu ?? "…"}</p>
        <p className="quantia-media">
          {vivos} de {nos.length || 3} nós de pé · maioria {cluster?.maioria ?? 2}
        </p>
        {erro ? (
          <p className="aviso fora-do-ar" role="alert">{erro}</p>
        ) : vivos >= (cluster?.maioria ?? 2) ? (
          <p className="carimbo">✓ há maioria: o banco escreve</p>
        ) : (
          <p className="aviso fora-do-ar">sem maioria: só leituras</p>
        )}
      </section>

      <div className="grade-de-nos">
        {nos.map((no) => (
          <section key={no.no}
                   className={`cartao surge no-do-cluster ${no.vivo ? "" : "em-baixo"} ${no.papel === "primário" ? "e-primario" : ""}`}>
            <p className="rotulo-de-seccao">nó {no.no} · {no.endereco}</p>
            <p className="quantia-grande">{no.vivo ? no.papel : "em baixo"}</p>
            {no.vivo ? (
              <table className="razao">
                <tbody>
                  <tr><td>epoch</td><td className="direita">{no.epoch}</td></tr>
                  <tr><td>líder conhecido</td><td className="direita">{no.lider ?? "—"}</td></tr>
                  <tr><td>último índice</td><td className="direita">{no.ultimo_indice}</td></tr>
                  <tr><td>confirmado até</td><td className="direita">{no.indice_commit}</td></tr>
                  <tr><td>aplicado até</td><td className="direita">{no.ultimo_aplicado}</td></tr>
                </tbody>
              </table>
            ) : (
              <p className="legenda">{no.motivo}</p>
            )}
          </section>
        ))}
      </div>

      <section className="cartao surge">
        <h2>Experimentar</h2>
        <p className="legenda">
          Numa consola, na pasta <code>prototipo-2</code>: <code>docker compose kill
          no-a</code> (ou o nó que for primário). Em menos de dois segundos outro
          nó passa a primário com um epoch maior, e o banco continua a escrever.
          <code> docker compose start no-a</code> trá-lo de volta como réplica, e o
          seu "aplicado até" alcança o dos outros.
        </p>
      </section>
    </div>
  );
}
