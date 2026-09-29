"""Uji alur D2: keputusan per kolom, kartu lama, dan pencatatan snapshot."""

import json
import sqlite3

import pytest

from csais import flows, survey
from test_flows import _latest, _pipeline_tables


@pytest.mark.parametrize(
    "counts, verdict",
    [
        ({"sesuai": 3}, "sesuai"),
        ({"sesuai": 2, "tidak_tahu": 5}, "belum"),  # tidak tahu tidak ikut menentukan
        ({"sesuai": 2, "tidak_sesuai": 1}, "sesuai"),
        ({"sesuai": 2, "tidak_sesuai": 2}, "belum"),
        ({"tidak_sesuai": 4, "sesuai": 1}, "tidak_sesuai"),
    ],
)
def test_decide(counts, verdict):
    assert survey.decide(counts) == verdict


def _answers(incident_id, field, shown, answer, n, start=0):
    return [(incident_id, field, shown, answer, f"r{start + i}") for i in range(n)]


def test_record_d2(temp_conn):
    _pipeline_tables(temp_conn)
    flows.record_d1(temp_conn)
    responses = (
        _answers("INC-A", "target", "Bank X", "sesuai", 3)
        + _answers("INC-A", "attack_type", "phishing", "sesuai", 2)
        + _answers("INC-A", "target", "Bank Lama", "tidak_sesuai", 4)  # kartu lama, diabaikan
        + _answers("INC-B", "threat_actor", "LockBit", "tidak_sesuai", 3)
        + _answers("INC-X", "target", "?", "sesuai", 3)  # incident tidak dikenal
    )
    assert survey.record_d2(temp_conn, responses) == (2, 2)
    a = _latest(temp_conn, "INC-A", "D2")
    assert (a["status"], a["tier"], a["target"]) == ("sesuai", "waspada", "Bank X")
    assert json.loads(a["field_status"]) == {"target": "sesuai", "attack_type": "belum"}
    basis = json.loads(a["basis"])
    assert (basis["responses"], basis["ignored_old_card"], basis["respondents"]) == (5, 4, 3)
    assert json.loads(a["prevention"])["steps"][0] == "group:BANK_CUSTOMERS"
    b = _latest(temp_conn, "INC-B", "D2")
    assert (b["status"], b["tier"], b["prevention"]) == ("tidak_sesuai", None, None)
    # tanpa jawaban baru tidak ada snapshot baru; jawaban baru mengubah hitungan
    assert survey.record_d2(temp_conn, responses) == (0, 2)
    more = responses + _answers("INC-A", "attack_type", "phishing", "sesuai", 1, start=9)
    assert survey.record_d2(temp_conn, more) == (1, 2)
    assert json.loads(_latest(temp_conn, "INC-A", "D2")["field_status"])["attack_type"] == "sesuai"


def test_pending_when_not_enough(temp_conn):
    _pipeline_tables(temp_conn)
    flows.record_d1(temp_conn)
    survey.record_d2(temp_conn, _answers("INC-A", "target", "Bank X", "sesuai", 1))
    assert _latest(temp_conn, "INC-A", "D2")["status"] == flows.PENDING


def test_fetch_from_file(tmp_path, monkeypatch):
    path = tmp_path / "survey.db"
    monkeypatch.setenv("SURVEY_DATABASE_URL", f"file:{path}")
    assert survey.fetch_responses() == []  # tabel belum ada
    conn = sqlite3.connect(path)
    conn.execute(survey.SURVEY_SCHEMA)
    conn.execute(
        "INSERT INTO survey_responses (submission_id, incident_id, card_output_id, field, shown_value,"
        " answer, respondent, created_at) VALUES ('s1', 'INC-A', 1, 'target', NULL, 'sesuai', 'r1', 't')"
    )
    conn.commit()
    conn.close()
    assert survey.fetch_responses() == [("INC-A", "target", None, "sesuai", "r1")]
    monkeypatch.delenv("SURVEY_DATABASE_URL")
    assert survey.fetch_responses() is None
