// O endereço do banco não pode ficar aqui gravado, e a razão é prática: o túnel
// HTTPS dá uma URL nova a cada arranque, e a Vercel não injeta variáveis de
// ambiente num sítio estático sem passo de build — que este projeto não tem.
//
// A ordem de precedência está em app.js: ?api= na barra de endereços, depois o
// que ficou guardado no navegador, e só depois este valor.
window.BANCO_URL_BASE = "";
