"""Pengujian csais/ledger.py: pohon Merkle, batch bukti, dan bukti Merkle."""

import hashlib
import json
import sqlite3

import pytest

from csais import ledger


def _leaves(n):
    return [ledger.leaf_hash(f'{{"i":{i}}}') for i in range(n)]


def test_leaf_and_node_hash_domains_are_separated():
    payload = '{"a":1}'
    assert ledger.leaf_hash(payload) == hashlib.sha256(b"\x00" + payload.encode()).digest()
    a, b = ledger.leaf_hash("x"), ledger.leaf_hash("y")
    assert ledger.node_hash(a, b) == ledger.node_hash(b, a)
    assert ledger.node_hash(a, b) == hashlib.sha256(b"\x01" + min(a, b) + max(a, b)).digest()


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 8, 13])
def test_every_leaf_has_a_valid_proof(n):
    leaves = _leaves(n)
    root = ledger.merkle_root(leaves)
    for index in range(n):
        proof = ledger.merkle_proof(leaves, index)
        assert ledger.verify_proof(leaves[index], proof, root)
        assert not ledger.verify_proof(ledger.leaf_hash("lain"), proof, root)
    if n == 1:
        assert root == leaves[0]


def test_root_is_deterministic_and_order_sensitive():
    leaves = _leaves(4)
    assert ledger.merkle_root(leaves) == ledger.merkle_root(list(leaves))
    # pasangan diurutkan, jadi pembalikan penuh menghasilkan akar yang sama;
    # pertukaran daun antar pasangan mengubahnya
    assert ledger.merkle_root(leaves) == ledger.merkle_root(leaves[::-1])
    assert ledger.merkle_root(leaves) != ledger.merkle_root([leaves[2], leaves[1], leaves[0], leaves[3]])
    with pytest.raises(ValueError):
        ledger.merkle_root([])


def test_known_vector_shared_with_web():
    """Vektor uji yang sama dipakai web/lib/merkle.test.mjs; bila berubah, ubah keduanya."""
    leaves = [ledger.leaf_hash(p) for p in ('{"a":1}', '{"b":2}', '{"c":3}')]
    assert leaves[0].hex() == "c7261463ebd776f4650b6d0fe942d9cc38c925d90f77d440ab6df8d5dd258c5f"
    assert ledger.merkle_root(leaves).hex() == "5ca2a520a34dd496e9f019d5b7134f0de3871de74f533a8b651edff02cb7b14a"
    assert [p.hex() for p in ledger.merkle_proof(leaves, 2)] == ["7673264e0014faa0f593a422cab882e1a572938819e2d7495c0cedae392a6729"]


def test_canonical_payload_is_sorted_compact_ascii():
    payload = ledger.canonical_payload(
        {"evidence_uid": "e", "incident_id": "i", "source_domain": "détik.com", "extra": 1}
    )
    data = json.loads(payload)
    assert list(data) == sorted(ledger.PAYLOAD_FIELDS)
    assert "extra" not in data
    assert " " not in payload and "\\u00e9" in payload
    assert data["content_sha256"] is None


def _seed(conn, count):
    conn.executescript("""
        CREATE TABLE articles (article_id INTEGER PRIMARY KEY, article_uid TEXT, article_url TEXT,
            resolved_url TEXT, content_sha256 TEXT, content_fetched_at TEXT);
        CREATE TABLE v06_evidence (evidence_id INTEGER PRIMARY KEY, evidence_uid TEXT,
            incident_id TEXT, article_id INTEGER, content_fingerprint TEXT,
            publication_date TEXT, source_domain TEXT, pipeline_version TEXT);
        CREATE TABLE pipeline_runs (run_id INTEGER PRIMARY KEY AUTOINCREMENT, stage TEXT,
            pipeline_version TEXT, started_at TEXT, finished_at TEXT, rows_processed INTEGER,
            notes TEXT);
    """)
    for i in range(count):
        conn.execute(
            "INSERT INTO articles VALUES (?, ?, ?, ?, ?, ?)",
            (i, f"uid{i}", f"https://g/{i}", f"https://m/{i}", f"{i:064x}", "2026-09-26"),
        )
        conn.execute(
            "INSERT INTO v06_evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (i + 1, f"ev{i}", "INC", i, f"fp{i}", "2026-09-25", "m", "0.7.0+x"),
        )
    conn.commit()


def test_batch_pending_chunks_and_is_append_only(temp_conn):
    _seed(temp_conn, 5)
    created = ledger.batch_pending(temp_conn, max_leaves=2)
    assert [count for _, _, count in created] == [2, 2, 1]
    assert ledger.pending_evidence(temp_conn) == []
    assert ledger.batch_pending(temp_conn, max_leaves=2) == []
    batches = temp_conn.execute(
        "SELECT batch_id, previous_root, merkle_root, leaf_count, anchor_status FROM evidence_batches ORDER BY batch_id"
    ).fetchall()
    assert batches[0][1] is None
    assert batches[1][1] == batches[0][2]  # rantai akar antar batch
    assert all(status == "PENDING" for *_, status in batches)
    # bukti baru masuk batch berikutnya; bukti lama tidak dihitung ulang
    temp_conn.execute("INSERT INTO articles VALUES (9, 'uid9', 'g9', 'm9', NULL, NULL)")
    temp_conn.execute(
        "INSERT INTO v06_evidence VALUES (99, 'ev9', 'INC', 9, 'fp9', '2026-09-26', 'm', '0.7.0+x')"
    )
    temp_conn.commit()
    created = ledger.batch_pending(temp_conn, max_leaves=2)
    assert len(created) == 1 and created[0][2] == 1
    assert ledger.ledger_summary(temp_conn) == (4, 6, 4)


def test_proof_for_returns_verifiable_proof_from_stored_leaves(temp_conn):
    _seed(temp_conn, 3)
    ledger.batch_pending(temp_conn)
    proof = ledger.proof_for(temp_conn, "ev1")
    assert proof["valid"] is True
    assert proof["batch_id"] == 1 and proof["leaf_index"] == 1 and proof["leaf_count"] == 3
    assert len(proof["proof"]) == 2
    assert ledger.leaf_hash(proof["payload"]).hex() == proof["leaf_hash"]
    assert json.loads(proof["payload"])["content_sha256"] == f"{1:064x}"
    assert proof["anchor_status"] == "PENDING" and proof["anchor_tx"] is None
    assert ledger.proof_for(temp_conn, "tidak-ada") is None


def test_run_records_pipeline_run(tmp_path, monkeypatch, capsys):
    db = tmp_path / "ledger.db"
    conn = sqlite3.connect(db)
    _seed(conn, 2)
    conn.close()
    monkeypatch.setattr(ledger, "get_connection", lambda: sqlite3.connect(db))
    ledger.run()
    out = capsys.readouterr().out
    assert "batch #1: 2 daun" in out
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT stage, rows_processed FROM pipeline_runs").fetchone() == (
        "ledger_batch", 2,
    )
    conn.close()
