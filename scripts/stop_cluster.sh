#!/usr/bin/env bash
# Para todos os nos do cluster local, pelos PIDs registrados em data/pids.
#
# Mata por PID, e nao por padrao de nome (`pkill -f bank.server`): o padrao
# tambem casaria com o proprio shell que roda este script, que entao se mataria
# antes de terminar o trabalho.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${ROOT}/data"
PIDS="${DATA_DIR}/pids"

[[ -f "$PIDS" ]] || { echo "nada a parar (sem ${PIDS})"; exit 0; }

while read -r ID PID; do
  [[ -n "${PID:-}" ]] || continue
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null && echo "no ${ID} (pid ${PID}) encerrado"
  else
    echo "no ${ID} (pid ${PID}) ja estava fora do ar"
  fi
done < "$PIDS"

# Prazo curto para o encerramento limpo (flush do WAL) antes do SIGKILL.
sleep 1
while read -r ID PID; do
  [[ -n "${PID:-}" ]] || continue
  kill -0 "$PID" 2>/dev/null && kill -9 "$PID" 2>/dev/null && echo "no ${ID} forcado"
done < "$PIDS"

rm -f "$PIDS"
echo "cluster parado"
