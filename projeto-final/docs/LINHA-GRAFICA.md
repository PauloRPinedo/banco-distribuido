# Linha gráfica do painel

O desenho é o da versão do Jefferson, traduzido e arrumado. É uma só página
responsiva, que ocupa sempre a janela inteira; não há moldura de telefone. A
base é o telemóvel, e cada patamar acrescenta espaço:

| Largura | Como se vê |
|---|---|
| Até 767px (telemóvel) | Cabeçalho fixo com menu, logótipo e título; conteúdo numa coluna |
| 768–1023px (tablet) | O mesmo cabeçalho; conteúdo centrado, contas e nós em grelha |
| 1024px ou mais (portátil, computador) | Barra lateral e conteúdo em grelha; sem sessão, a marca de um lado e o formulário do outro |
| 1200px ou mais | No Início, o saldo e os atalhos lado a lado |

Os ecrãs são os mesmos componentes em todos os tamanhos: muda o `estilo.css`,
não o código de cada página. Verificado de 360px a 1920px sem barra de
deslocamento horizontal.

## Cor

| Token (`src/estilo.css`) | Valor | Uso |
|---|---|---|
| `--roxo` | `#820AD1` | Botão principal, ligações, marca |
| `--roxo-escuro` | `#5A0791` | Botão premido |
| `--roxo-suave` | `#F3E8FC` | Avisos, confirmação do titular |
| `--fundo` | `#F7F7F9` | Fundo do ecrã e dos campos |
| `--superficie` | `#FFFFFF` | Cartões e cabeçalho |
| `--borda` | `#E7E7EC` | Bordas |
| `--texto` | `#1A1A2E` | Texto principal |
| `--texto-tenue` | `#6B6B7B` | Rótulos e ajuda |
| `--sucesso` | `#00A868` | Carimbo de confirmação, auditoria que bate |
| `--erro` | `#E5484D` | Erros, auditoria que não bate, nó em baixo |

A barra do navegador usa o mesmo roxo (`theme-color`).

## Letra e espaço

Instrument Sans, auto-alojada em `public/tipos/`. A versão original usava a Inter
do Google Fonts; trocou-se para o painel não depender de um CDN (ver
`public/tipos/LEIA-ME.md`). Pesos de 400 a 700.

- Título do cabeçalho: 16px, peso 700.
- Rótulos dos campos: em maiúsculas, 11px.
- Quantias grandes: 32px, peso 700.
- Campos de texto: 16px. Abaixo disso, o iOS faz zoom ao focar o campo.
- Botão principal: 54px de altura no mínimo, com a largura do cartão.
- Raios: cartões 20px, botões 14px, campos 12px.

## Peças (`src/componentes/`)

| Peça | O que é |
|---|---|
| `Ecra` | A moldura: cabeçalho com o logótipo, o título, "voltar" ou o menu, e uma ação à direita. No computador, também a barra lateral (com sessão) ou o painel da marca (sem sessão). `publico` marca entrada, registo e termos; `largura` é `estreita` (formulários, 600px), `media` (listas, 840px) ou `larga` (grelhas, 1160px) |
| `Campo` | Rótulo e `<input>` (ou o `<select>` que vier como filho), com ajuda opcional |
| `CampoConta` | Escolher uma das contas de quem tem a sessão, pelo número |
| `Botao` | Principal, secundário ou perigo |
| `Aviso` | Nota neutra, de sucesso ou de erro (`role="alert"`) |
| `Icones` | Ícones de traço em `currentColor` |
| `Carregamento` | O texto enquanto chega o código de outro ecrã |

A marca é o escudo com o infinito de `public/logo.png`. O favicon e os ícones
(`favicon.png`, `icon-192.png`, `icon-512.png`) são o mesmo escudo.

## Telemóvel

A página tem a altura da janela (`100dvh`) e o cabeçalho fica fixo no topo. O
espaçamento respeita a área segura do telefone (`safe-area-inset`). No tablet,
o conteúdo centra-se com uma largura máxima (600, 840 ou 1160px, conforme a
`largura` do ecrã) e as contas, as moedas da auditoria e os nós passam a
grelha.

Os termos, abertos a partir do registo, saem numa cortina por cima do
formulário, para não apagar o que a pessoa já escreveu.

## Computador

De 1024px para cima:

- **Com sessão.** Uma barra lateral branca de 272px, fixa, com o logótipo, o
  Início, os grupos *Dinheiro* e *Mais* (os mesmos destinos do menu do
  telemóvel, com ícone) e *Sair* em baixo. A página aberta fica em roxo suave.
  O cabeçalho passa a título da página, a 28px, sem logótipo, sem "voltar" e
  sem menu: a barra leva a todo o lado.
- **Início.** O saldo em destaque (44px), os quatro atalhos numa fila e as
  contas em grelha, até seis antes de "ver todas". De 1200px para cima, o
  saldo e os atalhos (em 2 × 2, como cartões) ficam lado a lado.
- **Grelhas.** Os nós do cluster em três colunas; as moedas da auditoria em
  cartões lado a lado. Numa página larga, os botões têm a largura do texto.
- **Sem sessão.** O ecrã divide-se a meio: à esquerda, o painel da marca
  (o degradê roxo do saldo, o logótipo num quadrado branco, três frases sobre o
  banco); à direita, o formulário, com 440px.
- Com rato, os botões e as opções escurecem ao passar por cima.

## O que se carrega

O ecrã de entrada vai na primeira descarga. Os outros ecrãs são módulos à parte
(`React.lazy`): registo, termos, início e cada operação. O navegador só os pede
quando se abre essa rota.

## Instalar no telefone

`public/manifest.webmanifest` diz o nome, os ícones e o modo `standalone`: o
navegador do telefone deixa adicionar o banco ao ecrã principal. Ao contrário da
versão original, não há *service worker*. O painel não abre sem rede, e
nenhuma resposta da API fica em cache. Num banco, um saldo velho no ecrã é pior
do que não abrir.
