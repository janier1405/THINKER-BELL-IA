#!/usr/bin/env bash
# Copia lógica de PostgreSQL. Uso: PG_URL=postgresql://usuario:clave@host/bd scripts/backup.sh [archivo.dump]
# ATENCIÓN: el volcado contiene datos de pacientes. Cifrarlo y guardarlo fuera del servidor (pendiente de implementar aquí).
set -euo pipefail
: "${PG_URL:?Define PG_URL (formato libpq, sin +psycopg)}"
OUT="${1:-backup_$(date +%Y%m%d_%H%M%S).dump}"
umask 077
pg_dump --format=custom --no-owner --file="$OUT" "$PG_URL"
sha256sum "$OUT" > "$OUT.sha256"
echo "Copia creada: $OUT"
