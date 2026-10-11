"""Uji saran AI D1 - D4 dan Peta Literasi dengan model tiruan (tanpa jaringan)."""

import json

from csais import ai_prevention, flows, official, survey
from test_flows import _pipeline_tables
from test_official import REVIEW


class FakeModel:
    """Meniru LLMClient.chat_json; mencatat masukan tiap permintaan."""

    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on

    def chat_json(self, system, user, schema, name="x", temperature=0.0, max_tokens=800):
        self.calls.append(user)
        if self.fail_on and self.fail_on in user:
            raise ai_prevention.LLMError("gagal tiruan")
        return {
            "ringkasan": "Relevan untuk Indonesia.",
            "sasaran": [{"kelompok": "Nasabah Bank X pengguna m-banking", "usia": "", "wilayah": "", "alasan": "korban langsung"}, {"kelompok": ""}] + [{"kelompok": f"k{i}"} for i in range(5)],
            "materi": ["Mengenali SMS palsu", " ", "Verifikasi dua langkah"],
            "langkah": ["Ganti kata sandi"],
            "kanal": ["patrolisiber.id"],
            "pesan_kunci": "Jangan bagikan OTP.",
        }, {}


def _setup(conn):
    _pipeline_tables(conn)
    # kolom yang dibaca tahap AI tetapi tidak ada di tabel uji ringkas
    conn.execute("ALTER TABLE v05_incidents ADD COLUMN anchor_article_id INTEGER")
    conn.execute("ALTER TABLE v05_incidents ADD COLUMN last_published_date TEXT")
    conn.execute("ALTER TABLE articles ADD COLUMN title TEXT")
    conn.execute("UPDATE articles SET title = 'Judul ' || article_id")
    flows.record_d1(conn)
    survey.record_d2(conn, [("INC-A", "target", "Bank X", "tidak_sesuai", f"r{i}", "Bank Y") for i in range(3)])
    official.record_official(conn, official.review_rows([REVIEW]))


def test_clean_output_limits_and_types():
    out = ai_prevention.clean_output(FakeModel().chat_json("", "", {})[0])
    assert len(out["sasaran"]) == 3 and out["sasaran"][0]["kelompok"].startswith("Nasabah")
    assert out["materi"] == ["Mengenali SMS palsu", "Verifikasi dua langkah"]


def test_flow_inputs_differ_per_flow(temp_conn):
    _setup(temp_conn)
    inputs = ai_prevention.flow_inputs(temp_conn, "INC-A", ai_prevention._latest_outputs(temp_conn))
    assert set(inputs) == {"D1", "D2", "D3", "D4"}
    assert "survei_publik" in inputs["D2"] and inputs["D2"]["survei_publik"]["koreksi_publik"]["target"]["value"] == "Bank Y"
    assert inputs["D3"]["keputusan_lembaga"]["alasan"].startswith("Sudah ditangani")
    assert inputs["D4"]["keputusan_lembaga"]["catatan_resmi"] is True
    assert "survei_publik" not in inputs["D1"] and "keputusan_lembaga" not in inputs["D1"]


def test_run_ai_only_top_incidents_and_caches(temp_conn, monkeypatch):
    _setup(temp_conn)
    monkeypatch.setattr(ai_prevention, "TOP_N", 1)
    monkeypatch.setattr(ai_prevention, "top_incidents", lambda conn, n=1, days=14: [("INC-A", 9.0)])
    model = FakeModel()
    calls, failed = ai_prevention.run_ai(temp_conn, model, "model-x", max_calls=100, now="2026-10-11T00:00:00+00:00")
    assert failed == 0
    stored = dict(temp_conn.execute("SELECT flow, output FROM ai_prevention WHERE incident_id = 'INC-A'").fetchall())
    assert set(stored) == {"D1", "D2", "D3", "D4"}  # INC-B bukan incident terbesar
    assert json.loads(stored["D1"])["pesan_kunci"] == "Jangan bagikan OTP."
    regions = temp_conn.execute("SELECT COUNT(*) FROM ai_region_literacy").fetchone()[0]
    assert regions == 38 and calls == 4 + 38
    assert temp_conn.execute("SELECT incident_id FROM ai_top").fetchall() == [("INC-A",)]
    # masukan sama, belum basi: tidak ada permintaan baru
    again = FakeModel()
    assert ai_prevention.run_ai(temp_conn, again, "model-x", now="2026-10-12T00:00:00+00:00") == (0, 0)
    # model lain: saran incident ditulis ulang, provinsi tidak (belum basi)
    other = FakeModel()
    assert ai_prevention.run_ai(temp_conn, other, "model-y", now="2026-10-12T00:00:00+00:00")[0] == 4
    # provinsi basi setelah REGION_MAX_AGE_DAYS hari
    late = FakeModel()
    assert ai_prevention.run_ai(temp_conn, late, "model-y", now="2026-10-20T00:00:00+00:00")[0] == 38


def test_run_ai_respects_call_budget_and_failures(temp_conn, monkeypatch):
    _setup(temp_conn)
    monkeypatch.setattr(ai_prevention, "top_incidents", lambda conn, n=10, days=14: [("INC-A", 9.0)])
    model = FakeModel(fail_on="D2 (publik)")
    calls, failed = ai_prevention.run_ai(temp_conn, model, "m", max_calls=3, now="2026-10-11T00:00:00+00:00")
    assert (calls, failed) == (3, 1)
    flows_done = {row[0] for row in temp_conn.execute("SELECT flow FROM ai_prevention")}
    assert flows_done == {"D1", "D3"}


def test_store_top_ranking_without_ai(temp_conn, monkeypatch):
    _setup(temp_conn)
    monkeypatch.setattr(ai_prevention, "top_incidents", lambda conn, n=10, days=14: [("INC-A", 9.0), ("INC-B", 4.0)])
    ai_prevention.store_top(temp_conn)
    assert temp_conn.execute("SELECT incident_id FROM ai_top ORDER BY rank").fetchall() == [("INC-A",), ("INC-B",)]
    assert temp_conn.execute("SELECT COUNT(*) FROM ai_prevention").fetchone() == (0,)
