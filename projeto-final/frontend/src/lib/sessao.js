// O que o painel guarda no navegador. Nada disto é fonte de verdade: o token
// valida-o o servidor, e os saldos leem-se sempre do banco. Tudo dentro de
// try/catch, porque numa janela privada o armazenamento pode não existir.
const TOKEN = "banco.token";
const CONTA_ESCOLHIDA = "banco.conta-escolhida";
const SALDOS_VISIVEIS = "banco.saldos-visiveis";
const PRINCIPAL = "banco.conta-principal";

function ler(armazem, chave) {
  try {
    return armazem.getItem(chave);
  } catch {
    return null;
  }
}

function escrever(armazem, chave, valor) {
  try {
    if (valor == null) armazem.removeItem(chave);
    else armazem.setItem(chave, valor);
  } catch {
    // Sem armazenamento, a preferência dura só esta página.
  }
}

export const lerToken = () => ler(localStorage, TOKEN);

export function guardarToken(token) {
  escrever(localStorage, TOKEN, token);
}

// O utilizador do token, só para separar preferências entre pessoas que usam
// o mesmo navegador. O servidor nunca confia nisto: valida a assinatura.
export function usuarioDoToken() {
  const token = lerToken();
  if (!token) return null;
  try {
    const corpo = token.split(".")[0].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(corpo)).usuario_id ?? null;
  } catch {
    return null;
  }
}

export function terminarSessao() {
  const usuario = usuarioDoToken();
  escrever(localStorage, TOKEN, null);
  if (usuario) escrever(localStorage, `${PRINCIPAL}:${usuario}`, null);
  escrever(sessionStorage, CONTA_ESCOLHIDA, null);
  // O App ouve isto e volta ao ecrã de entrada.
  window.dispatchEvent(new Event("banco:sessao-terminada"));
}

// A conta com que se está a trabalhar, para não a escolher em cada ecrã.
export const lerContaEscolhida = () => ler(sessionStorage, CONTA_ESCOLHIDA) || "";

export function guardarContaEscolhida(conta) {
  if (conta) escrever(sessionStorage, CONTA_ESCOLHIDA, conta);
}

export function lerPrincipal() {
  const usuario = usuarioDoToken();
  return usuario ? ler(localStorage, `${PRINCIPAL}:${usuario}`) || "" : "";
}

export function guardarPrincipal(conta) {
  const usuario = usuarioDoToken();
  if (usuario && conta) escrever(localStorage, `${PRINCIPAL}:${usuario}`, conta);
}

export const lerSaldosVisiveis = () => ler(localStorage, SALDOS_VISIVEIS) !== "0";

export function guardarSaldosVisiveis(visiveis) {
  escrever(localStorage, SALDOS_VISIVEIS, visiveis ? "1" : "0");
}
