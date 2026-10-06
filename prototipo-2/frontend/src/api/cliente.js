// Fala sempre com `/api`. Quem reescreve esse prefixo depende de onde o
// painel corre — o vite.config.js em desenvolvimento, o nginx.conf em
// contentor, o vercel.json na nuvem — e por isso este ficheiro não conhece
// endereço nenhum. Do outro lado de `/api` está sempre o balanceador.
const BASE = "/api";
const CHAVE_DO_TOKEN = "banco.token";

export const sessao = {
  token: () => {
    try {
      return localStorage.getItem(CHAVE_DO_TOKEN);
    } catch {
      return null;
    }
  },
  guardar: (token) => {
    try {
      localStorage.setItem(CHAVE_DO_TOKEN, token);
    } catch {
      // Sem armazenamento a sessão dura só esta página; não é razão para falhar.
    }
  },
  terminar: () => {
    try {
      localStorage.removeItem(CHAVE_DO_TOKEN);
    } catch {
      // idem
    }
    // O App ouve isto e volta ao ecrã de login.
    window.dispatchEvent(new Event("banco:sessao-terminada"));
  },
};

export class ErroDoBanco extends Error {
  constructor(mensagem, estado, codigo) {
    super(mensagem);
    this.estado = estado;
    this.codigo = codigo;
  }
}

async function pedir(caminho, { metodo = "GET", corpo } = {}) {
  const cabecalhos = { "Content-Type": "application/json" };
  const token = sessao.token();
  if (token) cabecalhos.Authorization = `Bearer ${token}`;

  const resposta = await fetch(`${BASE}${caminho}`, {
    method: metodo,
    headers: cabecalhos,
    body: corpo ? JSON.stringify(corpo) : undefined,
  });

  const dados = await resposta.json().catch(() => null);
  if (!resposta.ok) {
    if (resposta.status === 401 && token) sessao.terminar();
    // Todos os erros do banco têm a mesma forma, por isso há um só caminho
    // de tratamento.
    throw new ErroDoBanco(dados?.mensagem || "o banco não respondeu",
                          resposta.status, dados?.erro);
  }
  return dados;
}

// Uma intenção do utilizador é um op_id. Carregar duas vezes em "Transferir"
// com os mesmos dados, depois de uma falha de rede ou de um 503 sem maioria,
// reutiliza o op_id da primeira tentativa: se ela chegou a ser aplicada, o
// banco devolve o resultado guardado em vez de mover o dinheiro outra vez.
//
// A intenção só se fecha quando há uma resposta definitiva — sucesso ou uma
// recusa do banco (4xx). Mudar os dados é outra intenção, com op_id novo.
export function criarIntencao() {
  let chave = null;
  let opId = null;
  return {
    para(dados) {
      const nova = JSON.stringify(dados);
      if (nova !== chave) {
        chave = nova;
        opId = crypto.randomUUID();
      }
      return opId;
    },
    concluir() {
      chave = null;
      opId = null;
    },
  };
}

async function escrever(caminho, corpo, intencao) {
  const op_id = intencao.para({ caminho, ...corpo });
  try {
    const resultado = await pedir(caminho, { metodo: "POST", corpo: { ...corpo, op_id } });
    intencao.concluir();
    return resultado;
  } catch (falha) {
    if (falha instanceof ErroDoBanco && falha.estado < 500) intencao.concluir();
    throw falha;
  }
}

// `valor` e `saldoInicial` são texto, e vão como texto. Nunca se faz
// Number(...) em dinheiro: seria o float que o banco proíbe, reintroduzido
// no último passo.
export const api = {
  // Que nó respondeu, e com que papel. `/saude` não serve: através do
  // balanceador, quem responde a `/saude` é o próprio balanceador.
  estadoDoNo: () => pedir("/interno/estado"),

  // Os três nós, vistos pelo primário (que pergunta aos outros dois).
  cluster: () => pedir("/interno/cluster"),

  registar: (nome, email, senha) =>
    pedir("/auth/registo", { metodo: "POST", corpo: { nome, email, senha } }),

  entrar: async (email, senha) => {
    const { token } = await pedir("/auth/login", {
      metodo: "POST", corpo: { email, senha },
    });
    sessao.guardar(token);
  },

  listarContas: () => pedir("/contas"),

  // `produto` traz moeda, produto, taxa_juros (texto, "0.10" é 10 %) e
  // prazo_dias; os campos vazios não vão.
  criarConta: (conta, saldoInicial, produto, intencao) =>
    escrever("/contas", {
      conta, saldo_inicial: saldoInicial || "0",
      ...Object.fromEntries(Object.entries(produto).filter(([, v]) => v !== "" && v != null)),
    }, intencao),

  consultarSaldo: (conta) => pedir(`/contas/${conta}`),

  consultarExtrato: (conta) => pedir(`/contas/${conta}/extrato`),

  depositar: (conta, valor, intencao) =>
    escrever(`/contas/${conta}/deposito`, { valor }, intencao),

  sacar: (conta, valor, intencao) =>
    escrever(`/contas/${conta}/saque`, { valor }, intencao),

  transferir: (de, para, valor, intencao) =>
    escrever("/transferencias", { de, para, valor }, intencao),

  converter: (de, para, valor, intencao) =>
    escrever("/transferencias/conversao", { de, para, valor }, intencao),

  transferirParaFora: (de, sistemaExternoId, valor, intencao) =>
    escrever("/transferencias/externa",
             { de, sistema_externo_id: sistemaExternoId, valor }, intencao),

  sistemasExternos: () => pedir("/sistemas-externos"),

  creditarJuros: () => pedir("/admin/juros", { metodo: "POST" }),

  auditoria: () => pedir("/auditoria"),
};
