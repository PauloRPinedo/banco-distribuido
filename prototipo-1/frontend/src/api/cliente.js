// Fala sempre com `/api`. Quem reescreve esse prefixo depende de onde o
// painel corre — o vite.config.js em desenvolvimento, o nginx.conf em
// contentor — e por isso este ficheiro não conhece endereço nenhum.
const BASE = "/api";

// O op_id é gerado aqui, no cliente, e não no servidor. É isso
// que torna seguro repetir um pedido de que não se sabe o desfecho: se a
// primeira tentativa chegou a ser aplicada, a segunda devolve o resultado
// guardado em vez de mover o dinheiro outra vez.
function opId() {
  return crypto.randomUUID();
}

async function pedir(caminho, { metodo = "GET", corpo } = {}) {
  const resposta = await fetch(`${BASE}${caminho}`, {
    method: metodo,
    headers: { "Content-Type": "application/json" },
    body: corpo ? JSON.stringify(corpo) : undefined,
  });

  const dados = await resposta.json().catch(() => null);
  if (!resposta.ok) {
    // Todos os erros do banco têm a mesma forma, por isso há um só
    // caminho de tratamento.
    throw new Error(dados?.mensagem || "o banco não respondeu");
  }
  return dados;
}

// `valor` e `saldoInicial` são texto, e vão como texto. Nunca se faz
// Number(...) em dinheiro: seria o float que o banco proíbe, reintroduzido
// no último passo.
export const api = {
  // Quem é este nó. Com dois painéis iguais abertos, é o que diz qual é qual.
  saude: () => pedir("/saude"),

  criarConta: (conta, saldoInicial) =>
    pedir("/contas", {
      metodo: "POST",
      corpo: { conta, saldo_inicial: saldoInicial || "0", op_id: opId() },
    }),

  consultarSaldo: (conta) => pedir(`/contas/${conta}`),

  consultarExtrato: (conta) => pedir(`/contas/${conta}/extrato`),

  depositar: (conta, valor) =>
    pedir(`/contas/${conta}/deposito`, {
      metodo: "POST",
      corpo: { valor, op_id: opId() },
    }),

  sacar: (conta, valor) =>
    pedir(`/contas/${conta}/saque`, {
      metodo: "POST",
      corpo: { valor, op_id: opId() },
    }),

  transferir: (de, para, valor) =>
    pedir("/transferencias", {
      metodo: "POST",
      corpo: { de, para, valor, op_id: opId() },
    }),

  auditoria: () => pedir("/auditoria"),
};
