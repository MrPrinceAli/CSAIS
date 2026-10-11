"""Data uji untuk melihat alur D2 - D4 bekerja sebelum ada responden dan lembaga sungguhan.

``main.py --seed-demo`` (lokal):
  - survei: jawaban publik tiruan (responden ``demo-*``) untuk sekitar 30
    incident terbaru, ditulis langsung ke database masukan (SURVEY_WRITE_TOKEN),
    termasuk koreksi untuk kolom yang dijawab tidak sesuai dan jawaban
    pertanyaan kesimpulan ("benar terjadi?");
  - lembaga: keputusan tiruan lewat API portal produksi, masuk dengan password
    tiap lembaga (PORTAL_PASSWORDS di lingkungan, JSON), sehingga ditandatangani
    kunci lembaga seperti keputusan sungguhan. Sebagian membawa nilai yang
    benar dan langkah pencegahan lembaga. Catatannya diawali "DATA UJI".
Semua data uji ditandai "DATA UJI" di web.

Untuk salinan lokal, TURSO_DATABASE_URL dan SURVEY_DATABASE_URL boleh berupa
``file:/path.db`` dan CSAIS_WEB_URL menunjuk ke server pengembangan
(lihat scripts/demo_local.sh).

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
from csais.official import DEMO_NOTE, INSTITUTION_NAMES
from csais.official import REVIEWS_SCHEMA
from csais.survey import DEMO_PREFIX, SURVEY_FIELDS, SURVEY_SCHEMA, VERDICT_FIELD

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
# Imbauan tiruan per lembaga (teks bebas portal)
ADVICE = {
    "BSSN": "Perbarui sistem dan cadangkan data secara berkala; laporkan insiden ke BSSN.",
    "OJK": "Cek legalitas pihak yang menawarkan investasi atau pinjaman di situs OJK sebelum bertransaksi.",
    "KOMDIGI": "Jangan membuka tautan atau lampiran dari pengirim yang tidak dikenal; laporkan konten ke aduankonten.id.",
    "POLRI": "Simpan bukti percakapan dan transfer, lalu laporkan ke patrolisiber.id.",
}
# Sasaran dan materi literasi yang lazim ditekankan tiap lembaga (tiruan)
LITERACY = {
    "BSSN": (["staf_ti", "pimpinan"], ["pembaruan_sistem", "cadangan_data"]),
    "OJK": (["investor_ritel", "nasabah_bank"], ["cek_legalitas", "data_pribadi"]),
    "KOMDIGI": (["pengguna_medsos", "orang_tua"], ["kenali_phishing", "cek_fakta"]),
    "POLRI": (["ibu_rumah_tangga", "lansia"], ["rekayasa_sosial", "lapor_insiden"]),
}

CARDS_SQL = """
    SELECT o.incident_id, o.output_id, o.attack_type, o.target, o.threat_actor, o.attack_date, o.location,
           o.target_group
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
    from csais.survey import fetch_file, fetch_remote

    url = os.environ[url_env]
    if url.startswith("file:"):
        return fetch_file(url[len("file:"):], sql)
    return fetch_remote(url, os.environ.get(token_env), sql)


def _write_input(statements):
    url = os.environ["SURVEY_DATABASE_URL"]
    if url.startswith("file:"):
        import sqlite3

        conn = sqlite3.connect(url[len("file:"):])
        try:
            for sql, args in statements:
                conn.execute(sql, args)
            conn.commit()
        finally:
            conn.close()
        return []
    from csais.publish import TursoClient

    token = os.environ.get("SURVEY_WRITE_TOKEN")
    if not token:
        raise SystemExit("SURVEY_WRITE_TOKEN belum diisi di .env")
    return TursoClient(url, token).execute(statements)


def _ensure_survey_table():
    """Tabel jawaban dengan kolom koreksi (database lama belum punya kolomnya)."""
    _write_input([(SURVEY_SCHEMA, [])])
    columns = {row[1] for row in _remote("PRAGMA table_info(survey_responses)", "SURVEY_DATABASE_URL", "SURVEY_AUTH_TOKEN")}
    if "corrected_value" not in columns:
        _write_input([("ALTER TABLE survey_responses ADD COLUMN corrected_value TEXT", [])])


def alternatives(cards):
    """Nilai lain per kolom dari kartu-kartu lain, untuk koreksi tiruan."""
    pool = {field: [] for field in SURVEY_FIELDS}
    for card in cards:
        for field, value in zip(SURVEY_FIELDS, card[2:7]):
            if value and value not in pool[field]:
                pool[field].append(value.split(",")[0].strip() if field == "attack_type" else value)
    return pool


def _correction(rng, pool, field, current, index):
    """Koreksi tiruan yang konsisten per incident (penjawab cenderung sepakat)."""
    options = [v for v in pool[field] if v != current]
    if not options:
        return None
    main, other = options[index % len(options)], options[(index + 7) % len(options)]
    return main if rng.random() < 0.8 else other


def survey_rows(cards, rng, now):
    """Jawaban tiruan: sebagian besar sesuai, sebagian incident cenderung tidak sesuai.

    Jawaban tidak sesuai sering membawa koreksi, dan setiap penjawab juga
    menjawab pertanyaan kesimpulan; incident yang dinilai keliru cenderung
    dianggap hoaks."""
    rows = []
    pool = alternatives(cards)
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
                corrected = None
                if answer == "tidak_sesuai" and rng.random() < 0.75:
                    corrected = _correction(rng, pool, field, values[field], index)
                rows.append((submission, incident_id, output_id, field, values[field], answer, respondent, None, "id", now, corrected))
            roll = rng.random()
            if skeptical:
                verdict = "tidak_sesuai" if roll < 0.65 else "tidak_tahu" if roll < 0.9 else "sesuai"
            else:
                verdict = "sesuai" if roll < 0.75 else "tidak_tahu" if roll < 0.95 else "tidak_sesuai"
            rows.append((submission, incident_id, output_id, VERDICT_FIELD, None, verdict, respondent, None, "id", now, None))
    return rows


def candidate_steps(group, attack_type):
    """Langkah yang bisa dipilih lembaga; sama dengan candidateSteps di web/lib/prevention.ts."""
    by_type, alias = flows.PREVENTION["by_type"], flows.PREVENTION["alias"]
    keys = [f"group:{group}"] if group in flows.PREVENTION["by_group"] else []
    types = [alias.get(t, t) for t in flows.attack_types(attack_type or "")]
    known = list(dict.fromkeys(t for t in types if t in by_type and t != "cyber_attack"))
    for name in known + ["cyber_attack"]:
        keys.extend(f"type:{name}:{j}" for j in range(len(by_type[name])))
    return keys


def pick_reviews(cards):
    """Empat incident per lembaga sesuai mandat, tidak dipakai dua lembaga."""
    used, picks = set(), []
    for inst, words in MANDATE.items():
        chosen = [c for c in cards if c[0] not in used and any(w in (c[2] or "") for w in words)][: len(PLAN)]
        for card, plan in zip(chosen, PLAN):
            used.add(card[0])
            picks.append((inst, card, plan))
    return picks


def literacy_plan(inst, card, status):
    """Pilihan lembaga: satu sasaran dan materi dari saran mesin, sisanya khas lembaga."""
    machine = flows.literacy_for(card[7] or "", flows.attack_types(card[2]), hoax=status == "dibantah")
    audience, topics = LITERACY[inst]
    if status == "dibantah":
        return {"audience": audience, "topics": ["cek_fakta", "lapor_insiden"]}
    return {
        "audience": list(dict.fromkeys(machine["audience"][:1] + audience)),
        "topics": list(dict.fromkeys(machine["topics"][:1] + topics)),
    }


def seed(log=print, with_survey=True, institutions=None, overlap=False):
    """Isi data uji; ``with_survey=False`` dan ``institutions`` untuk melanjutkan sebagian,
    ``overlap`` untuk keputusan lembaga pada incident yang sudah disurvei."""
    rng = random.Random(SEED)
    cards = _remote(CARDS_SQL)
    log(f"Kartu D1 kandidat dari Turso: {len(cards)}")
    if with_survey and not overlap:
        seed_survey(cards, rng, log)
    seed_reviews(cards, institutions, log, overlap)


def seed_survey(cards, rng, log=print):
    now = get_timestamp()
    rows = survey_rows(cards[:SURVEY_INCIDENTS], rng, now)
    _ensure_survey_table()
    insert = (
        "INSERT INTO survey_responses (submission_id, incident_id, card_output_id, field, shown_value, answer,"
        " respondent, ip_hash, lang, created_at, corrected_value) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    for start in range(0, len(rows), 200):
        _write_input([(insert, list(r)) for r in rows[start : start + 200]])
    log(f"Survei: {len(rows)} jawaban untuk {SURVEY_INCIDENTS} incident")


OVERLAP_PLAN = [("dikonfirmasi", "laporan_diterima", True), ("dibantah", "hoaks", False)]


def pick_overlap(cards):
    """Dua incident yang sudah disurvei per lembaga, agar D2 dan D3/D4 bisa dibandingkan."""
    picks, pool = [], list(cards[:SURVEY_INCIDENTS])
    for index, inst in enumerate(MANDATE):
        for plan, card in zip(OVERLAP_PLAN, pool[index * 2 : index * 2 + 2]):
            picks.append((inst, card, plan))
    return picks


def seed_reviews(cards, institutions=None, log=print, overlap=False):
    passwords = json.loads(os.environ.get("PORTAL_PASSWORDS") or "{}")
    if not passwords:
        log("PORTAL_PASSWORDS kosong; keputusan lembaga dilewati.")
        return
    saved = 0
    sessions = {}
    from csais.survey import fetch_rows

    _write_input([(REVIEWS_SCHEMA, [])])  # tabel kosong bila web belum pernah menyimpan keputusan
    done = {row[0] for row in fetch_rows(f"SELECT incident_id FROM official_reviews WHERE reason_text LIKE '{DEMO_NOTE}%'") or []}
    pool = alternatives(cards)
    picks = pick_overlap(cards) if overlap else pick_reviews(cards[SURVEY_INCIDENTS:])
    for inst, card, (status, reason, target_wrong) in picks:
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
        wrong = bool(target_wrong and card[3])
        steps = candidate_steps(card[7], card[2])
        body = {
            "incident_id": card[0], "output_id": int(card[1]), "status": status, "reason": reason,
            "fields": {"target": "salah"} if wrong else {},
            "corrections": {"target": _correction(random.Random(card[0]), pool, "target", card[3], len(card[0]))} if wrong else {},
            # langkah lembaga: dua langkah terakhir yang relevan (sering berbeda dari saran mesin)
            "prevention": steps[-2:] if status != "dibantah" else [],
            "prevention_text": ADVICE[inst] if status == "dikonfirmasi" else "",
            "literacy": literacy_plan(inst, card, status),
            "note": f"{DEMO_NOTE}: keputusan contoh untuk pengujian alur, bukan pernyataan resmi {INSTITUTION_NAMES.get(inst, inst)}.",
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
