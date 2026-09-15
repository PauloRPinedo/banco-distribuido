#!/usr/bin/env bash
# Cria as tabelas na base partilhada. Corre-se UMA vez, de um portátil qualquer.
#
#     BANCO_BD='postgresql://...?sslmode=require' ./scripts/preparar_base.sh
#
# Correr duas vezes falha no CREATE TABLE e não altera nada. É a proteção que se
# quer: apagar as contas dos colegas a meio de um ensaio tinha de ser difícil.
set -euo pipefail

: "${BANCO_BD:?define BANCO_BD com a linha de ligação da base}"

esquema="$(dirname "$0")/../db/esquema.sql"

echo "a criar as tabelas em ${BANCO_BD%%\?*}"
psql "$BANCO_BD" -v ON_ERROR_STOP=1 -f "$esquema"
echo "pronto. Agora, em cada portátil: cp .env.exemplo .env"
