import { useEffect, useRef, useState } from "react";

import { api, criarIntencao } from "../../api/cliente.js";
import Aviso from "../../componentes/Aviso.jsx";
import Botao from "../../componentes/Botao.jsx";
import Campo from "../../componentes/Campo.jsx";
import CampoConta from "../../componentes/CampoConta.jsx";
import Ecra from "../../componentes/Ecra.jsx";
import { numeroVisivel } from "../../lib/dinheiro.js";
import { guardarContaEscolhida, lerContaEscolhida } from "../../lib/sessao.js";
import useContas from "../../lib/useContas.js";

// RF-04/05, RF-20 (câmbio), CU-06 (entre contas próprias) e RF-25 (outro banco).
const TIPOS = [
  ["propria", "Entre as tuas contas", "Se as moedas forem diferentes, é um câmbio à taxa do dia."],
  ["pessoa", "Para outra pessoa", "Pelo número da conta. Confirmas o titular antes de enviar."],
  ["banco", "Para outro banco", "Sai já da tua conta; se o outro banco recusar, o valor volta."],
];

export default function Transferir() {
  const { contas, recarregar } = useContas();
  const [tipo, definirTipo] = useState("");
  const [de, definirDe] = useState(lerContaEscolhida);
  const [para, definirPara] = useState("");
  const [numero, definirNumero] = useState("");
  const [destinatario, definirDestinatario] = useState(null);
  const [sistemas, definirSistemas] = useState([]);
  const [sistema, definirSistema] = useState("");
  const [valor, definirValor] = useState("");
  const [feita, definirFeita] = useState(null);
  const [erro, definirErro] = useState(null);
  const [aEnviar, definirAEnviar] = useState(false);
  // Repetir com os mesmos dados (depois de uma falha de rede ou de um 503) é a
  // mesma intenção, com o mesmo op_id: o dinheiro nunca sai duas vezes.
  const intencao = useRef(criarIntencao()).current;

  useEffect(() => {
    if (tipo !== "banco" || sistemas.length) return;
    api.sistemasExternos()
      .then(({ sistemas: lista }) => {
        definirSistemas(lista);
        if (lista.length) definirSistema(lista[0].id);
      })
      .catch((falha) => definirErro(falha.message));
  }, [tipo, sistemas.length]);

  const origem = contas.find((conta) => conta.conta === de);

  async function procurar() {
    definirErro(null);
    definirDestinatario(null);
    try {
      definirDestinatario(await api.contaPorNumero(numero));
    } catch (falha) {
      definirErro(falha.message);
    }
  }

  async function enviar(evento) {
    evento.preventDefault();
    definirErro(null);
    definirFeita(null);
    definirAEnviar(true);
    try {
      let resposta;
      if (tipo === "propria") {
        resposta = await api.autotransferir(de, para, valor.trim(), intencao);
      } else if (tipo === "pessoa") {
        // O servidor aceita o número no lugar do id; com moedas diferentes,
        // é um câmbio à taxa em vigor.
        const enviarCom = destinatario.moeda === origem?.moeda ? api.transferir : api.converter;
        resposta = await enviarCom(de, destinatario.numero, valor.trim(), intencao);
      } else {
        resposta = await api.transferirParaFora(de, sistema, valor.trim(), intencao);
      }
      guardarContaEscolhida(de);
      definirFeita({ ...resposta, tipo });
      recarregar();
    } catch (falha) {
      definirErro(falha.message);
    } finally {
      definirAEnviar(false);
    }
  }

  function recomecar() {
    definirTipo("");
    definirErro(null);
    definirFeita(null);
    definirDestinatario(null);
    definirNumero("");
  }

  const pronto = de && valor.trim() && (
    (tipo === "propria" && para) ||
    (tipo === "pessoa" && destinatario) ||
    (tipo === "banco" && sistema));
  const cambio = tipo === "pessoa" && destinatario && origem && destinatario.moeda !== origem.moeda;

  return (
    <Ecra titulo="Transferir" voltar>
      {!tipo && (
        <div className="opcoes">
          <p className="legenda">Para onde vai o dinheiro?</p>
          {TIPOS.map(([id, titulo, texto]) => (
            <button key={id} type="button" className="opcao" onClick={() => definirTipo(id)}>
              <strong>{titulo}</strong>
              <span>{texto}</span>
            </button>
          ))}
        </div>
      )}

      {tipo && !feita && (
        <form className="cartao" onSubmit={enviar}>
          <CampoConta rotulo="De" contas={contas} valor={de} aoMudar={definirDe} />

          {tipo === "propria" && (
            <CampoConta rotulo="Para" contas={contas} valor={para} aoMudar={definirPara} excluir={de} />
          )}

          {tipo === "pessoa" && (
            <>
              <Campo rotulo="Número da conta de destino" ajuda="Por exemplo 0001 / 12345678-9"
                     autoComplete="off" value={numero}
                     onChange={(e) => { definirNumero(e.target.value); definirDestinatario(null); }}
                     onBlur={() => numero.trim() && !destinatario && procurar()} required />
              {destinatario && (
                <div className="confirmacao">
                  <span className="legenda">Titular</span>
                  <strong>{destinatario.titular}</strong>
                  <span className="legenda">{numeroVisivel(destinatario)} · {destinatario.moeda}</span>
                </div>
              )}
              {!destinatario && numero.trim() && (
                <Botao tipo="button" variante="secundario" onClick={procurar}>Procurar titular</Botao>
              )}
              {cambio && (
                <Aviso>
                  A conta de destino é em {destinatario.moeda}: o valor converte-se à taxa em vigor.
                </Aviso>
              )}
            </>
          )}

          {tipo === "banco" && (
            <Campo rotulo="Banco">
              <select value={sistema} onChange={(e) => definirSistema(e.target.value)}>
                {sistemas.map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
              </select>
            </Campo>
          )}

          <Campo rotulo={`Valor${origem ? ` em ${origem.moeda}` : ""}`} inputMode="decimal"
                 placeholder="25.00" value={valor} onChange={(e) => definirValor(e.target.value)} required />
          <Aviso erro>{erro}</Aviso>
          <Botao disabled={aEnviar || !pronto}>{aEnviar ? "A confirmar…" : "Transferir"}</Botao>
          <button className="botao-expandir" type="button" onClick={recomecar}>Outro tipo</button>
        </form>
      )}

      {feita && <Comprovativo feita={feita} contas={contas} aoRecomecar={recomecar} />}
    </Ecra>
  );
}

function Comprovativo({ feita, contas, aoRecomecar }) {
  const nome = (id) => {
    const conta = contas.find((c) => c.conta === id);
    return conta ? numeroVisivel(conta) : id;
  };
  return (
    <section className="cartao resultado" aria-live="polite">
      {feita.tipo === "banco" ? (
        <>
          <p className="rotulo">Para outro banco</p>
          <p className="quantia">{feita.saldo}</p>
          <p className="legenda">saldo de {nome(feita.conta)} depois da operação</p>
          {feita.estado === "confirmada" ? (
            <p className="carimbo">✓ confirmada · ref. {feita.referencia_externa}</p>
          ) : (
            <Aviso erro>O outro banco recusou: o valor voltou à tua conta.</Aviso>
          )}
        </>
      ) : (
        <>
          <p className="rotulo">{feita.taxa ? `Câmbio a ${feita.taxa}` : "Transferência"}</p>
          <p className="quantia">{feita.saldos?.[feita.de]}</p>
          <p className="legenda">saldo de {nome(feita.de)} depois da operação</p>
          {feita.taxa && <p className="legenda">Saíram {feita.valor} e entraram {feita.valor_destino}.</p>}
          {/* O saldo do destino só vem quando a conta também é tua. */}
          {feita.saldos?.[feita.para] && (
            <div className="linhas">
              <div className="linha"><span>{nome(feita.para)}</span><strong>{feita.saldos[feita.para]}</strong></div>
            </div>
          )}
          <p className="carimbo">✓ confirmada pela maioria dos nós</p>
        </>
      )}
      <Botao tipo="button" variante="secundario" onClick={aoRecomecar}>Outra transferência</Botao>
    </section>
  );
}
