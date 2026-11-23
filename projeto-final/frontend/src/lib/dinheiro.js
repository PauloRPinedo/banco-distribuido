// O dinheiro chega já formatado do servidor (`saldo`, `valor`): o painel não
// divide centavos por 100, que seria pôr um float no meio do dinheiro. Aqui só
// há o que é de apresentação.

// "0001 · 12345678-9". As contas abertas antes de haver números mostram o id.
export function numeroVisivel(conta) {
  if (!conta) return "";
  if (!conta.numero) return conta.conta;
  return `${conta.agencia || "0001"} · ${conta.numero}`;
}

export const PRODUTOS = { corrente: "Corrente", poupanca: "Poupança", prazo_fixo: "Prazo fixo" };

export const OPERACOES = {
  criar_conta: "Abertura",
  deposito: "Depósito",
  saque: "Saque",
  transferencia: "Transferência",
  cambio: "Câmbio",
  juros: "Juros",
  transferencia_externa: "Para outro banco",
  desfecho_externo: "Devolução de outro banco",
};

// "0.100000" -> "10 %". Só para mostrar: a taxa com que se calcula é a do
// servidor, em milionésimos inteiros.
export function percentagem(taxa) {
  const [inteiros, decimais = ""] = String(taxa).split(".");
  const centesimos = `${inteiros}${decimais.padEnd(6, "0")}`.replace(/^0+(?=\d)/, "");
  const parte = centesimos.padStart(5, "0");
  const inteira = parte.slice(0, -4).replace(/^0+(?=\d)/, "");
  const fracao = parte.slice(-4).replace(/0+$/, "");
  return `${inteira}${fracao ? "," + fracao : ""} %`;
}
