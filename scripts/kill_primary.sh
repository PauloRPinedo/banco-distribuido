#!/usr/bin/env bash
# Derruba o primario atual com SIGKILL (historia de usuario 10, RF-16).
#
# SIGKILL de proposito: um encerramento gentil daria ao processo a chance de dar
# flush no que faltasse, e o teste ficaria facil demais. A corretude tem de vir do
# fsync antes do ACK, nao de um desligamento educado.
#
#   ./scripts/kill_primary.sh            # mata e mostra quem assumiu
#   ./scripts/kill_primary.sh --restart  # mata, espera o failover e sobe de novo (RF-12)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${ROOT}/data"
CONFIG="${ROOT}/config/cluster.json"
RESTART=0
[[ "${1:-}" == "--restart" ]] && RESTART=1

[[ -f "${DATA_DIR}/pids" ]] || { echo "cluster nao esta no ar (sem ${DATA_DIR}/pids)" >&2; exit 1; }

# id -> url, lido da configuracao do cluster
node_urls() {
  python3 -c '
import json, sys
cfg = json.load(open(sys.argv[1]))
for n in cfg["nodes"]:
    print(n["id"], "http://%s:%d" % (n["host"], n["port"]))
' "$CONFIG"
}

# Imprime "<id> <url>" do no que se declara primario, ou nada.
find_primary() {
  while read -r ID URL; do
    ROLE="$(curl -s --max-time 1 "${URL}/admin/status" 2>/dev/null \
            | python3 -c 'import json,sys; print(json.load(sys.stdin).get("role",""))' 2>/dev/null || true)"
    if [[ "$ROLE" == "primary" ]]; then
      echo "$ID $URL"
      return 0
    fi
  done < <(node_urls)
  return 1
}

read -r OLD_ID OLD_URL < <(find_primary) || { echo "nenhum primario encontrado" >&2; exit 1; }
OLD_EPOCH="$(curl -s "${OLD_URL}/admin/status" | python3 -c 'import json,sys; print(json.load(sys.stdin)["epoch"])')"
OLD_PID="$(awk -v id="$OLD_ID" '$1==id {print $2}' "${DATA_DIR}/pids")"

echo "primario atual: ${OLD_ID} (pid ${OLD_PID}, epoch ${OLD_EPOCH}) -- enviando SIGKILL"
kill -9 "$OLD_PID"

# O failover deve concluir em poucos segundos (RNF-03).
START="$(date +%s)"
for _ in $(seq 1 30); do
  sleep 0.5
  if read -r NEW_ID NEW_URL < <(find_primary); then
    if [[ "$NEW_ID" != "$OLD_ID" ]]; then
      NEW_EPOCH="$(curl -s "${NEW_URL}/admin/status" | python3 -c 'import json,sys; print(json.load(sys.stdin)["epoch"])')"
      echo "novo primario: ${NEW_ID} (epoch ${NEW_EPOCH}) apos $(( $(date +%s) - START ))s"
      [[ "$NEW_EPOCH" -gt "$OLD_EPOCH" ]] || echo "AVISO: epoch nao avancou -- investigar" >&2
      break
    fi
  fi
done

if [[ "$RESTART" -eq 1 ]]; then
  echo "reiniciando ${OLD_ID} para testar a reintegracao (RF-12)"
  python -m bank.server --config "$CONFIG" --id "$OLD_ID" --data-dir "$DATA_DIR" \
    > "${DATA_DIR}/${OLD_ID}.out" 2>&1 &
  # substitui o pid antigo no arquivo
  TMP="$(mktemp)"
  awk -v id="$OLD_ID" -v pid="$!" '$1==id {$2=pid} {print}' "${DATA_DIR}/pids" > "$TMP"
  mv "$TMP" "${DATA_DIR}/pids"
  echo "${OLD_ID} reiniciado (pid $!); deve voltar como replica e alcancar o log"
fi
