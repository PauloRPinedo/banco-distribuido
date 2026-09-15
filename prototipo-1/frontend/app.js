"use strict";

/* O frontend do banco. Sem framework e sem passo de build, como o resto do
   projeto — o que se publica é exatamente o que está escrito aqui.
 *
 * Três regras que vêm do servidor e não se negoceiam:
 *
 *   1. o dinheiro viaja como TEXTO ("25.00"), nunca como número JSON. Um número
 *      seria descodificado como float do outro lado, e um float em dinheiro é a
 *      origem do desvio que RNF-01 proíbe;
 *   2. toda escrita leva um op_id gerado AQUI. É o que torna a retentativa
 *      segura: repetir devolve o resultado guardado em vez de mover o dinheiro
 *      outra vez (RF-13);
 *   3. nenhuma regra de negócio vive nesta página. Quem valida é o banco.
 */

const CHAVE = "banco.url_base";
const CHAVE_DO_ECRA = "banco.ecra";
const RITMO_MS = 1000;
const ECRAS = ["inicio", "operacoes", "extrato", "cluster"];

let urlBase = "";
let ultimaLeitura = 0;
let totalConhecido = null;
let contasConhecidas = [];

const elemento = (id) => document.getElementById(id);

// ------------------------------------------------------------------ dinheiro

/* Trabalha sobre inteiros de centavos, e não passa por `Intl.NumberFormat`.
   É um desvio deliberado às recomendações de interface: o Intl recebe um número
   em reais, o que obrigaria a dividir por 100 e a meter um float no dinheiro —
   exatamente o que RNF-01 proíbe. A parte inteira é que vai ao `toLocaleString`,
   já como inteiro, só para ganhar os separadores de milhar. */
function emReais(centavos) {
  const sinal = centavos < 0 ? "-" : "";
  const inteiro = Math.trunc(Math.abs(centavos) / 100);
  const resto = String(Math.abs(centavos) % 100).padStart(2, "0");
  return `${sinal}R$ ${inteiro.toLocaleString("pt-BR")},${resto}`;
}

// ------------------------------------------------------------------ endereço

function descobrirUrlBase() {
  const naQuery = new URLSearchParams(location.search).get("api");
  if (naQuery) return naQuery.trim();
  return ler(CHAVE) || window.BANCO_URL_BASE || "";
}

function ler(chave) {
  try {
    return localStorage.getItem(chave) || "";
  } catch (_) {
    // Navegador em modo privado, ou armazenamento bloqueado. Não é um erro: o
    // endereço passa a ter de vir na query ou no campo, e a página funciona.
    return "";
  }
}

function guardar(chave, valor) {
  try {
    if (valor) localStorage.setItem(chave, valor);
    else localStorage.removeItem(chave);
  } catch (_) { /* ver acima */ }
}

function guardarUrlBase(valor) {
  urlBase = valor.trim().replace(/\/+$/, "");
  elemento("url-base").value = urlBase;
  guardar(CHAVE, urlBase);
}

// --------------------------------------------------------------------- rede

class SemEndereco extends Error {}

class RecusaDoBanco extends Error {
  constructor(estado, corpo) {
    super(corpo.mensagem || `o banco respondeu ${estado}`);
    this.estado = estado;
    this.codigo = corpo.erro || "erro_desconhecido";
    this.corpo = corpo;
  }
}

async function pedir(metodo, caminho, corpo) {
  if (!urlBase) throw new SemEndereco();
  const resposta = await fetch(urlBase + caminho, {
    method: metodo,
    headers: corpo ? { "Content-Type": "application/json" } : undefined,
    body: corpo ? JSON.stringify(corpo) : undefined,
  });
  const lido = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new RecusaDoBanco(resposta.status, lido);
  return lido;
}

function opId() {
  // randomUUID exige um contexto seguro; o túnel é HTTPS, mas em http:// local
  // não existe. O reserva é suficiente: só tem de ser único.
  if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
  return `op-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

// ------------------------------------------------------------------- avisos

const PASSOS = {
  saldo_insuficiente: "consulte o saldo da conta antes de repetir",
  conta_inexistente: "crie a conta primeiro, no ecrã «Operações»",
  conta_duplicada: "escolha outro identificador",
  valor_invalido: "escreva o valor com duas casas decimais, como 25.00",
  nao_sou_primario: "aponte o endereço a outro nó do cluster",
  sem_quorum: "veja no ecrã «Cluster» quantos nós estão de pé, e repita",
  somente_leitura: "o cluster não vê a maioria; arranque os nós em falta",
  armazem_indisponivel: "o nó não conseguiu gravar; repita dentro de momentos",
  particao_simulada: "limpe a falha injetada com: banco.cli falha limpar",
};

// Que campo tem culpa de cada recusa. O que não estiver aqui é do cluster, não
// do formulário, e vai para o aviso geral.
const CAMPO_CULPADO = {
  conta_inexistente: "conta",
  conta_duplicada: "conta",
  saldo_insuficiente: "valor",
  valor_invalido: "valor",
};

function mostrarAviso(titulo, detalhe, passo, tipo = "erro") {
  const alvo = elemento("aviso");
  alvo.innerHTML = "";
  const caixa = document.createElement("div");
  caixa.className = `aviso ${tipo}`;
  for (const [classe, texto] of [["titulo", titulo], ["", detalhe], ["passo", passo]]) {
    if (!texto) continue;
    const linha = document.createElement("span");
    linha.className = classe;
    linha.textContent = texto;
    caixa.appendChild(linha);
  }
  alvo.appendChild(caixa);
}

function limparAviso() {
  elemento("aviso").innerHTML = "";
}

function limparErrosDe(formulario) {
  const slot = elemento(`erro-${formulario.dataset.erro}`);
  if (slot) { slot.hidden = true; slot.textContent = ""; }
  for (const campo of formulario.querySelectorAll("input")) {
    campo.removeAttribute("aria-invalid");
  }
}

/* Põe o erro ao lado do campo culpado e leva-lhe o foco. Devolve `true` se
   conseguiu — quem chama decide se ainda precisa do aviso geral. */
function marcarCampo(formulario, erro) {
  const papel = CAMPO_CULPADO[erro.codigo];
  if (!papel) return false;
  const campo = formulario.querySelector(`input[name="${papel}"]`)
             || formulario.querySelector("input[name=de]");
  const slot = elemento(`erro-${formulario.dataset.erro}`);
  if (!campo || !slot) return false;
  slot.textContent = erro.message;
  slot.hidden = false;
  campo.setAttribute("aria-invalid", "true");
  campo.focus();
  return true;
}

function relatar(erro, formulario) {
  if (erro instanceof SemEndereco) {
    abrirPainelDoEndereco(true);
    mostrarAviso("falta o endereço do banco",
                 "cole o endereço do túnel no campo acima",
                 "por exemplo https://xxxx.trycloudflare.com");
    return;
  }
  if (erro instanceof RecusaDoBanco) {
    if (formulario && marcarCampo(formulario, erro)) {
      // Deixar o «transferência confirmada» anterior por baixo de um erro novo
      // daria a ler duas respostas contraditórias ao mesmo tempo.
      limparAviso();
      return;
    }
    // Três linhas: o que aconteceu, com os números concretos, e o passo
    // seguinte. Um erro que não diz o passo seguinte deixa quem o lê onde
    // estava (CODESTYLE 9.4).
    mostrarAviso(erro.codigo.replace(/_/g, " "), erro.message,
                 PASSOS[erro.codigo] || "veja o estado no ecrã «Cluster»");
    return;
  }
  mostrarAviso("não foi possível falar com o banco", String(erro),
               "confirme o endereço e que o túnel está de pé");
}

/* Envolve o envio de um formulário: limpa erros, marca o botão como ocupado e
   garante que ele volta ao normal mesmo quando a operação falha. */
async function enviar(formulario, botao, ocupado, tarefa) {
  limparErrosDe(formulario);
  const original = botao.textContent;
  botao.disabled = true;
  botao.textContent = ocupado;
  try {
    await tarefa();
  } catch (erro) {
    relatar(erro, formulario);
  } finally {
    botao.disabled = false;
    botao.textContent = original;
  }
}

// -------------------------------------------------------------------- ecrãs

function mostrarEcra(nome, focar = false) {
  const escolhido = ECRAS.includes(nome) ? nome : ECRAS[0];
  for (const outro of ECRAS) {
    const aba = elemento(`aba-${outro}`);
    const ecra = elemento(`ecra-${outro}`);
    const ativo = outro === escolhido;
    aba.setAttribute("aria-selected", String(ativo));
    aba.tabIndex = ativo ? 0 : -1;
    ecra.hidden = !ativo;
  }
  if (focar) elemento(`aba-${escolhido}`).focus();
  guardar(CHAVE_DO_ECRA, escolhido);
  if (location.hash.slice(1) !== escolhido) {
    history.replaceState(null, "", `#${escolhido}`);
  }
}

function ecraInicial() {
  const noEndereco = location.hash.slice(1);
  if (ECRAS.includes(noEndereco)) return noEndereco;
  return ler(CHAVE_DO_ECRA) || ECRAS[0];
}

function ligarAbas() {
  const abas = ECRAS.map((nome) => elemento(`aba-${nome}`));
  for (const [posicao, aba] of abas.entries()) {
    aba.addEventListener("click", () => mostrarEcra(aba.dataset.ecra));
    aba.addEventListener("keydown", (evento) => {
      const saltos = { ArrowRight: 1, ArrowLeft: -1 };
      let destino = null;
      if (evento.key in saltos) {
        destino = (posicao + saltos[evento.key] + abas.length) % abas.length;
      } else if (evento.key === "Home") {
        destino = 0;
      } else if (evento.key === "End") {
        destino = abas.length - 1;
      }
      if (destino === null) return;
      evento.preventDefault();
      mostrarEcra(abas[destino].dataset.ecra, true);
    });
  }
  window.addEventListener("hashchange", () => mostrarEcra(location.hash.slice(1)));
}

// ------------------------------------------------------------------ desenho

function desenharTotal(auditoria) {
  const numero = elemento("total");
  numero.classList.remove("esqueleto");
  elemento("cartao-total").classList.remove("sem-contacto");
  numero.textContent = emReais(auditoria.total_centavos);
  totalConhecido = auditoria.total_centavos;
  ultimaLeitura = Date.now();

  elemento("sob-o-total").textContent =
    `${auditoria.contas} contas · ${auditoria.operacoes} operações`;
  elemento("auditoria-saldos").textContent = emReais(auditoria.total_centavos);
  elemento("auditoria-log").textContent =
    emReais(auditoria.total_esperado_centavos);

  const veredito = elemento("auditoria-veredito");
  if (auditoria.divergente) {
    veredito.textContent =
      `diverge em ${emReais(auditoria.divergencia_centavos)}`;
    veredito.className = "erro-do-campo";
    mostrarAviso("a auditoria diverge",
                 "os saldos não batem com o que o log explica",
                 "guarde o estado dos nós antes de mexer em mais nada");
    return;
  }
  veredito.textContent = "os dois cálculos batem";
  veredito.className = "carimbo";
}

function marcarSemContacto() {
  if (totalConhecido === null) return;
  // Nunca se mostra um número velho como se fosse atual: esbate-se e diz-se há
  // quanto tempo é que foi lido.
  elemento("cartao-total").classList.add("sem-contacto");
  const segundos = Math.round((Date.now() - ultimaLeitura) / 1000);
  elemento("sob-o-total").textContent = `última leitura há ${segundos} s`;
}

function desenharContas(contas) {
  const alvo = elemento("lista-contas");
  alvo.innerHTML = "";
  if (!contas.length) {
    alvo.innerHTML = '<p class="rotulo">ainda não há contas conhecidas nesta sessão</p>';
    return;
  }
  for (const conta of contas) {
    const linha = document.createElement("div");
    linha.className = "linha";
    const nome = document.createElement("span");
    nome.textContent = conta.conta;
    const saldo = document.createElement("span");
    saldo.className = "valor";
    saldo.textContent = emReais(conta.saldo_centavos);
    linha.append(nome, saldo);
    alvo.appendChild(linha);
  }
}

/* O motivo vem do `urllib` e chega em inglês, com número de erro e tudo. Serve
   para depurar, não para se ler num ecrã projetado. */
const MOTIVOS = [
  [/refused/i, "o processo não está a responder"],
  [/timed? ?out/i, "não respondeu a tempo"],
  [/isolado/i, "isolado por uma falha injetada"],
  [/terminar/i, "este nó está a fechar"],
  [/unreachable|not known|resolve/i, "endereço inalcançável"],
];

function emPortugues(motivo) {
  if (!motivo) return "sem contacto";
  for (const [padrao, texto] of MOTIVOS) {
    if (padrao.test(motivo)) return texto;
  }
  return "sem contacto";
}

function desenharNos(vista) {
  const alvo = elemento("nos");
  alvo.innerHTML = "";
  const nos = vista.nos || [];
  const vivos = nos.filter((no) => no.vivo);
  const aFrente = Math.max(0, ...vivos.map((no) => no.ultimo_indice || 0));

  elemento("fonte-do-cluster").textContent = nos.length
    ? `${vivos.length} de ${nos.length} nós respondem · maioria de ${vista.maioria}`
      + ` · segundo o nó ${vista.eu}`
    : "sem contacto com o banco";

  for (const no of nos) {
    const atraso = no.vivo ? aFrente - (no.ultimo_indice || 0) : 0;
    const cartao = document.createElement("div");
    cartao.className = "cartao";
    if (!no.vivo) cartao.classList.add("fora");
    else if (atraso > 0) cartao.classList.add("atrasado");

    const topo = document.createElement("div");
    topo.className = "linha";
    const nome = document.createElement("span");
    nome.style.fontWeight = "600";
    nome.textContent = `nó ${no.no}`;
    const endereco = document.createElement("span");
    endereco.className = "rotulo";
    endereco.textContent = no.endereco || "";
    topo.append(nome, endereco);

    const papel = document.createElement("span");
    papel.className = "valor";
    // "2 entradas atrás" diz o tamanho do problema; uma luz amarela só diz que
    // existe um.
    papel.textContent = !no.vivo ? "sem contacto"
      : atraso > 0 ? `${no.papel} · ${atraso} atrás` : no.papel;
    cartao.append(topo, papel);

    const detalhe = document.createElement("span");
    detalhe.className = "rotulo";
    if (no.vivo) {
      detalhe.textContent = `epoch ${no.epoch}`;
    } else {
      detalhe.textContent = emPortugues(no.motivo);
      // O texto cru do erro fica no title: é o que serve para depurar, mas não
      // é o que alguém quer ler num cartão durante uma demonstração.
      if (no.motivo) detalhe.title = no.motivo;
    }
    cartao.appendChild(detalhe);

    if (no.vivo) {
      const par = document.createElement("div");
      par.className = "par";
      for (const [rotulo, valor] of [["índice", no.ultimo_indice],
                                     ["commit", no.indice_commit],
                                     ["contas", no.contas]]) {
        const caixa = document.createElement("div");
        const etiqueta = document.createElement("span");
        etiqueta.className = "rotulo";
        etiqueta.textContent = rotulo;
        const numero = document.createElement("span");
        numero.textContent = valor;
        caixa.append(etiqueta, numero);
        par.appendChild(caixa);
      }
      cartao.appendChild(par);
    }
    alvo.appendChild(cartao);
  }
}

// Os tipos vêm do domínio sem acentos, porque são identificadores. No ecrã
// escrevem-se como se escreve em português.
const NOMES_DE_OPERACAO = {
  criar_conta: "criar conta",
  deposito: "depósito",
  saque: "saque",
  transferencia: "transferência",
  noop: "mudança de mandato",
};

function desenharExtrato(resposta) {
  const alvo = elemento("extrato");
  if (!resposta.movimentos.length) {
    alvo.textContent = "";
    const vazio = document.createElement("p");
    vazio.className = "rotulo";
    vazio.textContent = `${resposta.conta} não tem movimentos`;
    alvo.appendChild(vazio);
    return;
  }
  const linhas = resposta.movimentos.map((m) => `
    <tr>
      <td class="direita indice">${m.indice}</td>
      <td>${NOMES_DE_OPERACAO[m.tipo] || m.tipo.replace(/_/g, " ")}</td>
      <td>${m.contraparte || "—"}</td>
      <td class="direita">${emReais(m.valor_centavos)}</td>
      <td class="direita">${emReais(m.saldo_depois_centavos)}</td>
    </tr>`).join("");
  alvo.innerHTML = `<table>
      <caption class="rotulo">movimentos de ${resposta.conta}</caption>
      <thead><tr><th class="direita indice">#</th><th>operação</th><th>contraparte</th>
        <th class="direita">valor</th><th class="direita">saldo</th></tr></thead>
      <tbody>${linhas}</tbody>
    </table>`;
}

// ---------------------------------------------------------------- atualizar

async function atualizar() {
  if (!urlBase) return;
  try {
    const [auditoria, vista] = await Promise.all([
      pedir("GET", "/auditoria"),
      pedir("GET", "/interno/cluster"),
    ]);
    desenharTotal(auditoria);
    desenharNos(vista);

    const eu = vista.nos.find((no) => no.no === vista.eu) || {};
    elemento("ponto").classList.remove("parado");
    elemento("resumo-cluster").textContent =
      `nó ${vista.eu} · ${eu.papel || "?"} · epoch ${eu.epoch ?? "?"}`;
    await recarregarContas();
  } catch (erro) {
    elemento("ponto").classList.add("parado");
    elemento("resumo-cluster").textContent = "sem contacto";
    marcarSemContacto();
    if (!(erro instanceof SemEndereco)) desenharNos({ nos: [] });
  }
}

async function recarregarContas() {
  const saldos = [];
  const continuam = [];
  for (const id of contasConhecidas) {
    try {
      saldos.push(await pedir("GET", `/contas/${encodeURIComponent(id)}`));
      continuam.push(id);
    } catch (erro) {
      // Uma conta que o banco já não conhece sai da lista. Mantê-la faria a
      // página pedi-la outra vez a cada segundo, para sempre, e encher a
      // consola de 404 que ninguém pode resolver. Um erro de rede não conta:
      // aí a conta existe, o que falhou foi a ligação.
      if (erro instanceof RecusaDoBanco && erro.estado === 404) continue;
      continuam.push(id);
    }
  }
  contasConhecidas = continuam;
  desenharContas(saldos);
}

function lembrarConta(id) {
  if (id && !contasConhecidas.includes(id)) contasConhecidas.push(id);
}

// ------------------------------------------------------------------ ligações

function abrirPainelDoEndereco(abrir) {
  elemento("painel-endereco").hidden = !abrir;
  elemento("botao-endereco").setAttribute("aria-expanded", String(abrir));
  if (abrir) elemento("url-base").focus();
}

function ligarFormularios() {
  elemento("botao-endereco").addEventListener("click", () => {
    abrirPainelDoEndereco(elemento("painel-endereco").hidden);
  });

  elemento("form-endereco").dataset.erro = "endereco";
  elemento("form-endereco").addEventListener("submit", (evento) => {
    evento.preventDefault();
    guardarUrlBase(elemento("url-base").value);
    limparAviso();
    abrirPainelDoEndereco(false);
    atualizar();
  });

  elemento("botao-esquecer").addEventListener("click", () => {
    guardarUrlBase("");
    elemento("resumo-cluster").textContent = "sem endereço";
  });

  const conta = elemento("form-conta");
  conta.dataset.erro = "conta";
  conta.addEventListener("submit", (evento) => {
    evento.preventDefault();
    const botao = conta.querySelector("button[type=submit]");
    enviar(conta, botao, "A criar…", async () => {
      const resposta = await pedir("POST", "/contas", {
        conta: elemento("conta-id").value.trim(),
        saldo_inicial: elemento("conta-saldo").value.trim(),
        op_id: opId(),
      });
      lembrarConta(resposta.conta);
      mostrarAviso("conta criada",
                   `${resposta.conta} começa com ${emReais(resposta.saldo_centavos)}`,
                   "", "bom");
      elemento("conta-id").value = "";
      atualizar();
    });
  });

  const movimento = elemento("form-movimento");
  movimento.dataset.erro = "movimento";
  const movimentar = (tipo, botao) => enviar(
    movimento, botao, tipo === "deposito" ? "A depositar…" : "A sacar…",
    async () => {
      const id = elemento("mov-conta").value.trim();
      const resposta = await pedir(
        "POST", `/contas/${encodeURIComponent(id)}/${tipo}`,
        { valor: elemento("mov-valor").value.trim(), op_id: opId() });
      lembrarConta(resposta.conta);
      mostrarAviso(tipo === "deposito" ? "depositado" : "sacado",
                   `${resposta.conta} fica com ${emReais(resposta.saldo_centavos)}`,
                   "", "bom");
      atualizar();
    });

  movimento.addEventListener("submit", (evento) => {
    evento.preventDefault();
    movimentar("deposito", movimento.querySelector("button[type=submit]"));
  });
  elemento("botao-sacar").addEventListener("click", (evento) => {
    movimentar("saque", evento.currentTarget);
  });

  const transferencia = elemento("form-transferencia");
  transferencia.dataset.erro = "transferencia";
  transferencia.addEventListener("submit", (evento) => {
    evento.preventDefault();
    const botao = transferencia.querySelector("button[type=submit]");
    enviar(transferencia, botao, "A transferir…", async () => {
      const de = elemento("tr-de").value.trim();
      const para = elemento("tr-para").value.trim();
      const resposta = await pedir("POST", "/transferencias", {
        de, para, valor: elemento("tr-valor").value.trim(), op_id: opId(),
      });
      lembrarConta(de);
      lembrarConta(para);
      mostrarAviso("transferência confirmada",
                   `${de} fica com ${emReais(resposta.saldos_centavos[de])} · `
                   + `${para} fica com ${emReais(resposta.saldos_centavos[para])}`,
                   "confirmada depois de gravada na maioria dos nós", "bom");
      atualizar();
    });
  });

  const extrato = elemento("form-extrato");
  extrato.dataset.erro = "extrato";
  extrato.addEventListener("submit", (evento) => {
    evento.preventDefault();
    const botao = extrato.querySelector("button[type=submit]");
    enviar(extrato, botao, "A carregar…", async () => {
      const id = elemento("ex-conta").value.trim();
      const resposta = await pedir(
        "GET", `/contas/${encodeURIComponent(id)}/extrato`);
      lembrarConta(id);
      desenharExtrato(resposta);
      limparAviso();
    });
  });
}

// ------------------------------------------------------------------ arranque

guardarUrlBase(descobrirUrlBase());
ligarAbas();
mostrarEcra(ecraInicial());
ligarFormularios();
atualizar();
setInterval(atualizar, RITMO_MS);
