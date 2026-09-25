"""Koneksi SQLite dan timestamp yang dipakai bersama oleh seluruh modul."""

import sqlite3
from datetime import datetime, timezone

from csais.config import DATABASE_FILE


def get_connection(db_path=None):
    """Buka koneksi SQLite dengan pengaturan yang sama untuk semua modul."""
    conn = sqlite3.connect(db_path or DATABASE_FILE)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def get_timestamp():
    """Waktu sekarang dalam UTC, format ISO 8601."""
    return datetime.now(timezone.utc).isoformat()
