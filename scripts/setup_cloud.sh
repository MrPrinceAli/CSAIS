#!/bin/sh
# Siapkan jalur cloud setelah .env terisi:
#   1. simpan TURSO_DATABASE_URL dan TURSO_AUTH_TOKEN sebagai rahasia GitHub Actions
#   2. unggah database SQLite saat ini sebagai rilis "bootstrap" (dipakai run pertama)
# Butuh `gh` yang sudah login ke akun pemilik repo.
# Pemakaian: scripts/setup_cloud.sh [--no-release]
set -eu
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

[ -f .env ] || { echo "File .env tidak ada; salin dari .env.example lalu isi." >&2; exit 1; }
set -a
. ./.env
set +a
: "${TURSO_DATABASE_URL:?TURSO_DATABASE_URL masih kosong di .env}"
: "${TURSO_AUTH_TOKEN:?TURSO_AUTH_TOKEN masih kosong di .env}"

gh secret set TURSO_DATABASE_URL --body "$TURSO_DATABASE_URL"
gh secret set TURSO_AUTH_TOKEN --body "$TURSO_AUTH_TOKEN"
echo "Rahasia Turso tersimpan di GitHub Actions."

if [ "${1:-}" != "--no-release" ]; then
  sqlite3 database/csais.db "PRAGMA wal_checkpoint(TRUNCATE);" >/dev/null
  if gh release view bootstrap >/dev/null 2>&1; then
    gh release upload bootstrap database/csais.db --clobber
  else
    gh release create bootstrap database/csais.db --title "Database bootstrap" \
      --notes "Database SQLite awal untuk run pertama workflow harian."
  fi
  echo "Rilis bootstrap berisi database/csais.db sudah diunggah."
fi
