# Tipo de letra

O Instrument Sans está aqui dentro, e não vem de um CDN, por duas razões: o painel
é servido por nginx dentro de um contentor e tem de funcionar sem internet, e um
pedido a `fonts.gstatic.com` a meio da demonstração é uma dependência de rede que
ninguém quer descobrir na altura.

| Ficheiro | Tipo | Autor | Licença |
|---|---|---|---|
| `instrument-sans-*.woff2` | Instrument Sans (variável: `wght` 400–700) | Instrument | SIL OFL 1.1 — `OFL-InstrumentSans.txt` |

Os subconjuntos `latin` e `latin-ext` chegam para português: o `latin` já cobre
`ã`, `ç`, `õ` e `é`, e o `latin-ext` fica para o resto dos acentos.

A linha gráfica da versão do Jefferson usava Inter, do Google Fonts. Ficou o
Instrument Sans, que é do mesmo género (sem serifa, legível em tamanhos pequenos)
e já estava auto-alojado.
