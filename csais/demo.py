"""Data uji untuk melihat alur D2 - D4 bekerja sebelum ada responden dan lembaga sungguhan.

``main.py --seed-demo`` (lokal):
  - survei: jawaban publik tiruan (responden ``demo-*``) untuk sekitar 30
    incident terbaru, ditulis langsung ke database masukan (SURVEY_WRITE_TOKEN);
  - lembaga: keputusan tiruan lewat API portal produksi, masuk dengan password
    tiap lembaga (PORTAL_PASSWORDS di lingkungan, JSON), sehingga ditandatangani
    kunci lembaga seperti keputusan sungguhan. Catatannya diawali "DATA UJI".
Semua data uji ditandai "DATA UJI" di web.

``main.py --purge-demo``: hapus data uji dari database masukan (bila token tulis
ada) dan keluaran D2 - D4 bertanda demo dari database pipeline. Di GitHub
Actions jalankan workflow dengan input ``purge_demo`` agar database pipeline
di cloud ikut dibersihkan.
"""

import json
import os
import random
import uuid

import requests

from csais import flows
from csais.db import get_connection, get_timestamp
from csais.official import DEMO_NOTE
from csais.survey import DEMO_PREFIX, SURVEY_FIELDS

PORTAL_URL = os.environ.get("CSAIS_WEB_URL") or "https://csais.vercel.app"
SURVEY_INCIDENTS = 30
SEED = 20260929

# Mandat ringkas per lembaga (sama semangatnya dengan web/lib/portal.ts)
MANDATE = {
    "BSSN": ("ransomware", "malware", "network_intrusion", "vulnerability", "ddos", "cyber_attack"),
    "OJK": ("investment_scam", "credential", "account_takeover", "crypto"),
    "KOMDIGI": ("phishing", "malicious", "data_breach", "data_leak", "mobile"),
    "POLRI": ("online_scam", "job_scam", "social_engineering", "deepfake", "extortion"),
}
# (status, alasan, tandai target salah) per lembaga: 2 konfirmasi, 1 bantah, 1 sebagian
PLAN = [("dikonfirmasi", "ditangani", False), ("dikonfirmasi", "laporan_diterima", True),
        ("dibantah", "hoaks", False), ("sebagian", "diselidiki", False)]

CARDS_SQL = """
    SELECT o.incident_id, o.output_id, o.attack_type, o.target, o.threat_actor, o.attack_date, o.location
    FROM flow_outputs o
    JOIN (SELECT incident_id, MAX(output_id) AS last_id FROM flow_outputs WHERE flow = 'D1' GROUP BY incident_id) m
      ON m.last_id = o.output_id
    JOIN v05_incidents i ON i.incident_id = o.incident_id
    LEFT JOIN articles a ON a.article_id = i.anchor_article_id
    WHERE o.status != 'dihapus' AND i.document_count >= 2
    ORDER BY (lower(COALESCE(i.location, '')) LIKE '%indonesia%' OR a.language = 'id') DESC, i.anchor_published_date DESC
    LIMIT 200
"""


def _remote(sql, url_env="TURSO_DATABASE_URL", token_env="TURSO_AUTH_TOKEN"):
    from csais.survey import fetch_remote

    return fetch_remote(os.environ[url_env], os.environ.get(token_env), sql)


def _write_input(statements):
    from csais.publish import TursoClient

    token = os.environ.get("SURVEY_WRITE_TOKEN")
    if not token:
        raise SystemExit("SURVEY_WRITE_TOKEN belum diisi di .env")
    return TursoClient(os.environ["SURVEY_DATABASE_URL"], token).execute(statements)


def survey_rows(cards, rng, now):
    """Jawaban tiruan: sebagian besar sesuai, sebagian incident cenderung tidak sesuai."""
    rows = []
    for index, card in enumerate(cards):
        incident_id, output_id = card[0], card[1]
        values = dict(zip(SURVEY_FIELDS, card[2:7]))
        skeptical = index % 5 == 4  # tiap incident kelima dinilai keliru oleh publik
        for n in range(rng.randint(3, 6)):
            respondent = f"{DEMO_PREFIX}{index:02d}{n}"
            submission = str(uuid.uuid4())
            for field in SURVEY_FIELDS:
                if values[field] is None and rng.random() < 0.6:
                    continue
                roll = rng.random()
                if skeptical:
                    answer = "tidak_sesuai" if roll < 0.75 else "tidak_tahu"
                else:
                    answer = "sesuai" if roll < 0.8 else "tidak_tahu" if roll < 0.93 else "tidak_sesuai"
                rows.append((submission, incident_id, output_id, field, values[field], answer, respondent, None, "id", now))
    return rows


def pick_reviews(cards):
    """Empat incident per lembaga sesuai mandat, tidak dipakai dua lembaga."""
    used, picks = set(), []
    for inst, words in MANDATE.items():
        chosen = [c for c in cards if c[0] not in used and any(w in (c[2] or "") for w in words)][: len(PLAN)]
        for card, plan in zip(chosen, PLAN):
            used.add(card[0])
            picks.append((inst, card, plan))
    return picks


def seed(log=print, with_survey=True, institutions=None):
    """Isi data uji; ``with_survey=False`` dan ``institutions`` untuk melanjutkan sebagian."""
    rng = random.Random(SEED)
    cards = _remote(CARDS_SQL)
    log(f"Kartu D1 kandidat dari Turso: {len(cards)}")
    if with_survey:
        seed_survey(cards, rng, log)
    seed_reviews(cards, institutions, log)


def seed_survey(cards, rng, log=print):
    now = get_timestamp()
    rows = survey_rows(cards[:SURVEY_INCIDENTS], rng, now)
    insert = (
        "INSERT INTO survey_responses (submission_id, incident_id, card_output_id, field, shown_value, answer,"
        " respondent, ip_hash, lang, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    for start in range(0, len(rows), 200):
        _write_input([(insert, list(r)) for r in rows[start : start + 200]])
    log(f"Survei: {len(rows)} jawaban untuk {SURVEY_INCIDENTS} incident")


def seed_reviews(cards, institutions=None, log=print):
    passwords = json.loads(os.environ.get("PORTAL_PASSWORDS") or "{}")
    if not passwords:
        log("PORTAL_PASSWORDS kosong; keputusan lembaga dilewati.")
        return
    saved = 0
    sessions = {}
    from csais.survey import fetch_rows

    done = {row[0] for row in fetch_rows(f"SELECT incident_id FROM official_reviews WHERE reason_text LIKE '{DEMO_NOTE}%'") or []}
    for inst, card, (status, reason, target_wrong) in pick_reviews(cards[SURVEY_INCIDENTS:]):
        if (institutions and inst not in institutions) or card[0] in done:
            continue
        if inst not in sessions:  # satu kali masuk per lembaga (portal membatasi percobaan masuk)
            session = requests.Session()
            login = session.post(f"{PORTAL_URL}/api/portal/login", json={"institution": inst, "password": passwords.get(inst, "")}, timeout=60)
            sessions[inst] = session if login.status_code == 200 else None
            if login.status_code != 200:
                log(f"   ⚠️ {inst}: gagal masuk ({login.status_code})")
        session = sessions[inst]
        if session is None:
            continue
        body = {
            "incident_id": card[0], "output_id": int(card[1]), "status": status, "reason": reason,
            "fields": {"target": "salah"} if target_wrong and card[3] else {},
            "note": f"{DEMO_NOTE}: keputusan contoh untuk pengujian alur, bukan pernyataan resmi {inst}.",
        }
        response = session.post(f"{PORTAL_URL}/api/portal/review", json=body, timeout=60)
        if response.status_code == 200:
            saved += 1
        else:
            log(f"   ⚠️ {inst} {card[0]}: {response.status_code} {response.text[:120]}")
    log(f"Lembaga: {saved} keputusan tersimpan lewat portal (ditandatangani)")


def purge(log=print):
    """Hapus data uji dari database masukan (bila bisa) dan keluaran demo dari database pipeline."""
    if os.environ.get("SURVEY_WRITE_TOKEN") and os.environ.get("SURVEY_DATABASE_URL"):
        _write_input([
            (f"DELETE FROM survey_responses WHERE respondent LIKE '{DEMO_PREFIX}%'", []),
            (f"DELETE FROM official_reviews WHERE reason_text LIKE '{DEMO_NOTE}%'", []),
        ])
        log("Data uji dihapus dari database masukan.")
    conn = get_connection()
    try:
        removed = flows.purge_demo_outputs(conn)
    finally:
        conn.close()
    log(f"Keluaran D2 - D4 data uji dihapus dari database pipeline: {removed} baris")
