import { useEffect, useRef, useState } from "react";

import { api, criarIntencao } from "../api/cliente.js";

// RF-04/05 (mesma moeda), RF-20 (câmbio) e RF-25 (para outro banco).
//
// O ecrã mostra a direção do dinheiro em vez de a deixar implícita em dois
// campos de texto empilhados, e o sucesso ganha carimbo.
const MODOS = [
  { id: "transferencia", titulo: "Mesma moeda" },
  { id: "cambio", titulo: "Câmbio" },
  { id: "externa", titulo: "Outro banco" },
];

export default function Transferir() {
  const [modo, definirModo] = useState("transferencia");
  const [de, definirDe] = useState("");
  const [para, definirPara] = useState("");
  const [sistema, definirSistema] = useState("");
  const [sistemas, definirSistemas] = useState([]);
  const [valor, definirValor] = useState("");
  const [feita, definirFeita] = useState(null);
  const [erro, definirErro] = useState(null);
  const [aEnviar, definirAEnviar] = useState(false);

  // Uma transferência que falhou por rede e se repete com os mesmos dados é
  // a mesma intenção, com o mesmo op_id: nunca move o dinheiro duas vezes.
  const intencao = useRef(criarIntencao()).current;

  useEffect(() => {
    api.sistemasExternos()
      .then(({ sistemas: lista }) => {
        definirSistemas(lista);
        if (lista.length) definirSistema(lista[0].id);
      })
      .catch(() => definirSistemas([]));
  }, []);

  async function enviar(evento) {
    evento.preventDefault();
    definirErro(null);
    definirAEnviar(true);
    try {
      const resultado =
        modo === "externa" ? await api.transferirParaFora(de, sistema, valor, intencao)
        : modo === "cambio" ? await api.converter(de, para, valor, intencao)
        : await api.transferir(de, para, valor, intencao);
      definirFeita({ ...resultado, modo });
    } catch (falha) {
      definirErro(falha.message);
      definirFeita(null);
    } finally {
      definirAEnviar(false);
    }
  }

  const externa = modo === "externa";
  const completo = de && valor && (externa ? sistema : para);

  return (
    <div className="livro-e-raio">
      <section className="cartao surge" aria-live="polite">
        {!feita ? (
          <div className="vazio">
            <p className="titulo">Nenhuma transferência feita</p>
            <p>
              Escolhe o tipo, a origem, o destino e o valor no raio ao lado. O
              comprovativo aparece aqui.
            </p>
          </div>
        ) : feita.modo === "externa" ? (
          <>
            <p className="rotulo-de-seccao">para outro banco</p>
            <p className="quantia-grande">{feita.saldo}</p>
            <p className="legenda">saldo de {feita.conta} depois da operação</p>
            {feita.estado === "confirmada" ? (
              <p className="carimbo">✓ confirmada · ref. {feita.referencia_externa}</p>
            ) : (
              <p className="aviso fora-do-ar">rejeitada pelo outro banco — o valor voltou à conta</p>
            )}
            <p className="legenda" style={{ marginTop: "16px" }}>
              O débito e a resposta do outro banco são duas operações, cada uma
              com o seu op_id. Repetir este pedido não volta a perguntar.
            </p>
          </>
        ) : (
          <>
            <p className="rotulo-de-seccao">
              {feita.modo === "cambio" ? `câmbio a ${feita.taxa}` : "transferência"}
            </p>
            <p className="quantia-grande">{feita.saldos[feita.de]}</p>
            <p className="legenda">saldo de {feita.de} depois da operação</p>
            <p className="carimbo">✓ confirmada</p>

            <div className="rolavel" style={{ marginTop: "40px" }}>
              <table className="razao">
                <caption>as duas contas, depois</caption>
                <thead>
                  <tr>
                    <th scope="col">conta</th>
                    <th scope="col">papel</th>
                    <th scope="col" className="direita">saldo</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>{feita.de}</td>
                    <td><span className="tipo-de-operacao">origem</span></td>
                    <td className="direita">{feita.saldos[feita.de]}</td>
                  </tr>
                  <tr>
                    <td>{feita.para}</td>
                    <td><span className="tipo-de-operacao">destino</span></td>
                    <td className="direita">{feita.saldos[feita.para]}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <p className="legenda" style={{ marginTop: "16px" }}>
              {feita.modo === "cambio"
                ? `Saíram ${feita.valor} e entraram ${feita.valor_destino}. A taxa ficou gravada com a operação.`
                : "As duas mudaram na mesma transação. Não houve instante nenhum em que o dinheiro tivesse saído de uma e ainda não tivesse entrado na outra."}
            </p>
          </>
        )}
      </section>

      <div className="raio">
        <form className="cartao surge" onSubmit={enviar}>
          <h2>Transferir</h2>

          <div className="pastilhas" style={{ marginTop: "16px" }}>
            {MODOS.map(({ id, titulo }) => (
              <button key={id} type="button"
                      className={id === modo ? "pastilha escolhida" : "pastilha"}
                      onClick={() => { definirModo(id); definirErro(null); }}>
                {titulo}
              </button>
            ))}
          </div>

          <div className="percurso">
            <label className="campo" style={{ marginBottom: 0 }}>
              <span>De — uma conta tua</span>
              <input value={de} onChange={(e) => definirDe(e.target.value)}
                     placeholder="alice" autoComplete="off" spellCheck="false"
                     required />
            </label>
            <span className="seta" aria-hidden="true">→</span>
            {externa ? (
              <label className="campo" style={{ marginBottom: 0 }}>
                <span>Banco</span>
                <select value={sistema} onChange={(e) => definirSistema(e.target.value)}>
                  {sistemas.map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
                </select>
              </label>
            ) : (
              <label className="campo" style={{ marginBottom: 0 }}>
                <span>Para</span>
                <input value={para} onChange={(e) => definirPara(e.target.value)}
                       placeholder="bob" autoComplete="off" spellCheck="false"
                       required />
              </label>
            )}
          </div>

          <label className={erro ? "campo heroi tem-erro" : "campo heroi"}
                 style={{ marginTop: "24px" }}>
            <span>Valor{modo === "cambio" ? " — na moeda da origem" : ""}</span>
            <input value={valor} onChange={(e) => definirValor(e.target.value)}
                   placeholder="25.00" inputMode="decimal" required />
          </label>

          {erro && <p className="erro-do-campo" role="alert">{erro}</p>}

          <div className="botoes" style={{ marginTop: "16px" }}>
            <button type="submit" className="principal"
                    disabled={!completo || aEnviar}>
              {aEnviar ? "A confirmar…" : "Transferir"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
