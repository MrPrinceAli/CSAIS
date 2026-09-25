#!/bin/sh
# Jalankan crawl harian tanpa prompt, lalu olah artikel baru.
# Contoh penjadwalan dengan cron (setiap hari pukul 06:00):
#   0 6 * * * /path/ke/CSAIS/scripts/run_daily.sh
# Keluaran layar disalin otomatis ke folder logs/ oleh main.py.
set -eu
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
exec ./.venv/bin/python main.py --crawl
