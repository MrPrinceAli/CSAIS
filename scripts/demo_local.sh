#!/usr/bin/env bash
# Website CSAIS di komputer sendiri dengan data uji, untuk melihat dan merancang
# tampilan tanpa menyentuh database live (Turso hanya dibaca saat mirror).
#
#   scripts/demo_local.sh mirror   # salin data situs live ke database/demo.db
#   scripts/demo_local.sh start    # jalankan website di http://localhost:3100
#   scripts/demo_local.sh seed     # (server harus jalan) isi data uji D2 - D4,
#                                  # lalu hitung ulang alur D1 - D4, peringatan, dan metrik
#
# Portal lembaga lokal memakai kunci uji database/demo-portal.json; password
# tiap lembaga ada di TEST_PASSWORDS di bawah. Semua berkas demo ada di
# database/ dan tidak ikut git.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
DB="$ROOT/database/demo.db"
SURVEY="$ROOT/database/demo-survey.db"
KEYS="$ROOT/database/demo-portal.json"
PORT="${PORT:-3100}"
TEST_PASSWORDS='{"BSSN":"bssn-uji","OJK":"ojk-uji","KOMDIGI":"komdigi-uji","POLRI":"polri-uji"}'

case "${1:-start}" in
  mirror)
    python3 scripts/mirror_turso.py "$DB"
    ;;
  start)
    [ -f "$DB" ] || { echo "database/demo.db belum ada; jalankan dulu: scripts/demo_local.sh mirror"; exit 1; }
    [ -f "$KEYS" ] || (cd web && echo "$TEST_PASSWORDS" | node scripts/portal-keys.mjs > "$KEYS")
    PORTAL_KEYS=$(python3 -c "import json, sys; print(json.dumps(json.load(open(sys.argv[1]))['portalKeys']))" "$KEYS")
    cd web
    TURSO_DATABASE_URL="file:$DB" SURVEY_DATABASE_URL="file:$SURVEY" SURVEY_SALT=lokal \
      PORTAL_KEYS="$PORTAL_KEYS" PORTAL_SECRET=demo-lokal-0123456789abcdef \
      exec npx next dev -p "$PORT"
    ;;
  seed)
    export TURSO_DATABASE_URL="file:$DB" SURVEY_DATABASE_URL="file:$SURVEY" CSAIS_DB_PATH="$DB" \
      CSAIS_WEB_URL="http://localhost:$PORT" PORTAL_PASSWORDS="$TEST_PASSWORDS"
    rm -f "$SURVEY"
    python3 -c "from csais import flows; from csais.db import get_connection; print('Keluaran demo lama dihapus:', flows.purge_demo_outputs(get_connection()))"
    python3 -c "from csais import flows, regions; regions.run(); flows.run()"
    python3 main.py --seed-demo
    DEMO_OVERLAP=1 python3 main.py --seed-demo
    python3 -c "
from csais import flow_compare, flows, official, survey, v07_trust_score
for step in (survey.run, official.run, v07_trust_score.verification_run, flows.tiers_run, flow_compare.run):
    step()
"
    ;;
  *)
    echo "pakai: scripts/demo_local.sh mirror|start|seed"; exit 1
    ;;
esac
