// Percorre o painel num navegador sem janela e tira uma captura por passo.
//
//     cd prototipo-2/provas/scripts
//     npm install --no-save playwright-core   # só para isto; não é dependência do projeto
//     CHROMIUM=/caminho/para/chrome node capturas_painel.mjs
//
// Contra o compose a correr (painel em http://localhost:8080). As capturas vão
// para provas/capturas/. Cada passo confere o que aparece no ecrã; se algo não
// aparecer, o script para com erro em vez de tirar uma captura enganadora.

import { execSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const PAINEL = process.env.PAINEL || "http://localhost:8080/";
const BALANCEADOR = process.env.BALANCEADOR || "http://localhost:8000";
// Onde está o compose.yaml, para matar e trazer de volta um nó. A SECRET_KEY
// tem de estar no ambiente: o nó tem de voltar com a mesma chave.
const PROTOTIPO = process.env.PROTOTIPO || join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const compose = (argumentos) => execSync(`docker compose ${argumentos}`, { cwd: PROTOTIPO, stdio: "ignore" });
const PASTA = join(dirname(fileURLToPath(import.meta.url)), "..", "capturas");
const SUFIXO = Math.random().toString(16).slice(2, 8);
mkdirSync(PASTA, { recursive: true });

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM });
const page = await browser.newPage({ viewport: { width: 1280, height: 860 } });
const errosDePagina = [];
page.on("pageerror", (erro) => errosDePagina.push(String(erro)));

let numero = 0;
async function captura(nome, { inteira = false } = {}) {
  await page.waitForTimeout(700); // deixar acabar a entrada animada dos cartões
  numero += 1;
  const ficheiro = `${String(numero).padStart(2, "0")}-${nome}.png`;
  await page.screenshot({ path: join(PASTA, ficheiro), fullPage: inteira });
  console.log("captura", ficheiro);
}

const formulario = () => page.locator("form");
const conta = (nome) => `${nome}-${SUFIXO}`;

async function abrirConta(id, saldo, { moeda = "BRL", produto = "corrente", taxa, prazo } = {}) {
  await page.getByLabel("Identificador").fill(id);
  await page.getByLabel(/Saldo inicial/).fill(saldo);
  await page.getByLabel("Moeda").selectOption(moeda);
  await page.getByLabel("Produto").selectOption(produto);
  if (taxa) await page.getByLabel(/Taxa de juros/).fill(taxa);
  if (prazo) await page.getByLabel("Prazo em dias").fill(prazo);
  await page.getByRole("button", { name: "Abrir conta" }).click();
  await page.getByText(`saldo de ${id}`).waitFor();
}

async function transferir(modo, de, destino, valor) {
  await page.getByRole("button", { name: modo }).click();
  await page.getByLabel(/^De/).fill(de);
  if (destino) await page.getByLabel("Para").fill(destino);
  await page.getByLabel(/^Valor/).fill(valor);
  await formulario().getByRole("button", { name: "Transferir" }).click();
}

// ------------------------------------------------------------------ sessão
await page.goto(PAINEL);
await page.getByRole("heading", { name: "Iniciar sessão" }).waitFor();
await captura("login");

await page.getByRole("button", { name: "Entrar" }).first().waitFor();
await page.getByLabel("Email").fill(`ana-${SUFIXO}@teste.pt`);
await page.getByLabel(/Senha/).fill("errada");
await page.locator("form").getByRole("button", { name: "Entrar" }).click();
await page.getByText("email ou senha incorretos").waitFor();
await captura("login-recusado");

await page.getByRole("button", { name: "Criar utilizador" }).click();
await page.getByLabel("Nome").fill("Ana");
await page.getByLabel(/Senha/).fill("segredo-ana");
await captura("registo");
await page.getByRole("button", { name: "Registar e entrar" }).click();
await page.getByRole("button", { name: "Abrir conta" }).waitFor();
await captura("contas-vazio");

// ------------------------------------------------------------------ contas
const corrente = conta("corrente");
await abrirConta(corrente, "100.00");
await captura("conta-corrente-aberta");

await page.getByLabel("Valor", { exact: true }).fill("25.50");
await page.getByRole("button", { name: "Depositar" }).click();
await page.getByText("depósito de 25.50 confirmado").waitFor();
await captura("deposito-e-extrato");

await page.getByLabel("Valor", { exact: true }).fill("9999.00");
await page.getByRole("button", { name: "Sacar" }).click();
await page.getByText(/e a operação pede R\$ 9\.999,00/).waitFor();
await captura("saque-sem-saldo");

await page.getByLabel("Valor", { exact: true }).fill("10.00");
await page.getByRole("button", { name: "Sacar" }).click();
await page.getByText("saque de 10.00 confirmado").waitFor();

const dolares = conta("dolares");
await abrirConta(dolares, "50.00", { moeda: "USD" });
await captura("conta-em-dolares");

await abrirConta(conta("poupanca"), "1000.00", { produto: "poupanca", taxa: "0.10" });
await captura("poupanca");

const prazo = conta("prazo");
await abrirConta(prazo, "500.00", { produto: "prazo_fixo", taxa: "0.12", prazo: "30" });
await page.getByLabel("Valor", { exact: true }).fill("1.00");
await page.getByRole("button", { name: "Sacar" }).click();
await page.getByText(/é um prazo fixo e só vence a/).waitFor();
await captura("prazo-fixo-bloqueado");

// ------------------------------------------------------------------ transferir
await page.getByRole("button", { name: "Transferir", exact: true }).first().click();
const destino = conta("destino");
// a conta de destino abre-se pela aba de contas; volta-se depois
await page.getByRole("button", { name: "Contas" }).click();
await abrirConta(destino, "0");
await page.getByRole("button", { name: "Transferir", exact: true }).first().click();

await transferir("Mesma moeda", corrente, destino, "30.00");
await page.getByText("✓ confirmada").waitFor();
await captura("transferencia");

await transferir("Mesma moeda", dolares, corrente, "1.00");
await page.getByText(/entre moedas é um câmbio/).waitFor();
await captura("transferencia-entre-moedas-recusada");

await transferir("Câmbio", dolares, corrente, "10.00");
await page.getByText(/^câmbio a/i).waitFor();
await captura("cambio");

await transferir("Outro banco", corrente, null, "5.00");
await page.locator("text=/confirmada · ref|rejeitada pelo outro banco/").waitFor();
await captura("transferencia-externa");

// ------------------------------------------------------------------ auditoria
await page.getByRole("button", { name: "Auditoria" }).click();
await page.getByText("USD", { exact: true }).waitFor();
await page.getByRole("button", { name: "Creditar juros agora" }).click();
await page.getByText(/conta\(s\) com juros creditados/).waitFor();
await captura("auditoria-por-moeda", { inteira: true });

// ------------------------------------------------------------------ cluster
await page.getByRole("button", { name: "Cluster" }).click();
await page.getByText(/^3 de 3 nós de pé/).waitFor();
await captura("cluster", { inteira: true });

const primario = (await (await fetch(`${BALANCEADOR}/interno/estado`)).json()).no;
compose(`kill no-${primario.toLowerCase()}`);
console.log(`matou-se o nó ${primario}`);
await page.getByText(/^2 de 3 nós de pé/).waitFor({ timeout: 20000 });
await page.locator(".no-do-cluster.e-primario").waitFor({ timeout: 20000 });
await captura("cluster-depois-de-matar-o-primario", { inteira: true });

// O dinheiro continua lá, servido pelo novo primário.
await page.getByRole("button", { name: "Contas" }).click();
await page.getByRole("button", { name: corrente }).click();
await page.getByText(`saldo de ${corrente}`).waitFor();
await page.getByLabel("Valor", { exact: true }).fill("1.00");
await page.getByRole("button", { name: "Depositar" }).click();
await page.getByText("depósito de 1.00 confirmado").waitFor();
await captura("contas-depois-da-queda");

compose(`start no-${primario.toLowerCase()}`);
await page.getByRole("button", { name: "Cluster" }).click();
await page.getByText(/^3 de 3 nós de pé/).waitFor({ timeout: 30000 });
await captura("cluster-no-de-volta", { inteira: true });

// ------------------------------------------------------------------ telemóvel
await page.setViewportSize({ width: 390, height: 844 });
await page.getByRole("button", { name: "Contas" }).click();
await page.getByRole("button", { name: corrente }).click();
await page.getByText(`saldo de ${corrente}`).waitFor();
await captura("telemovel-contas", { inteira: true });

// ------------------------------------------------------------------ sair
await page.setViewportSize({ width: 1280, height: 860 });
await page.getByRole("button", { name: "Sair" }).click();
await page.getByRole("heading", { name: "Iniciar sessão" }).waitFor();
await captura("depois-de-sair");

await browser.close();
if (errosDePagina.length) {
  console.error("erros de JavaScript na página:", errosDePagina);
  process.exit(1);
}
console.log(`${numero} capturas, sem erros de JavaScript na página`);
