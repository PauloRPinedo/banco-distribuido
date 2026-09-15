# Tipos de letra

Os dois tipos estão aqui dentro, e não vêm de um CDN, por duas razões: o painel
é servido por nginx dentro de um contentor e tem de funcionar sem internet, e um
pedido a `fonts.gstatic.com` a meio da demonstração é uma dependência de rede que
ninguém quer descobrir na altura.

| Ficheiro | Tipo | Autor | Licença |
|---|---|---|---|
| `fraunces-*.woff2` | Fraunces (variável: `opsz`, `wght`) | Undercase Type | SIL OFL 1.1 — `OFL-Fraunces.txt` |
| `instrument-sans-*.woff2` | Instrument Sans (variável: `wght`) | Instrument | SIL OFL 1.1 — `OFL-InstrumentSans.txt` |

Os subconjuntos `latin` e `latin-ext` chegam para português: o `latin` já cobre
`ã`, `ç`, `õ` e `é`, e o `latin-ext` fica para o resto dos acentos.

Porque é que este painel descarrega tipos quando `CODESTYLE.md` 8.2 diz para não
o fazer: ver `docs/SPECS.md` 11.11.
