"""Terbitkan hasil pipeline ke Turso (SQLite yang di-host) lewat HTTP API.

Pekerja pipeline tetap bekerja pada file SQLite lokal (cepat), lalu tahap ini
menyalin tabel yang dibutuhkan dashboard ke Turso. Setiap tabel ditulis ke
tabel sementara ``<nama>__new`` per potongan (masing-masing satu transaksi),
lalu ditukar dengan tabel lama dalam satu transaksi, sehingga pembaca tidak
pernah melihat tabel setengah terisi.

Kredensial dibaca dari variabel lingkungan:
  TURSO_DATABASE_URL  misalnya libsql://csais-nama.turso.io
  TURSO_AUTH_TOKEN    token dari `turso db tokens create <db>`
"""

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import requests

from csais.db import get_connection, get_timestamp
from csais.schema import record_run

CHUNK_ROWS = 2000  # baris per permintaan HTTP (satu transaksi)
ROWS_PER_STATEMENT = 100  # baris per statement INSERT multi-baris
WORKERS = 4  # tabel yang disalin bersamaan (masing-masing koneksi dan sesi sendiri)
REQUEST_TIMEOUT = 120

# Tabel yang diterbitkan: nama -> (SELECT sumber, daftar index remote)
PUBLISH_TABLES = {
    "sources": ("SELECT * FROM sources", []),
    "pipeline_runs": ("SELECT * FROM pipeline_runs", []),
    "articles": (
        """
        SELECT article_id, article_uid, article_url, resolved_url, title, summary,
               language, published_date, source_name, source_type, syndicated_of,
               content_status, content_sha256, content_fetched_at
        FROM articles
        WHERE article_id IN (SELECT article_id FROM v05_incident_documents)
        """,
        ["article_id", "article_uid", "published_date"],
    ),
    "v02_relevance": (
        "SELECT * FROM v02_relevance WHERE article_id IN "
        "(SELECT article_id FROM v05_incident_documents)",
        ["article_id", "relevance_label"],
    ),
    "v03_information_extraction": (
        "SELECT * FROM v03_information_extraction",
        ["article_id", "attack_type"],
    ),
    "v04_entities": ("SELECT * FROM v04_entities", ["entity_type"]),
    "v04_entity_mentions": ("SELECT * FROM v04_entity_mentions", ["article_id", "entity_id"]),
    "v05_incidents": (
        "SELECT * FROM v05_incidents",
        ["incident_id", "anchor_published_date", "attack_type", "target", "document_count"],
    ),
    "v05_incident_documents": (
        "SELECT * FROM v05_incident_documents",
        ["incident_id", "article_id"],
    ),
    "v06_evidence": ("SELECT * FROM v06_evidence", ["incident_id", "article_id"]),
    "v06_source_relations": ("SELECT * FROM v06_source_relations", ["incident_id"]),
}


# --- Transport ---
def _to_arg(value):
    """Nilai Python -> argumen JSON API Turso (hrana)."""
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "integer", "value": str(int(value))}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    if isinstance(value, bytes):
        raise TypeError("blob tidak didukung dalam publikasi")
    return {"type": "text", "value": str(value)}


class TursoClient:
    """Klien kecil untuk endpoint /v2/pipeline Turso."""

    def __init__(self, database_url, auth_token, session=None):
        if not database_url or not auth_token:
            raise ValueError(
                "TURSO_DATABASE_URL dan TURSO_AUTH_TOKEN harus diisi untuk --publish"
            )
        url = database_url.strip()
        for scheme in ("libsql://", "wss://", "ws://"):
            if url.startswith(scheme):
                url = "https://" + url[len(scheme) :]
        self.endpoint = url.rstrip("/") + "/v2/pipeline"
        self.headers = {"Authorization": f"Bearer {auth_token}"}
        self.session = session or requests.Session()

    def execute(self, statements):
        """Jalankan daftar (sql, args) berurutan dalam satu permintaan; kembalikan hasilnya."""
        payload = {
            "requests": [
                {"type": "execute", "stmt": {"sql": sql, "args": [_to_arg(a) for a in args]}}
                for sql, args in statements
            ]
            + [{"type": "close"}]
        }
        response = self.session.post(
            self.endpoint, json=payload, headers=self.headers, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        for result in results:
            if result.get("type") == "error":
                raise RuntimeError(f"Turso: {result.get('error', {}).get('message')}")
        return results

    def transaction(self, statements):
        """Jalankan statements di dalam BEGIN ... COMMIT (satu permintaan)."""
        return self.execute([("BEGIN", [])] + list(statements) + [("COMMIT", [])])


# --- Skema ---
def column_definitions(conn, table, select_sql):
    """(nama, tipe) kolom hasil SELECT, tipe diambil dari PRAGMA table_info tabel asal."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    declared = {row[1]: (row[2] or "TEXT") for row in cursor.fetchall()}
    cursor.execute(f"SELECT * FROM ({select_sql}) LIMIT 0")
    return [(desc[0], declared.get(desc[0], "TEXT")) for desc in cursor.description]


def create_statements(table, columns):
    body = ", ".join(f'"{name}" {ctype}' for name, ctype in columns)
    return [
        (f'DROP TABLE IF EXISTS "{table}__new"', []),
        (f'CREATE TABLE "{table}__new" ({body})', []),
    ]


def swap_statements(table, indexes):
    statements = [
        (f'DROP TABLE IF EXISTS "{table}"', []),
        (f'ALTER TABLE "{table}__new" RENAME TO "{table}"', []),
    ]
    for column in indexes:
        statements.append(
            (f'CREATE INDEX IF NOT EXISTS "idx_{table}_{column}" ON "{table}"("{column}")', [])
        )
    return statements


def insert_statements(table, columns, rows):
    """INSERT multi-baris: setiap statement memuat sampai ROWS_PER_STATEMENT baris."""
    names = ", ".join(f'"{name}"' for name, _ in columns)
    row_marks = "(" + ", ".join("?" for _ in columns) + ")"
    rows = list(rows)
    statements = []
    for start in range(0, len(rows), ROWS_PER_STATEMENT):
        batch = rows[start : start + ROWS_PER_STATEMENT]
        sql = (
            f'INSERT INTO "{table}__new" ({names}) VALUES '
            + ", ".join([row_marks] * len(batch))
        )
        statements.append((sql, [value for row in batch for value in row]))
    return statements


# --- Publikasi ---
def publish_table(conn, client, table, select_sql, indexes, log=print):
    """Salin satu tabel ke Turso; kembalikan jumlah baris."""
    columns = column_definitions(conn, table, select_sql)
    client.execute(create_statements(table, columns))
    cursor = conn.cursor()
    cursor.execute(select_sql)
    total = 0
    while True:
        rows = cursor.fetchmany(CHUNK_ROWS)
        if not rows:
            break
        client.transaction(insert_statements(table, columns, rows))
        total += len(rows)
    client.transaction(swap_statements(table, indexes))
    log(f"   {table:28s} {total} baris")
    return total


def publish_all(client=None, tables=None, log=print, workers=WORKERS):
    """Terbitkan semua tabel di PUBLISH_TABLES; kembalikan total baris.

    Tabel independen satu sama lain (masing-masing punya tabel sementara dan
    ditukar sendiri), jadi disalin ``workers`` sekaligus. Bila ``client``
    diberikan (pengujian), semua tabel memakai klien itu secara berurutan.
    """
    database_url = os.environ.get("TURSO_DATABASE_URL")
    auth_token = os.environ.get("TURSO_AUTH_TOKEN")
    if client is None:
        TursoClient(database_url, auth_token)  # validasi kredensial lebih awal
    started_at = get_timestamp()
    items = list((tables or PUBLISH_TABLES).items())

    def publish_one(item):
        table, (select_sql, indexes) = item
        conn = get_connection()
        table_client = client or TursoClient(database_url, auth_token)
        try:
            return publish_table(conn, table_client, table, select_sql, indexes, log)
        except sqlite3.OperationalError as error:
            log(f"   {table:28s} dilewati ({error})")
            return 0
        finally:
            conn.close()

    if client is None and workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            total = sum(pool.map(publish_one, items))
    else:
        total = sum(publish_one(item) for item in items)

    conn = get_connection()
    record_run(conn, "publish_turso", started_at, total)
    conn.close()
    return total


def run():
    """Titik masuk: terbitkan ke Turso dan cetak ringkasan."""
    print("\n==================================================")
    print("   PUBLISH - TERBITKAN KE TURSO")
    print("==================================================")
    total = publish_all()
    print(f"\nSelesai: {total} baris diterbitkan.")


if __name__ == "__main__":
    run()
