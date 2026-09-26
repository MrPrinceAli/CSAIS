"""Migrasi skema ringan dan identitas deterministik.

- ``ensure_column``: tambah kolom bila belum ada (SQLite tidak punya
  ADD COLUMN IF NOT EXISTS).
- ``article_uid``: ID artikel yang sama di database mana pun, dihitung dari
  URL, sehingga bukti bisa dirujuk oleh sistem lain (ledger, laporan) tanpa
  bergantung pada nomor urut ``article_id``.
- ``pipeline_runs``: catatan setiap tahap yang dijalankan.
"""

import hashlib

from csais.db import get_timestamp
from csais.provenance import pipeline_stamp

UID_LENGTH = 24


def ensure_column(conn, table, column, definition="TEXT"):
    """Tambahkan kolom ke tabel bila belum ada; True bila ditambahkan."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    if column in {row[1] for row in cursor.fetchall()}:
        return False
    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    conn.commit()
    return True


def article_uid(article_url):
    """ID deterministik artikel: 24 heksadesimal pertama SHA-256 dari URL."""
    return hashlib.sha256((article_url or "").encode("utf-8")).hexdigest()[:UID_LENGTH]


def evidence_uid(incident_id, uid):
    """ID deterministik bukti: gabungan incident dan artikel."""
    raw = f"{incident_id}|{uid}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:UID_LENGTH]


def ensure_article_uid(conn):
    """Pastikan kolom articles.article_uid ada dan terisi; kembalikan jumlah yang diisi."""
    ensure_column(conn, "articles", "article_uid", "TEXT")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT article_id, article_url FROM articles WHERE article_uid IS NULL"
    )
    rows = cursor.fetchall()
    if rows:
        cursor.executemany(
            "UPDATE articles SET article_uid = ? WHERE article_id = ?",
            [(article_uid(url), article_id) for article_id, url in rows],
        )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_articles_uid ON articles(article_uid)"
    )
    conn.commit()
    return len(rows)


def ensure_content_columns(conn):
    """Kolom isi artikel penuh pada tabel articles (dipakai content_fetcher)."""
    for column, definition in (
        ("resolved_url", "TEXT"),
        ("content_status", "TEXT"),
        ("content_sha256", "TEXT"),
        ("content_fetched_at", "TEXT"),
        ("image_url", "TEXT"),  # og:image artikel, untuk kartu berita di web
    ):
        ensure_column(conn, "articles", column, definition)


def ensure_evidence_uids(conn):
    """Isi v06_evidence.evidence_uid untuk baris lama yang belum punya; kembalikan jumlahnya."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT e.evidence_id, e.incident_id, a.article_uid, e.article_id
        FROM v06_evidence e
        LEFT JOIN articles a ON a.article_id = e.article_id
        WHERE e.evidence_uid IS NULL
        """
    )
    rows = cursor.fetchall()
    if rows:
        cursor.executemany(
            "UPDATE v06_evidence SET evidence_uid = ? WHERE evidence_id = ?",
            [
                (evidence_uid(incident_id, uid or article_id), evidence_id)
                for evidence_id, incident_id, uid, article_id in rows
            ],
        )
        conn.commit()
    return len(rows)


def ensure_pipeline_runs(conn):
    """Buat tabel catatan run bila belum ada."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            stage TEXT NOT NULL,
            pipeline_version TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            rows_processed INTEGER,
            notes TEXT
        )
        """)
    conn.commit()


def record_run(conn, stage, started_at, rows_processed, notes=None):
    """Catat satu run tahap pipeline."""
    ensure_pipeline_runs(conn)
    conn.execute(
        """
        INSERT INTO pipeline_runs (
            stage, pipeline_version, started_at, finished_at, rows_processed, notes
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (stage, pipeline_stamp(), started_at, get_timestamp(), rows_processed, notes),
    )
    conn.commit()
