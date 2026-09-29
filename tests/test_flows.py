"""Uji alur D1 - D4: aturan pencegahan, snapshot D1, dan perbandingan laporan."""

import json
import os
import sys
from datetime import datetime, timezone

import pytest

from csais import flows, v07_trust_score

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eval"))
import compare_flows  # noqa: E402


# --- Pencegahan (harus sama dengan web/lib/prevention.ts) ---
@pytest.mark.parametrize(
    "group, types, steps, channels",
    [
        ("BANK_CUSTOMERS", ["phishing"], ["group:BANK_CUSTOMERS", "type:phishing:0", "type:phishing:1"], ["ojk", "konten", "patrol"]),
        ("", ["data_leak"], ["type:data_breach:0", "type:data_breach:1"], ["patrol"]),
        ("", [], ["type:cyber_attack:0", "type:cyber_attack:1"], ["patrol"]),
        ("ELDERLY", ["ddos"], ["group:ELDERLY", "type:ddos:0"], ["rekening", "patrol"]),
        ("INDIVIDUALS", ["investment_scam", "phishing"], ["group:INDIVIDUALS", "type:investment_scam:0", "type:investment_scam:1"], ["ojk", "rekening", "konten", "patrol"]),
    ],
)
def test_prevention_for(group, types, steps, channels):
    assert flows.prevention_for(group, types) == {"steps": steps, "channels": channels}


def test_prevention_keys_resolve_to_text():
    for key in flows.prevention_for("STUDENTS", ["ransomware"])["steps"]:
        kind, name, *index = key.split(":")
        source = flows.PREVENTION["by_group"][name] if kind == "group" else flows.PREVENTION["by_type"][name][int(index[0])]
        assert source["id"] and source["en"]


# --- Snapshot D1 ---
def _pipeline_tables(conn):
    conn.executescript("""
        CREATE TABLE v05_incidents (incident_id TEXT PRIMARY KEY, attack_type TEXT, target TEXT,
            threat_actor TEXT, attack_date TEXT, location TEXT, document_count INTEGER);
        CREATE TABLE v05_incident_documents (incident_id TEXT, article_id INTEGER);
        CREATE TABLE v03_information_extraction (article_id INTEGER PRIMARY KEY, target_group TEXT);
        CREATE TABLE articles (article_id INTEGER PRIMARY KEY, published_date TEXT);
        INSERT INTO v05_incidents VALUES
            ('INC-A', 'phishing', 'Bank X', 'UNKNOWN', '2026-09-10', 'indonesia', 2),
            ('INC-B', 'ransomware', 'UNKNOWN', 'LockBit', NULL, '', 1);
        INSERT INTO v05_incident_documents VALUES ('INC-A', 1), ('INC-A', 2), ('INC-B', 3);
        INSERT INTO v03_information_extraction VALUES
            (1, 'BANK_CUSTOMERS, INDIVIDUALS'), (2, 'BANK_CUSTOMERS'), (3, 'UNKNOWN');
        INSERT INTO articles VALUES (1, '2026-09-10T01:00:00+00:00'),
            (2, '2026-09-10T05:00:00+00:00'), (3, '2026-09-11T00:00:00+00:00');
        """)
    v07_trust_score.create_tables(conn)
    conn.execute(
        "INSERT INTO v07_trust (incident_id, score, level, corroboration, independence, claim, content, clustering, document_count, domain_count, pipeline_version, computed_at) VALUES ('INC-A', 0.5, 'sedang', 0, 0, 0, 0, 0, 2, 2, 'v', 't')"
    )
    conn.commit()


def _latest(conn, incident_id, flow="D1"):
    conn.row_factory = None
    cursor = conn.execute(
        "SELECT * FROM flow_outputs WHERE incident_id = ? AND flow = ? ORDER BY output_id DESC LIMIT 1",
        (incident_id, flow),
    )
    names = [d[0] for d in cursor.description]
    return dict(zip(names, cursor.fetchone()))


def test_record_d1_values(temp_conn):
    _pipeline_tables(temp_conn)
    assert flows.record_d1(temp_conn) == (2, 0, 2)
    a = _latest(temp_conn, "INC-A")
    assert (a["target"], a["threat_actor"], a["target_group"], a["status"], a["tier"]) == (
        "Bank X", None, "BANK_CUSTOMERS", "sedang", "peringatan_dini",
    )
    assert json.loads(a["prevention"])["steps"][0] == "group:BANK_CUSTOMERS"
    assert json.loads(a["basis"]) == {"documents": 2, "domains": 2, "trust_score": 0.5}
    b = _latest(temp_conn, "INC-B")
    assert (b["target"], b["location"], b["target_group"], b["status"]) == (None, None, None, "tanpa_skor")


def test_record_d1_only_changes(temp_conn):
    _pipeline_tables(temp_conn)
    flows.record_d1(temp_conn)
    assert flows.record_d1(temp_conn) == (0, 0, 2)
    temp_conn.execute("UPDATE v05_incidents SET threat_actor = 'Scattered Spider' WHERE incident_id = 'INC-A'")
    assert flows.record_d1(temp_conn) == (1, 0, 2)
    assert _latest(temp_conn, "INC-A")["threat_actor"] == "Scattered Spider"
    temp_conn.execute("DELETE FROM v05_incidents WHERE incident_id = 'INC-B'")
    assert flows.record_d1(temp_conn) == (0, 1, 1)
    assert _latest(temp_conn, "INC-B")["status"] == flows.REMOVED
    assert flows.record_d1(temp_conn) == (0, 0, 1)  # tanda dihapus tidak diulang
    assert flows.flow_summary(temp_conn)["D1"] == 1


def test_record_output_rejects_unknown_values(temp_conn):
    flows.create_tables(temp_conn)
    with pytest.raises(ValueError):
        flows.record_output(temp_conn, "INC-A", "D5", {"status": "x"})
    with pytest.raises(ValueError):
        flows.record_output(temp_conn, "INC-A", "D2", {"status": "x", "tier": "entah"})


# --- Perbandingan ---
def _flows_fixture(conn):
    _pipeline_tables(conn)
    flows.record_d1(conn, recorded_at="2026-09-09T00:00:00+00:00")  # sebelum artikel: latensi 0
    card = {"attack_type": "phishing", "target": "Bank X", "threat_actor": None}
    flows.record_output(conn, "INC-A", "D2", {
        **card, "status": "sesuai", "tier": "waspada",
        "field_status": {"attack_type": "sesuai", "target": "sesuai"},
    }, recorded_at="2026-09-10T11:00:00+00:00")
    flows.record_output(conn, "INC-A", "D3", {
        **card, "status": "dikonfirmasi",
        "field_status": {"attack_type": "dikonfirmasi", "target": "dibantah"},
    }, recorded_at="2026-09-12T01:00:00+00:00")
    flows.record_output(conn, "INC-A", "D4", {
        "attack_type": "phishing", "target": "Bank Y", "status": "dikonfirmasi",
        "tier": "rekomendasi_resmi", "reason": "Pernyataan resmi OJK",
        "prevention": {"steps": ["group:BANK_CUSTOMERS", "type:phishing:0", "type:online_scam:1"]},
    }, recorded_at="2026-09-12T02:00:00+00:00")
    flows.record_output(conn, "INC-B", "D2", {"status": "sesuai", "tier": "waspada"}, recorded_at="2026-09-11T02:00:00+00:00")
    flows.record_output(conn, "INC-B", "D4", {"status": "dibantah", "tier": "peringatan_hoaks"}, recorded_at="2026-09-13T00:00:00+00:00")
    conn.commit()


def _metric(metrics, name, flow, field=""):
    return next(m for m in metrics if (m["metric"], m["flow"], m["field"]) == (name, flow, field))


def test_compare_flows_metrics(temp_conn):
    _flows_fixture(temp_conn)
    as_of = datetime(2026, 9, 30, tzinfo=timezone.utc)
    latest, first = compare_flows.load_latest(temp_conn, as_of)
    temp_conn.row_factory = None
    metrics = compare_flows.compare(latest, first, compare_flows.first_seen(temp_conn))

    assert _metric(metrics, "cakupan", "D4")["value"] == 2
    assert _metric(metrics, "cakupan_porsi", "D2")["value"] == 1.0
    assert _metric(metrics, "kecepatan_median_jam", "D2")["value"] == pytest.approx(6.0)  # median dari A 10 jam dan B 2 jam
    # D1 benar di attack_type, salah di target (Bank X vs Bank Y)
    assert _metric(metrics, "ketepatan_recall", "D1", "attack_type")["value"] == 1.0
    assert _metric(metrics, "ketepatan_precision", "D1", "target")["value"] == 0.0
    # publik menilai target "sesuai" padahal salah; lembaga membantahnya dengan benar
    assert _metric(metrics, "penilaian_tepat", "D2", "target")["value"] == 0.0
    assert _metric(metrics, "penilaian_tepat", "D3", "target")["value"] == 1.0
    assert _metric(metrics, "kesepakatan_d2_d3", "D2-D3", "target")["value"] == 0.0
    assert _metric(metrics, "hoaks_dibantah_d4", "D4")["value"] == 1
    assert _metric(metrics, "hoaks_lolos_publik", "D2")["value"] == 1
    assert _metric(metrics, "hoaks_lolos_mesin", "D1")["value"] == 0  # INC-B tanpa skor
    jaccard = _metric(metrics, "preventif_jaccard_d1_d4", "D1-D4")
    assert jaccard["n"] == 1 and jaccard["value"] == pytest.approx(2 / 4)
    assert _metric(metrics, "preventif_d4_menambah", "D4")["value"] == 1.0


def test_compare_flows_as_of_hides_later_rows(temp_conn):
    _flows_fixture(temp_conn)
    latest, _ = compare_flows.load_latest(temp_conn, datetime(2026, 9, 11, 12, tzinfo=timezone.utc))
    assert set(latest["D2"]) == {"INC-A", "INC-B"}
    assert latest["D3"] == {} and latest["D4"] == {}


def test_cohen_kappa():
    assert compare_flows.cohen_kappa([(True, True), (False, False)]) == 1.0
    assert compare_flows.cohen_kappa([(True, True), (True, True)]) is None
    assert compare_flows.cohen_kappa([]) is None


def test_d1_splits_attack_type_list(temp_conn):
    _pipeline_tables(temp_conn)
    temp_conn.execute("UPDATE v05_incidents SET attack_type = 'ransomware, data_leak' WHERE incident_id = 'INC-B'")
    flows.record_d1(temp_conn)
    steps = json.loads(_latest(temp_conn, "INC-B")["prevention"])["steps"]
    assert steps == ["type:ransomware:0", "type:ransomware:1", "type:data_breach:0"]
    assert compare_flows.same_value("attack_type", "ransomware, data_leak", "Data_Leak")
    assert not compare_flows.same_value("attack_type", "ransomware", "phishing")
