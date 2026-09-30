"""Tes rantai incident dan keluarga jenis serangan di V0.5."""

import sqlite3

import pytest

from csais import v05_incident_clustering as v05


def _insert_incident(conn, incident_id, target, attack_type, first, last, anchor_text):
    conn.execute(
        """
        INSERT INTO v05_incidents (
            incident_id, attack_type, target, document_count, anchor_text,
            anchor_published_date, last_published_date, created_at, updated_at
        )
        VALUES (?, ?, ?, 1, ?, ?, ?, 'now', 'now')
        """,
        (incident_id, attack_type, target, anchor_text, first, last),
    )
    conn.execute(
        "INSERT INTO v05_incident_documents (incident_id, article_id, clustering_method) "
        "VALUES (?, ?, 'NEW_INCIDENT')",
        (incident_id, int(incident_id[-1])),
    )
    conn.execute(
        "INSERT INTO v05_processed_articles (article_id, incident_id, processed_at) "
        "VALUES (?, ?, 'now')",
        (int(incident_id[-1]), incident_id),
    )


@pytest.fixture
def conn(tmp_path, monkeypatch):
    connection = sqlite3.connect(tmp_path / "chain.db")
    v05.create_tables(connection)
    v05.migrate_existing_tables(connection)
    monkeypatch.setattr(v05, "_TOKEN_DF", {"canvas": 3, "coupang": 2})
    monkeypatch.setattr(v05, "_TARGET_DF_LIMIT", 20)
    yield connection
    connection.close()


def test_families():
    assert v05.attack_family_set("ransomware, data_leak") == {"BREACH"}
    assert v05.families_compatible("ransomware", "data_breach")
    assert v05.families_compatible(None, "phishing")
    assert not v05.families_compatible("phishing", "ddos")


def test_chain_merges_overlapping_incidents_with_same_target(conn):
    _insert_incident(conn, "INC_1", "canvas", "zero_day", "2026-05-07", "2026-05-20", "canvas hack")
    _insert_incident(conn, "INC_2", "canvas", "data_leak", "2026-05-08", "2026-05-26", "canvas leak")
    _insert_incident(conn, "INC_3", "coupang", "data_leak", "2026-05-08", "2026-05-09", "coupang")
    conn.commit()

    assert v05.chain_incidents(conn) == 1
    remaining = {row[0]: row[1] for row in conn.execute("SELECT incident_id, document_count FROM v05_incidents")}
    assert remaining == {"INC_1": 2, "INC_3": 1}
    docs = conn.execute("SELECT DISTINCT incident_id FROM v05_incident_documents").fetchall()
    assert sorted(d[0] for d in docs) == ["INC_1", "INC_3"]
    assert conn.execute("SELECT incident_id FROM v05_processed_articles WHERE article_id = 2").fetchone()[0] == "INC_1"


def test_chain_respects_gap_and_family_when_sequential(conn):
    # Berurutan (tidak tumpang tindih): keluarga harus cocok dan jarak <= CHAIN_GAP_DAYS
    _insert_incident(conn, "INC_1", "canvas", "phishing", "2026-01-01", "2026-01-05", "a")
    _insert_incident(conn, "INC_2", "canvas", "ddos", "2026-01-10", "2026-01-12", "b")
    _insert_incident(conn, "INC_3", "canvas", "ddos", "2026-04-01", "2026-04-02", "c")
    conn.commit()
    assert v05.chain_incidents(conn) == 0
    assert conn.execute("SELECT COUNT(*) FROM v05_incidents").fetchone()[0] == 3


def test_generic_attack_type_behaves_as_unknown():
    assert v05.attack_type_set("cyber_attack") == set()
    assert v05.attack_type_set("cyber_attack, ransomware") == {"ransomware"}
    assert v05.families_compatible("cyber_attack", "phishing")
    assert v05.prefer_specific_attack_type("cyber_attack", "ransomware") == "ransomware"
    assert v05.prefer_specific_attack_type("ransomware", "phishing") == "ransomware"
    assert v05.prefer_specific_attack_type(None, "cyber_attack") == "cyber_attack"


def test_judged_merges_union_and_head(temp_conn):
    """Keputusan LLM 'sama' digabung per kelompok; incident paling awal menjadi induk."""
    from csais import merge_judge

    v05.create_tables(temp_conn)
    for incident_id, date, docs in (("A", "2026-09-03", 2), ("B", "2026-09-01", 1), ("C", "2026-09-05", 3), ("D", "2026-09-04", 1)):
        temp_conn.execute(
            "INSERT INTO v05_incidents (incident_id, attack_type, document_count, anchor_text, anchor_published_date, last_published_date) VALUES (?, 'ransomware', ?, 'x', ?, ?)",
            (incident_id, docs, date, date),
        )
        for n in range(docs):
            temp_conn.execute("INSERT INTO v05_incident_documents (incident_id, article_id) VALUES (?, ?)", (incident_id, hash((incident_id, n)) % 100000))
    temp_conn.commit()
    rows = [("A", "B", 0.9), ("B", "C", 0.8), ("X", "D", 0.95)]  # X sudah tidak ada: dilewati
    assert merge_judge.apply_judged_merges(temp_conn, rows) == 2
    remaining = dict(temp_conn.execute("SELECT incident_id, document_count FROM v05_incidents").fetchall())
    assert remaining == {"B": 6, "D": 1}
    methods = {m for (m,) in temp_conn.execute("SELECT clustering_method FROM v05_incident_documents WHERE incident_id = 'B'")}
    assert merge_judge.METHOD in methods
    assert merge_judge.apply_judged_merges(temp_conn, rows) == 0  # A dan C sudah tidak ada


def test_merge_groups():
    from csais.merge_judge import merge_groups

    groups = sorted(sorted(g) for g in merge_groups([("a", "b"), ("c", "d"), ("b", "e")]))
    assert groups == [["a", "b", "e"], ["c", "d"]]
