// As contas que já se abriu ou consultou **neste navegador**.
//
// É uma conveniência, e não uma fonte de verdade: SPECS 6.1 não tem rota para
// listar contas, e inventar uma aqui seria pôr a interface a decidir o que a
// especificação não decidiu. Serve só para não ter de escrever "alice" de
// memória a meio de uma demonstração.
//
// Mora no navegador de quem está a olhar. Outro portátil não a vê, e é isso
// mesmo que se quer dizer quando o ecrã lhe chama "neste navegador".

const CHAVE = "banco.contas-vistas";
const QUANTAS = 8;

export function lerContasVistas() {
  try {
    const guardado = JSON.parse(localStorage.getItem(CHAVE) || "[]");
    return Array.isArray(guardado) ? guardado.slice(0, QUANTAS) : [];
  } catch {
    // Navegação privada, armazenamento cheio, JSON estragado à mão. Nenhum
    // deles é razão para o painel deixar de funcionar.
    return [];
  }
}

export function guardarContaVista(conta) {
  if (!conta) return lerContasVistas();
  const semEsta = lerContasVistas().filter((outra) => outra !== conta);
  const atualizada = [conta, ...semEsta].slice(0, QUANTAS);
  try {
    localStorage.setItem(CHAVE, JSON.stringify(atualizada));
  } catch {
    // Não poder guardar não impede de usar.
  }
  return atualizada;
}
