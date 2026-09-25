"""Konfigurasi lokasi file yang dipakai bersama oleh seluruh modul.

Path database dihitung dari lokasi paket ini, sehingga program dapat
dijalankan dari direktori mana pun. Path dapat dioverride lewat
variabel lingkungan ``CSAIS_DB_PATH`` (dipakai untuk pengujian).
"""

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASE_DIR = os.path.join(PROJECT_ROOT, "database")

DATABASE_FILE = os.environ.get("CSAIS_DB_PATH") or os.path.join(
    DATABASE_DIR, "csais.db"
)
