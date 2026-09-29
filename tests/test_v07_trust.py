"""Pengujian csais/v07_trust_score.py: rumus skor dan perhitungan dari database."""

import json
import sqlite3

import pytest

from csais import v07_trust_score as v07


def test_score_incident_matches_web_formula():
    # domains 3 -> corroboration 0.5; independence 0.8; claim 0.9; content 0.5; clustering 0.7
    result = v07.score_incident(0.8, 3, 4, 0.9, 0.5, 0.7)
    expected = 0.5 * 0.3 + 0.8 * 0.3 + 0.9 * 0.2 + 0.5 * 0.1 + 0.7 * 0.1
    assert result["score"] == round(expected, 4)
    assert result["level"] == "sedang"
    assert result["parts"]["corroboration"] == 0.5


def test_single_article_uses_fixed_independence_and_clamps():
    result = v07.score_incident(None, 1, 1, 1.5, -0.2, 2.0)
    assert result["parts"]["independence"] == v07.SINGLE_SOURCE_INDEPENDENCE
    assert result["parts"]["corroboration"] == 0.0
    assert result["parts"]["claim"] == 1.0
    assert result["parts"]["content"] == 0.0
    assert result["parts"]["clustering"] == 1.0


def test_multi_article_without_evidence_scores_zero_independence():
    assert v07.score_incident(None, 2, 2, 0, 0, 0)["parts"]["independence"] == 0.0


@pytest.mark.parametrize(
    "score,level",
    [(0.72, "tinggi"), (0.719, "sedang"), (0.45, "sedang"), (0.449, "rendah")],
)
def test_levels(score, level, monkeypatch):
    # Bangun masukan yang menghasilkan skor persis: semua sinyal = score
    result = v07.score_incident(score, 1 + 4 * score, 2, score, score, score)
    assert abs(result["score"] - score) < 1e-9
    assert result["level"] == level


def _seed(conn):
    conn.executescript("""
        CREATE TABLE articles (article_id INTEGER PRIMARY KEY, resolved_url TEXT, article_url TEXT,
            source_name TEXT, content_status TEXT, title TEXT);
        CREATE TABLE v05_incidents (incident_id TEXT PRIMARY KEY, incident_confidence REAL);
        CREATE TABLE v05_incident_documents (incident_id TEXT, article_id INTEGER);
        CREATE TABLE v06_evidence (incident_id TEXT, article_id INTEGER, source_domain TEXT,
            evidence_independence_score REAL);
        CREATE TABLE v03_information_extraction (article_id INTEGER PRIMARY KEY, target TEXT,
            field_confidence TEXT);
        INSERT INTO articles VALUES (1, 'https://a.com/x', 'g1', 'A', 'ok', NULL);
        INSERT INTO articles VALUES (2, NULL, 'https://www.b.com/y', 'B', 'error', NULL);
        INSERT INTO articles VALUES (3, NULL, NULL, 'C Media', NULL, NULL);
        INSERT INTO v05_incidents VALUES ('INC1', 0.9);
        INSERT INTO v05_incidents VALUES ('INC2', 0.4);
        INSERT INTO v05_incident_documents VALUES ('INC1', 1);
        INSERT INTO v05_incident_documents VALUES ('INC1', 2);
        INSERT INTO v05_incident_documents VALUES ('INC2', 3);
        INSERT INTO v06_evidence VALUES ('INC1', 1, 'a.com', 0.8);
        INSERT INTO v06_evidence VALUES ('INC1', 2, NULL, 0.6);
        INSERT INTO v03_information_extraction VALUES (1, 'Acme', '{"target": 0.9}');
        INSERT INTO v03_information_extraction VALUES (2, 'UNKNOWN', '{"target": 0.0}');
        INSERT INTO v03_information_extraction VALUES (3, 'Zed', 'rusak');
    """)
    conn.commit()


def test_compute_all_writes_one_row_per_incident(temp_conn, monkeypatch):
    _seed(temp_conn)
    monkeypatch.setattr(v07, "pipeline_stamp", lambda: "0.0.0+test")
    assert v07.compute_all(temp_conn) == 2
    rows = {
        row[0]: row
        for row in temp_conn.execute(
            "SELECT incident_id, score, level, corroboration, independence, claim, content, "
            "clustering, document_count, domain_count, pipeline_version FROM v07_trust"
        )
    }
    inc1 = rows["INC1"]
    assert inc1[8] == 2 and inc1[9] == 2  # a.com dan b.com (fallback dari URL, tanpa www.)
    assert inc1[3] == 0.25  # (2 - 1) / 4
    assert inc1[4] == 0.7  # rata-rata 0.8 dan 0.6
    assert inc1[5] == 0.9 and inc1[6] == 0.5 and inc1[7] == 0.9
    assert inc1[10] == "0.0.0+test"
    inc2 = rows["INC2"]
    assert inc2[8] == 1 and inc2[9] == 1  # domain dari source_name
    assert inc2[4] == v07.SINGLE_SOURCE_INDEPENDENCE
    assert inc2[5] == 0.0  # field_confidence rusak -> 0
    assert inc2[2] == "rendah"


def test_compute_all_is_idempotent_and_drops_stale_incidents(temp_conn):
    _seed(temp_conn)
    v07.compute_all(temp_conn)
    temp_conn.execute("DELETE FROM v05_incidents WHERE incident_id = 'INC2'")
    temp_conn.commit()
    assert v07.compute_all(temp_conn) == 1
    assert [r[0] for r in temp_conn.execute("SELECT incident_id FROM v07_trust")] == ["INC1"]


def test_google_news_links_count_publishers(temp_conn):
    """Tautan Google News dihitung per penerbit (akhiran judul), bukan satu domain news.google.com."""
    from csais.sources import source_identity

    g = "https://news.google.com/rss/articles/abc"
    publishers = {"reuters": "reuters.com"}
    assert source_identity(g, "Bank X diserang - Reuters", publishers) == "reuters.com"
    assert source_identity(g, "Bank X diserang - Kompas.com", publishers) == "penerbit:kompas.com"
    assert source_identity("https://www.detik.com/a", "Judul - Reuters", publishers) == "detik.com"
    assert source_identity(g, "Tanpa penerbit", publishers) == "news.google.com"
    rows = [
        ("I", "ok", "news.google.com", g, "A - Reuters", "Google News", 0.8, None, None),
        ("I", None, "news.google.com", g, "B - Kompas.com", "Google News", 0.8, None, None),
        ("I", None, "news.google.com", g, "C - Kompas.com", "Google News", 0.8, None, None),
    ]
    assert v07.incident_inputs(rows, publishers)["domains"] == 2
