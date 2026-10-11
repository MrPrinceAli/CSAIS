"""Alur D2: kumpulkan jawaban survei publik menjadi keluaran D2 per incident.

Jawaban ditulis web (halaman /survey) ke database survei terpisah di Turso,
bukan ke database utama, agar token tulis web tidak bisa menyentuh hasil
pipeline. Tahap ini hanya membaca (token baca saja cukup):

  SURVEY_DATABASE_URL  libsql://csais-survey-nama.turso.io, atau file:/path.db
  SURVEY_AUTH_TOKEN    token baca; tidak perlu untuk file:

Satu baris ``survey_responses`` = satu jawaban untuk satu kolom kartu inti,
bersama nilai kolom yang ditampilkan saat itu (``shown_value``). Jawaban
dihitung hanya bila nilainya masih sama dengan kartu D1 terbaru; jawaban
untuk kartu lama dicatat sebagai ``ignored_old_card`` di kolom basis.

Keputusan per kolom: minimal MIN_DECISIVE jawaban sesuai/tidak sesuai dan
pilihan terbanyak sedikitnya AGREEMENT dari jawaban itu; selain itu ``belum``.
Status kartu: ``tidak_sesuai`` bila ada kolom yang diputuskan tidak sesuai,
``sesuai`` bila semua kolom yang diputuskan sesuai, selain itu ``belum``.

Penjawab yang memilih tidak sesuai boleh menulis nilai yang benar menurut
berita (``corrected_value``). Kolom yang diputuskan tidak sesuai memakai
koreksi terbanyak sebagai nilai D2; tanpa koreksi, nilai kartu tetap dipakai.

Pertanyaan terpisah ``kejadian`` ("menurut Anda kejadian ini benar terjadi?",
jawaban sesuai = ya, tidak_sesuai = tidak) diputuskan dengan aturan yang sama
dan menjadi kesimpulan D2 di ``basis.verdict``: benar, hoaks, atau belum_pasti.
Untuk sementara satu orang boleh menjawab berkali-kali; ``respondent`` dan
``ip_hash`` disimpan agar penyaringan bisa ditambahkan tanpa kehilangan data.
"""

import json
import os
import sqlite3

from csais import flows
from csais.db import get_connection, get_timestamp
from csais.provenance import pipeline_stamp
from csais.publish import TursoClient
from csais.schema import record_run

SURVEY_FIELDS = ("attack_type", "target", "threat_actor", "attack_date", "location")
ANSWERS = ("sesuai", "tidak_sesuai", "tidak_tahu")
MIN_DECISIVE = 3
AGREEMENT = 2 / 3
VERDICT_FIELD = "kejadian"  # pertanyaan kesimpulan, bukan kolom kartu
VERDICT_OF_ANSWER = {"sesuai": "benar", "tidak_sesuai": "hoaks"}
UNDECIDED = "belum_pasti"
DEMO_PREFIX = "demo-"  # responden data uji (scripts/seed_demo.py); ditandai "DATA UJI" di web

# Skema di database survei; web (web/lib/survey.ts) membuat tabel yang sama
SURVEY_SCHEMA = """
    CREATE TABLE IF NOT EXISTS survey_responses (
        response_id INTEGER PRIMARY KEY AUTOINCREMENT,
        submission_id TEXT NOT NULL,
        incident_id TEXT NOT NULL,
        card_output_id INTEGER NOT NULL,
        field TEXT NOT NULL,
        shown_value TEXT,
        answer TEXT NOT NULL CHECK (answer IN ('sesuai', 'tidak_sesuai', 'tidak_tahu')),
        respondent TEXT,
        ip_hash TEXT,
        lang TEXT,
        created_at TEXT NOT NULL,
        corrected_value TEXT
    )
"""

RESPONSES_SQL = """
    SELECT incident_id, field, shown_value, answer, respondent, {corrected_value}
    FROM survey_responses
"""


# --- Pembacaan jawaban ---
def _hrana_value(cell):
    return None if cell.get("type") == "null" else cell.get("value")


def fetch_remote(database_url, auth_token, sql):
    """Baca baris dari database survei di Turso; [] bila tabel belum ada."""
    client = TursoClient(database_url, auth_token)
    try:
        results = client.execute([(sql, [])])
    except RuntimeError as error:
        if "no such table" in str(error):
            return []
        raise
    result = results[0]["response"]["result"]
    return [tuple(_hrana_value(cell) for cell in row) for row in result["rows"]]


def fetch_file(path, sql):
    """Baca baris dari berkas SQLite lokal (pengujian dan pengembangan)."""
    conn = sqlite3.connect(path)
    try:
        return conn.execute(sql).fetchall()
    except sqlite3.OperationalError as error:
        if "no such table" in str(error):
            return []
        raise
    finally:
        conn.close()


def fetch_rows(sql):
    """Baris hasil ``sql`` dari database survei; None bila belum dikonfigurasi."""
    url = (os.environ.get("SURVEY_DATABASE_URL") or "").strip()
    if not url:
        return None
    if url.startswith("file:"):
        return fetch_file(url[len("file:"):], sql)
    return fetch_remote(url, os.environ.get("SURVEY_AUTH_TOKEN"), sql)


def table_columns(table):
    """Nama kolom tabel di database survei; None bila belum dikonfigurasi.

    Kolom baru ditambahkan web saat pertama dipakai, jadi pipeline memeriksa
    dulu kolom yang ada sebelum memilihnya."""
    rows = fetch_rows(f"PRAGMA table_info({table})")
    return None if rows is None else {row[1] for row in rows}


def select_sql(template, columns, optional):
    """Isi kolom opsional di ``template``: namanya bila ada, NULL bila belum."""
    return template.format(**{name: name if name in columns else "NULL" for name in optional})


def fetch_responses():
    """Jawaban dari database survei; None bila belum dikonfigurasi."""
    columns = table_columns("survey_responses")
    if columns is None:
        return None
    return fetch_rows(select_sql(RESPONSES_SQL, columns, ("corrected_value",)))


# --- Agregasi ---
def decide(counts):
    """Keputusan satu kolom dari hitungan jawaban."""
    agree, disagree = counts.get("sesuai", 0), counts.get("tidak_sesuai", 0)
    decisive = agree + disagree
    if decisive < MIN_DECISIVE:
        return "belum"
    if agree / decisive >= AGREEMENT:
        return "sesuai"
    if disagree / decisive >= AGREEMENT:
        return "tidak_sesuai"
    return "belum"


def top_correction(values):
    """Koreksi terbanyak (huruf dan spasi dirapikan saat dihitung): (nilai, jumlah)."""
    counts, first = {}, {}
    for value in values:
        key = " ".join(value.lower().split())
        counts[key] = counts.get(key, 0) + 1
        first.setdefault(key, " ".join(value.split()))
    best = max(counts, key=counts.get)  # seri: koreksi yang lebih dulu masuk
    return first[best], counts[best]


def latest_d1(conn):
    """Kartu D1 terbaru per incident (tanpa yang dihapus): incident_id -> baris."""
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT o.* FROM flow_outputs o
            JOIN (SELECT incident_id, MAX(output_id) AS last_id
                  FROM flow_outputs WHERE flow = 'D1' GROUP BY incident_id) m
              ON m.last_id = o.output_id
            WHERE o.status != ?
            """, (flows.REMOVED,)).fetchall()
    finally:
        conn.row_factory = None
    return {row["incident_id"]: dict(row) for row in rows}


def d2_rows(cards, responses):
    """Keluaran D2 per incident yang punya jawaban untuk kartu terbarunya."""
    grouped = {}
    for incident_id, field, shown, answer, respondent, *rest in responses:
        correction = (rest[0] or "").strip() if rest and rest[0] else None
        if incident_id in cards and field in SURVEY_FIELDS + (VERDICT_FIELD,) and answer in ANSWERS:
            grouped.setdefault(incident_id, []).append((field, shown, answer, respondent, correction))
    rows = {}
    for incident_id, answers in grouped.items():
        card = cards[incident_id]
        counts = {field: {} for field in SURVEY_FIELDS + (VERDICT_FIELD,)}
        corrections = {field: [] for field in SURVEY_FIELDS}
        respondents, matched, ignored, demo = set(), 0, 0, 0
        for field, shown, answer, respondent, correction in answers:
            if field != VERDICT_FIELD and (shown or None) != card.get(field):
                ignored += 1
                continue
            matched += 1
            counts[field][answer] = counts[field].get(answer, 0) + 1
            if correction and answer == "tidak_sesuai" and field != VERDICT_FIELD:
                corrections[field].append(correction)
            if respondent:
                respondents.add(respondent)
                demo += str(respondent).startswith(DEMO_PREFIX)
        if not matched:
            continue
        verdicts = {field: decide(counts[field]) for field in SURVEY_FIELDS if counts[field]}
        values = {field: card.get(field) for field in flows.FIELDS}
        corrected = {}
        for field, given in corrections.items():
            if given and verdicts.get(field) == "tidak_sesuai":
                values[field], votes = top_correction(given)
                corrected[field] = {"value": values[field], "votes": votes, "given": len(given)}
        decided = [v for v in verdicts.values() if v != "belum"]
        if "tidak_sesuai" in decided:
            status = "tidak_sesuai"
        elif decided:
            status = "sesuai"
        else:
            status = flows.PENDING
        extra = {}
        if counts[VERDICT_FIELD]:
            extra["verdict"] = VERDICT_OF_ANSWER.get(decide(counts[VERDICT_FIELD]), UNDECIDED)
        if corrected:
            extra["corrections"] = corrected
        rows[incident_id] = {
            **values,
            "field_status": verdicts,
            "status": status,
            "tier": "waspada" if status == "sesuai" else None,
            "prevention": json.loads(card["prevention"]) if status == "sesuai" and card.get("prevention") else None,
            "basis": {
                "responses": matched,
                "respondents": len(respondents),
                "ignored_old_card": ignored,
                "counts": {field: c for field, c in counts.items() if c},
                "rule": {"min_decisive": MIN_DECISIVE, "agreement": round(AGREEMENT, 4)},
                **extra,
                **({"demo": True, "demo_responses": demo} if demo else {}),
            },
            "source_ref": "survey",
        }
    return rows


def record_d2(conn, responses, recorded_at=None):
    """Catat snapshot D2 yang berubah; kembalikan (baru/berubah, incident dengan jawaban)."""
    flows.create_tables(conn)
    recorded_at = recorded_at or get_timestamp()
    version = pipeline_stamp()
    previous = flows.latest_hashes(conn, "D2")
    current = d2_rows(latest_d1(conn), responses)
    changed = 0
    for incident_id, row in current.items():
        stored = dict(row)
        for key in ("field_status", "prevention", "basis"):
            if isinstance(stored[key], (dict, list)):
                stored[key] = json.dumps(stored[key], ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        known = previous.get(incident_id)
        if known and known[0] == flows.output_hash(stored):
            continue
        flows.record_output(conn, incident_id, "D2", stored, recorded_at, version)
        changed += 1
    conn.commit()
    return changed, len(current)


def run():
    """Jalankan tahap alur D2: kumpulkan jawaban survei publik."""
    print("\n==================================================")
    print("   ALUR D2 - SURVEI PUBLIK")
    print("==================================================")
    responses = fetch_responses()
    if responses is None:
        print("SURVEY_DATABASE_URL belum diisi; tahap D2 dilewati.")
        return
    started_at = get_timestamp()
    conn = get_connection()
    try:
        changed, total = record_d2(conn, responses)
        record_run(conn, "flows_d2", started_at, changed)
    finally:
        conn.close()
    print(f"Jawaban dibaca       : {len(responses)}")
    print(f"Incident dengan kartu: {total}")
    print(f"Snapshot baru/berubah: {changed}")
    print("==================================================")
    print("   ✅ ALUR D2 SELESAI")
    print("==================================================")


if __name__ == "__main__":
    run()
