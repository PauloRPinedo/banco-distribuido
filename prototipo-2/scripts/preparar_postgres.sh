#!/usr/bin/env bash
# Cria as bases de dados dos nós e aplica o esquema. Idempotente: correr duas
# vezes não faz mal nenhum.
#
#   ./scripts/preparar_postgres.sh            # bases banco_a, banco_b, banco_c
#   ./scripts/preparar_postgres.sh a b        # só as do laptop 1
#
# Cada nó precisa da **sua** base (docs/SPECS.md 4.3): com dois nós na mesma, o
# arranque do segundo é recusado de propósito.
set -euo pipefail

# Sem argumentos, os três nós. Escrito assim e não com ${@:-...} porque essa
# forma devolve "a b c" como uma palavra só, e criaria uma base chamada
# "banco_a b c"; e porque um `[ $# -gt 0 ] && ...` como último comando devolve 1
# quando não há argumentos, o que com `set -e` fazia o script sair em silêncio.
if [ $# -gt 0 ]; then
  NOS=("$@")
else
  NOS=(a b c)
fi

ESQUEMA="$(cd "$(dirname "$0")/.." && pwd)/banco/persistencia/esquema.sql"

if ! command -v psql > /dev/null; then
  echo "  erro: o psql não está instalado" >&2
  echo "  não foi encontrado o cliente do PostgreSQL no PATH" >&2
  echo "  → Debian/Ubuntu: sudo apt install postgresql" >&2
  echo "  → macOS: brew install postgresql@16" >&2
  echo "  → ou use o compose.yaml, ou arranque com --armazem ficheiro" >&2
  exit 1
fi

if ! pg_isready > /dev/null 2>&1; then
  echo "  erro: o servidor PostgreSQL não está a responder" >&2
  echo "  o psql existe, mas não há servidor a aceitar ligações" >&2
  echo "  → Linux: sudo systemctl start postgresql" >&2
  echo "  → macOS: brew services start postgresql@16" >&2
  exit 1
fi

for no in "${NOS[@]}"; do
  base="banco_${no}"
  if psql -lqt | cut -d'|' -f1 | grep -qw "$base"; then
    echo "· $base já existe"
  else
    createdb "$base"
    echo "· $base criada"
  fi
  # client-min-messages=warning cala os "relation already exists, skipping" do
  # IF NOT EXISTS: a idempotência é o objetivo, não algo de que avisar.
  PGOPTIONS='--client-min-messages=warning' psql -q -d "$base" -f "$ESQUEMA"
  echo "  esquema aplicado"
done

echo
echo "Para arrancar um nó:"
for no in "${NOS[@]}"; do
  echo "  python3 -m banco.servidor --id ${no^^} --porta 800X --bd postgresql:///banco_${no}"
done
