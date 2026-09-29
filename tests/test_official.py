"""Uji alur D3/D4 (pernyataan lembaga), batch ledger D4, dan tabel flow_metrics."""

import csv
import json

from csais import flow_compare, flows, ledger, official
from test_flows import _latest, _pipeline_tables

BASE = {
    "statement_id": "OJK-001", "incident_id": "INC-A", "institution": "OJK", "status": "dikonfirmasi",
    "statement_date": "2026-09-12", "source_url": "https://ojk.go.id/siaran-pers/1",
    "reason": "OJK mengonfirmasi phishing yang menyasar nasabah Bank Y.",
    "target": "Bank Y", "prevention_text": "Jangan bagikan OTP.", "prevention_keys": "type:phishing:1",
}


def _write(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=official.COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in official.COLUMNS})


def test_load_statements_validation(tmp_path):
    path = tmp_path / "s.csv"
    _write(path, [
        BASE,
        {**BASE},  # statement_id ganda
        {**BASE, "statement_id": "X-2", "status": "mungkin"},
        {**BASE, "statement_id": "X-3", "source_url": "ojk.go.id"},
        {**BASE, "statement_id": "X-4", "statement_date": "12/09/2026"},
    ])
    rows, errors = official.load_statements(path)
    assert [r["statement_id"] for r in rows] == ["OJK-001"]
    assert len(errors) == 4 and errors[0].startswith("baris 3")
    assert official.load_statements(tmp_path / "tidak-ada.csv") == ([], [])


def test_d3_and_d4(temp_conn):
    _pipeline_tables(temp_conn)
    flows.record_d1(temp_conn)
    rows = [BASE, {**BASE, "statement_id": "POL-1", "incident_id": "INC-B", "institution": "Polri",
                   "status": "dibantah", "target": "", "reason": "Hoaks.", "prevention_keys": ""},
            {**BASE, "statement_id": "BSSN-9", "incident_id": "INC-Z"}]
    assert official.record_official(temp_conn, rows) == (2, 2, ["INC-Z"])

    d3 = _latest(temp_conn, "INC-A", "D3")
    assert (d3["status"], d3["target"], d3["attack_type"]) == ("dikonfirmasi", "Bank Y", "phishing")
    assert json.loads(d3["field_status"]) == {"target": "dibantah"}  # kartu mesin menyebut Bank X
    assert json.loads(d3["basis"])["institutions"] == ["OJK"]
    d4 = _latest(temp_conn, "INC-A", "D4")
    assert (d4["tier"], d4["reason"], d4["supersedes"]) == ("rekomendasi_resmi", BASE["reason"], None)
    assert json.loads(d4["prevention"]) == {"steps": ["type:phishing:1"], "text": "Jangan bagikan OTP."}
    assert _latest(temp_conn, "INC-B", "D4")["tier"] == "peringatan_hoaks"

    # run ulang tanpa perubahan: tidak ada baris baru
    assert official.record_official(temp_conn, rows) == (0, 0, ["INC-Z"])
    # revisi lembaga: baris D4 baru merujuk baris lama
    revised = rows + [{**BASE, "statement_id": "OJK-002", "statement_date": "2026-09-20", "reason": "Revisi: korban dua bank."}]
    first_id = d4["output_id"]
    assert official.record_official(temp_conn, revised)[:2] == (1, 1)
    latest = _latest(temp_conn, "INC-A", "D4")
    assert latest["supersedes"] == first_id
    assert official.record_official(temp_conn, revised)[:2] == (0, 0)


def test_partial_statement_has_no_d4(temp_conn):
    _pipeline_tables(temp_conn)
    flows.record_d1(temp_conn)
    assert official.record_official(temp_conn, [{**BASE, "status": "sebagian"}])[:2] == (1, 0)
    assert official.record_official(temp_conn, [{**BASE, "reason": None}])[:2] == (1, 0)  # D4 butuh alasan


def test_d4_records_enter_ledger(temp_conn):
    _pipeline_tables(temp_conn)
    flows.record_d1(temp_conn)
    official.record_official(temp_conn, [BASE])
    temp_conn.executescript("""
        CREATE TABLE v06_evidence (evidence_id INTEGER, evidence_uid TEXT, incident_id TEXT, article_id INTEGER,
            content_fingerprint TEXT, publication_date TEXT, source_domain TEXT, pipeline_version TEXT);
        ALTER TABLE articles ADD COLUMN article_uid TEXT;
        ALTER TABLE articles ADD COLUMN article_url TEXT;
        ALTER TABLE articles ADD COLUMN resolved_url TEXT;
        ALTER TABLE articles ADD COLUMN content_sha256 TEXT;
        ALTER TABLE articles ADD COLUMN content_fetched_at TEXT;
        """)  # tanpa bukti V0.6: hanya catatan D4 yang dibatch
    created = ledger.batch_pending(temp_conn)
    assert [count for _, _, count in created] == [1]
    kind, uid, payload = temp_conn.execute(
        "SELECT b.batch_kind, l.evidence_uid, l.payload FROM evidence_leaves l JOIN evidence_batches b USING (batch_id)"
    ).fetchone()
    d4 = _latest(temp_conn, "INC-A", "D4")
    assert kind == ledger.OFFICIAL_RECORD
    assert uid == ledger.record_uid(d4["output_id"], d4["output_hash"])
    assert json.loads(payload)["output_hash"] == d4["output_hash"]
    proof = ledger.proof_for(temp_conn, uid)
    assert proof["valid"]
    assert ledger.batch_pending(temp_conn) == []  # tidak dibatch dua kali


def test_candidates(temp_conn):
    _pipeline_tables(temp_conn)
    temp_conn.executescript("""
        ALTER TABLE articles ADD COLUMN title TEXT;
        ALTER TABLE articles ADD COLUMN article_url TEXT;
        ALTER TABLE articles ADD COLUMN resolved_url TEXT;
        ALTER TABLE articles ADD COLUMN source_type TEXT;
        UPDATE articles SET title = 'OJK minta nasabah waspada phishing', article_url = 'https://x/1' WHERE article_id = 1;
        UPDATE articles SET title = 'FBI warns about LockBit', article_url = 'https://x/3' WHERE article_id = 3;
        """)
    flows.record_d1(temp_conn)
    rows = official.candidates(temp_conn)
    assert [(r["incident_id"], r["institution"]) for r in rows] == [("INC-A", "OJK")]


def test_store_metrics(temp_conn):
    _pipeline_tables(temp_conn)
    flows.record_d1(temp_conn)
    metrics = flow_compare.compute(temp_conn)
    flow_compare.store_metrics(temp_conn, metrics, "2026-09-29T00:00:00+00:00")
    stored = temp_conn.execute("SELECT value FROM flow_metrics WHERE metric = 'cakupan' AND flow = 'D1'").fetchone()
    assert stored == (2,)


# --- Keputusan dari portal lembaga ---
REVIEW = (7, "INC-A", "OJK", "dikonfirmasi", "ditangani", "Sudah diblokir.",
          '{"target": "dibantah", "attack_type": "dikonfirmasi", "tidak_dikenal": "dibantah"}',
          None, "Rina", "2026-09-29T08:00:00+00:00")


def test_review_rows_mapping():
    row = official.review_rows([REVIEW, (8, "INC-A", "OJK", "mungkin", "x", None, None, None, None, "t")])
    assert len(row) == 1  # status tidak dikenal dilewati
    row = row[0]
    assert (row["statement_id"], row["institution"], row["source_url"]) == ("portal-7", "OJK", "portal:OJK:7")
    assert row["reason"] == "Sudah ditangani atau diproses lembaga. Sudah diblokir."
    assert row["field_status"] == {"target": "dibantah", "attack_type": "dikonfirmasi"}
    assert official.review_rows([(9, "INC-B", "POLRI", "dibantah", "hoaks", None, None, "https://x.id/a", None, "t")])[0]["institution"] == "Siber Polri"


def test_portal_review_becomes_d3_and_d4(temp_conn):
    _pipeline_tables(temp_conn)
    flows.record_d1(temp_conn)
    assert official.record_official(temp_conn, official.review_rows([REVIEW]))[:2] == (1, 1)
    d3 = _latest(temp_conn, "INC-A", "D3")
    assert json.loads(d3["field_status"]) == {"target": "dibantah", "attack_type": "dikonfirmasi"}
    assert d3["target"] == "Bank X"  # nilai kartu tetap, penilaiannya dibantah
    d4 = _latest(temp_conn, "INC-A", "D4")
    assert (d4["tier"], d4["source_ref"]) == ("rekomendasi_resmi", "portal:OJK:7")
    # metrik: target mesin dinilai salah oleh lembaga walaupun nilainya sama dengan kartu
    metrics = flow_compare.compute(temp_conn)
    recall = next(m for m in metrics if (m["metric"], m["field"]) == ("ketepatan_recall", "target"))
    assert (recall["value"], recall["n"]) == (0.0, 1)
    ok = next(m for m in metrics if (m["metric"], m["field"]) == ("ketepatan_recall", "attack_type"))
    assert ok["value"] == 1.0


def test_load_reviews_from_file(tmp_path, monkeypatch):
    import sqlite3
    path = tmp_path / "survey.db"
    conn = sqlite3.connect(path)
    conn.execute(official.REVIEWS_SCHEMA)
    conn.execute(
        "INSERT INTO official_reviews (incident_id, card_output_id, institution, status, reason_code, field_status, created_at, signed)"
        " VALUES ('INC-A', 1, 'BSSN', 'dibantah', 'hoaks', '{}', 't', '{\"signer\": \"0xabc\", \"signature\": \"0x01\"}')"
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("SURVEY_DATABASE_URL", f"file:{path}")
    reviews = official.load_reviews()
    assert [r["statement_id"] for r in reviews] == ["portal-1"]
    assert reviews[0]["signed"] == {"signer": "0xabc", "signature": "0x01"}
    monkeypatch.delenv("SURVEY_DATABASE_URL")
    assert official.load_reviews() == []


def test_signature_travels_into_d4(temp_conn):
    _pipeline_tables(temp_conn)
    flows.record_d1(temp_conn)
    signed = {"signer": "0xOJK", "signature": "0xsig", "message": {"institution": "OJK"}}
    review = REVIEW + (json.dumps(signed),)
    official.record_official(temp_conn, official.review_rows([review]))
    basis = json.loads(_latest(temp_conn, "INC-A", "D4")["basis"])
    assert basis["signed"] == signed
