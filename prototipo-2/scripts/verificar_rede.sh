#!/usr/bin/env bash
# Testa cada endereço do cluster ANTES de subir os nós.
#
#   ./scripts/verificar_rede.sh config/cluster.json
#
# Este passo evita o modo de falha mais confuso do projeto: com uma porta
# bloqueada pela firewall, os sintomas — eleições sem fim, epoch a subir sozinho
# — parecem um erro de protocolo e levam a procurar no sítio errado durante
# horas. Cinco segundos de curl respondem à pergunta.
set -uo pipefail

CONFIG="${1:-config/cluster.json}"

if [ ! -f "$CONFIG" ]; then
  echo "  erro: não existe $CONFIG" >&2
  echo "  o ficheiro do cluster é local a cada máquina e não está versionado" >&2
  echo "  → copie o exemplo: cp config/cluster.exemplo.json $CONFIG" >&2
  exit 2
fi

echo "Nós declarados em $CONFIG:"
FALHAS=0
while IFS=$'\t' read -r id endereco porta; do
  url="http://${endereco}:${porta}/interno/estado"
  if resposta=$(curl -s --max-time 3 "$url"); then
    echo "  ✓ $id  $endereco:$porta  $resposta"
  else
    echo "  ✗ $id  $endereco:$porta  sem resposta"
    FALHAS=$((FALHAS + 1))
  fi
done < <(python3 -c "
import json, sys
for no in json.load(open('$CONFIG'))['nos']:
    print(no['id'], no['endereco'], no['porta'], sep='\t')
")

echo
if [ "$FALHAS" -gt 0 ]; then
  echo "  $FALHAS nó(s) sem resposta."
  echo "  Se ainda não os arrancou, é o esperado. Se já arrancou, confirme:"
  echo "  → o nó liga em 0.0.0.0 e não em 127.0.0.1"
  echo "  → a porta está aberta na firewall desse laptop"
  exit 1
fi
echo "  Todos os nós responderam. Pode subir o cluster."
