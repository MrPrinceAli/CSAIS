#!/usr/bin/env bash
# Jalankan blockchain lokal (Anvil) untuk prototipe penjangkaran CSAIS.
# State disimpan ke chain/anvil-state.json (dimuat lagi saat start, disimpan
# tiap 30 detik dan saat berhenti), jadi jangkar tidak hilang saat Anvil mati.
#
# Setelah jalan, di terminal lain:
#   python main.py --chain-deploy   # sekali saja, pasang kontrak
#   python main.py --anchor         # jangkarkan batch yang menunggu
set -euo pipefail
cd "$(dirname "$0")/.."
exec anvil --chain-id 31337 --state chain/anvil-state.json --state-interval 30 --host 127.0.0.1 --port 8545 "$@"
