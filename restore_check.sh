#!/usr/bin/env bash
# Restaura un volcado en una BD VACÍA de prueba y comprueba integridad. NUNCA apuntar a la BD de producción.
# Uso: PG_URL=postgresql://.../bd_vacia scripts/restore_check.sh archivo.dump
set -euo pipefail
: "${PG_URL:?Define PG_URL de la BD destino (vacía)}"; DUMP="${1:?Indica el archivo .dump}"
sha256sum -c "$DUMP.sha256"
pg_restore --no-owner --exit-on-error --dbname="$PG_URL" "$DUMP"
for t in users patients triage_evaluations audit_logs; do echo -n "$t: "; psql "$PG_URL" -Atc "select count(*) from $t"; done
DATABASE_URL="${PG_URL/postgresql:/postgresql+psycopg:}" python3 - <<'PY'
from backend.app.db.session import SessionLocal
from backend.app.services.audit import verify_chain
with SessionLocal() as s: ok, bad = verify_chain(s); print("cadena de auditoría válida:", ok, bad); raise SystemExit(0 if ok else 1)
PY
echo "Restauración verificada."
