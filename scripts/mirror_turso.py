"""Salin tabel terbit dari Turso ke berkas SQLite lokal (hanya membaca Turso).

    python scripts/mirror_turso.py database/demo.db

Dipakai scripts/demo_local.sh agar website bisa dijalankan dan dirancang di
komputer sendiri dengan data yang sama seperti situs live, tanpa menulis apa
pun ke Turso. Kredensial dibaca dari .env (TURSO_DATABASE_URL, TURSO_AUTH_TOKEN).
"""

import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import csais.config  # noqa: E402,F401  (memuat .env)
from csais.publish import TursoClient  # noqa: E402

PAGE = 5000


def _converter(declared):
    """Turso mengirim angka sebagai teks; kembalikan ke tipe kolomnya."""
    declared = (declared or "").upper()
    if "INT" in declared:
        return int
    if any(word in declared for word in ("REAL", "FLOA", "DOUB")):
        return float
    return None


def _create(local, table, columns, primary_key):
    """Buat tabel lokal. Turso menyimpan tabel terbit tanpa primary key, jadi kolom
    pertama ``*_id`` INTEGER dijadikan INTEGER PRIMARY KEY lagi: tahap pipeline
    yang menambah baris (mis. flow_outputs) mengandalkan nomor otomatisnya."""
    body = []
    for index, (_, name, declared, *_rest) in enumerate(columns):
        key = primary_key and index == 0
        body.append(f'"{name}" {"INTEGER PRIMARY KEY" if key else declared}')
    local.execute(f'DROP TABLE IF EXISTS "{table}"')
    local.execute(f'CREATE TABLE "{table}" ({", ".join(body)})')


def _convert(convert, value):
    if value is None or convert is None:
        return value
    try:
        return convert(value)
    except ValueError:
        return value


def mirror(client, path, log=print):
    tables = [row[0] for row in client.query(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        " AND name NOT LIKE '%\\_\\_new' ESCAPE '\\' AND name NOT LIKE '%\\_\\_add' ESCAPE '\\'"
    )]
    local = sqlite3.connect(path)
    for table in tables:
        columns = client.query(f'PRAGMA table_info("{table}")')
        names = [column[1] for column in columns]
        converters = [_converter(column[2]) for column in columns]
        primary_key = names[0].endswith("_id") and (columns[0][2] or "").upper() == "INTEGER"
        insert = f'INSERT INTO "{table}" VALUES ({", ".join("?" for _ in names)})'
        started = time.time()
        while True:
            _create(local, table, columns, primary_key)
            last, total = 0, 0
            try:
                while True:
                    rows = client.query(f'SELECT rowid, * FROM "{table}" WHERE rowid > ? ORDER BY rowid LIMIT ?', [last, PAGE])
                    if not rows:
                        break
                    local.executemany(insert, [[_convert(f, v) for f, v in zip(converters, row[1:])] for row in rows])
                    last, total = int(rows[-1][0]), total + len(rows)
            except sqlite3.IntegrityError:
                if not primary_key:
                    raise
                primary_key = False  # nilai kolom pertama tidak unik: tanpa primary key
                continue
            break
        local.commit()
        log(f"   {table:28s} {total:7d} baris  {time.time() - started:5.1f} s")
    for (sql,) in client.query("SELECT sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL"):
        try:
            local.execute(sql)
        except sqlite3.OperationalError:
            pass  # index tabel sementara
    local.commit()
    local.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    url, token = os.environ.get("TURSO_DATABASE_URL", ""), os.environ.get("TURSO_AUTH_TOKEN")
    if not url or url.startswith("file:"):
        raise SystemExit("TURSO_DATABASE_URL di .env harus menunjuk ke Turso")
    mirror(TursoClient(url, token), sys.argv[1])
