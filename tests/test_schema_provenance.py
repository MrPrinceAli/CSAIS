"""Pengujian csais/schema.py dan csais/provenance.py: ID deterministik, migrasi, stamp versi."""

import os
import re

from csais import provenance, schema
from csais.config import DATABASE_DIR, DATABASE_FILE


def test_database_path_points_to_temporary_file():
    assert DATABASE_FILE == os.environ["CSAIS_DB_PATH"]
    assert not DATABASE_FILE.startswith(DATABASE_DIR)
    assert os.path.basename(DATABASE_FILE) != "csais.db"


def test_article_uid_deterministic_and_length():
    uid = schema.article_uid("https://example.com/a")
    assert uid == schema.article_uid("https://example.com/a")
    assert len(uid) == schema.UID_LENGTH == 24
    assert re.fullmatch(r"[0-9a-f]{24}", uid)
    assert uid != schema.article_uid("https://example.com/b")
    assert schema.article_uid(None) == schema.article_uid("")


def test_evidence_uid_combines_incident_and_article():
    uid = schema.evidence_uid("INCIDENT_A", "uid-1")
    assert re.fullmatch(r"[0-9a-f]{24}", uid)
    assert uid == schema.evidence_uid("INCIDENT_A", "uid-1")
    assert uid != schema.evidence_uid("INCIDENT_B", "uid-1")
    assert uid != schema.evidence_uid("INCIDENT_A", "uid-2")


def test_ensure_column_is_idempotent(temp_conn):
    temp_conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    assert schema.ensure_column(temp_conn, "t", "extra", "TEXT") is True
    assert schema.ensure_column(temp_conn, "t", "extra", "TEXT") is False
    columns = [row[1] for row in temp_conn.execute("PRAGMA table_info(t)")]
    assert columns == ["id", "extra"]


def test_ensure_article_uid_backfills_missing_rows(temp_conn):
    temp_conn.execute("CREATE TABLE articles (article_id INTEGER PRIMARY KEY, article_url TEXT)")
    temp_conn.executemany(
        "INSERT INTO articles (article_url) VALUES (?)", [("https://a",), ("https://b",)]
    )
    assert schema.ensure_article_uid(temp_conn) == 2
    rows = temp_conn.execute(
        "SELECT article_url, article_uid FROM articles ORDER BY article_id"
    ).fetchall()
    assert rows == [
        ("https://a", schema.article_uid("https://a")),
        ("https://b", schema.article_uid("https://b")),
    ]
    assert schema.ensure_article_uid(temp_conn) == 0
    temp_conn.execute("INSERT INTO articles (article_url) VALUES ('https://c')")
    assert schema.ensure_article_uid(temp_conn) == 1
    indexes = {row[1] for row in temp_conn.execute("PRAGMA index_list(articles)")}
    assert "idx_articles_uid" in indexes


def test_record_run_writes_pipeline_runs(temp_conn):
    schema.record_run(
        temp_conn, "v04_entity_resolution", "2025-01-01T00:00:00+00:00", 12, notes="uji"
    )
    rows = temp_conn.execute(
        "SELECT stage, pipeline_version, started_at, finished_at, rows_processed, notes "
        "FROM pipeline_runs"
    ).fetchall()
    assert len(rows) == 1
    stage, version, started, finished, processed, notes = rows[0]
    assert (stage, started, processed, notes) == (
        "v04_entity_resolution", "2025-01-01T00:00:00+00:00", 12, "uji",
    )
    assert version == provenance.pipeline_stamp()
    assert finished >= started


def test_pipeline_stamp_format():
    stamp = provenance.pipeline_stamp()
    assert re.fullmatch(r"\d+\.\d+\.\d+\+[0-9a-f]{12}", stamp)
    assert stamp.startswith(provenance.PIPELINE_VERSION + "+")
    assert stamp == provenance.pipeline_stamp()  # sidik jari di-cache dalam satu proses
    assert provenance.code_fingerprint() == stamp.split("+", 1)[1]
