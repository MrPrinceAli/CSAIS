"""Konfigurasi lokasi file yang dipakai bersama oleh seluruh modul.

Path database dihitung dari lokasi paket ini, sehingga program dapat
dijalankan dari direktori mana pun. Path dapat dioverride lewat
variabel lingkungan ``CSAIS_DB_PATH`` (dipakai untuk pengujian).

File ``.env`` di akar proyek (bila ada) dimuat ke ``os.environ`` saat modul
ini diimpor, agar kredensial Turso dan override lain cukup ditulis di sana.
Variabel yang sudah ada di lingkungan tidak ditimpa.
"""

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASE_DIR = os.path.join(PROJECT_ROOT, "database")


def load_dotenv(path=None):
    """Muat baris KEY=VALUE dari file .env ke os.environ; kembalikan jumlah yang dimuat.

    Baris kosong, komentar (#), dan nilai kosong dilewati; awalan ``export`` dan
    tanda kutip di sekeliling nilai dibuang. Tidak butuh pustaka tambahan.
    """
    path = path or os.path.join(PROJECT_ROOT, ".env")
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return 0
    loaded = 0
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and value and key not in os.environ:
            os.environ[key] = value
            loaded += 1
    return loaded


load_dotenv()

DATABASE_FILE = os.environ.get("CSAIS_DB_PATH") or os.path.join(
    DATABASE_DIR, "csais.db"
)
