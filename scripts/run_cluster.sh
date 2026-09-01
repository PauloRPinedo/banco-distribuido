#!/usr/bin/env bash
# Sobe um cluster local de 3 servidores (RNF-09: Linux e macOS, um unico comando).
#
#   ./scripts/run_cluster.sh              # 3 nos, dados em ./data
#   ./scripts/run_cluster.sh --clean      # apaga ./data antes (estado zerado)
#   ./scripts/run_cluster.sh --nodes 2    # cluster minimo de 2
#
# Os PIDs ficam em ./data/pids para o kill_primary.sh e o encerramento.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${ROOT}/config/cluster.json"
DATA_DIR="${ROOT}/data"
NODES=3
CLEAN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --clean) CLEAN=1; shift ;;
    --nodes) NODES="$2"; shift 2 ;;
    --config) CONFIG="$2"; shift 2 ;;
    *) echo "argumento desconhecido: $1" >&2; exit 2 ;;
  esac
done

[[ -f "$CONFIG" ]] || cp "${ROOT}/config/cluster.example.json" "$CONFIG"
[[ "$CLEAN" -eq 1 ]] && rm -rf "$DATA_DIR"
mkdir -p "$DATA_DIR"
: > "${DATA_DIR}/pids"

IDS=(A B C)
for i in $(seq 0 $((NODES - 1))); do
  ID="${IDS[$i]}"
  python -m bank.server --config "$CONFIG" --id "$ID" --data-dir "$DATA_DIR" \
    > "${DATA_DIR}/${ID}.out" 2>&1 &
  echo "$ID $!" >> "${DATA_DIR}/pids"
  echo "no ${ID} iniciado (pid $!)"
done

echo
echo "cluster de ${NODES} nos no ar. Para ver quem e o primario:"
echo "  python cli/banco_cli.py status"
echo "Para derrubar o primario (RF-16, historia de usuario 10):"
echo "  ./scripts/kill_primary.sh"
echo "Para parar tudo:"
echo "  awk '{print \$2}' ${DATA_DIR}/pids | xargs kill"
