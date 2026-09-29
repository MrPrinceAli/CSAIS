"""Alur D3 dan D4: pernyataan lembaga atau kementerian per incident.

Sampai portal lembaga (Sprint 3) ada, pernyataan dicatat tim peneliti di
``statements/official_statements.csv``: satu baris per pernyataan resmi yang
sudah dipublikasikan lembaga (siaran pers, unggahan akun resmi, jawaban
tertulis), dengan tautan sumbernya. Berkas itu ada di git, jadi setiap
perubahan tercatat siapa dan kapan.

Setiap run tahap ini:
  1. memuat CSV ke tabel ``official_statements`` (diganti penuh; riwayatnya
     di git), baris yang tidak valid dilaporkan dan dilewati;
  2. D3: pernyataan terbaru per incident menjadi keluaran D3. Kolom yang
     disebut lembaga dibandingkan dengan kartu D1: sama = dikonfirmasi,
     berbeda = dibantah (kartu mesin keliru); kolom yang tidak disebut
     memakai nilai kartu dan tidak dinilai;
  3. D4: pernyataan terbaru berstatus dikonfirmasi atau dibantah yang punya
     reason statement dicatat sebagai catatan resmi, tingkat
     ``rekomendasi_resmi`` atau ``peringatan_hoaks``. Catatan tidak pernah
     diubah: isi baru menjadi baris baru dengan ``supersedes`` ke baris lama.

``candidates()`` menyiapkan daftar incident yang kemungkinan punya pernyataan
resmi (artikel dari sumber OFFICIAL atau judul menyebut lembaga) untuk
membantu tim mengisi CSV (``main.py --official-candidates FILE``).
"""

import csv
import json
import os
import re

from csais import flows
from csais.config import PROJECT_ROOT
from csais.db import get_connection, get_timestamp
from csais.provenance import pipeline_stamp
from csais.schema import record_run
from csais.survey import SURVEY_FIELDS, latest_d1

STATEMENTS_FILE = os.path.join(PROJECT_ROOT, "statements", "official_statements.csv")
COLUMNS = (
    "statement_id", "incident_id", "institution", "status", "statement_date",
    "source_url", "reason", "attack_type", "target", "threat_actor", "attack_date",
    "location", "prevention_text", "prevention_keys", "recorded_by",
)
STATUSES = ("dikonfirmasi", "dibantah", "sebagian")
OFFICIAL_TIER = {"dikonfirmasi": "rekomendasi_resmi", "dibantah": "peringatan_hoaks"}
INSTITUTION_WORDS = ("BSSN", "OJK", "Komdigi", "Kominfo", "Polri", "Bareskrim", "Siber Polri", "Bank Indonesia")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


# --- CSV ---
def _text(value):
    value = (value or "").strip()
    return value or None


def load_statements(path=STATEMENTS_FILE):
    """Baca CSV pernyataan; kembalikan (baris valid, daftar pesan kesalahan)."""
    if not os.path.exists(path):
        return [], []
    rows, errors, seen = [], [], set()
    with open(path, encoding="utf-8", newline="") as fh:
        for line, raw in enumerate(csv.DictReader(fh), start=2):
            row = {key: _text(raw.get(key)) for key in COLUMNS}
            problem = None
            if not row["statement_id"] or row["statement_id"] in seen:
                problem = "statement_id kosong atau ganda"
            elif not row["incident_id"]:
                problem = "incident_id kosong"
            elif not row["institution"]:
                problem = "institution kosong"
            elif row["status"] not in STATUSES:
                problem = f"status harus salah satu dari {', '.join(STATUSES)}"
            elif not row["source_url"] or not row["source_url"].startswith(("http://", "https://")):
                problem = "source_url harus tautan http(s) ke pernyataan resmi"
            elif not row["statement_date"] or not _DATE.match(row["statement_date"]):
                problem = "statement_date harus berformat YYYY-MM-DD"
            if problem:
                errors.append(f"baris {line}: {problem}")
                continue
            seen.add(row["statement_id"])
            rows.append(row)
    return rows, errors


def create_tables(conn):
    columns = ", ".join(f"{name} TEXT" for name in COLUMNS[1:])
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS official_statements "
        f"(statement_id TEXT PRIMARY KEY, {columns}, loaded_at TEXT NOT NULL)"
    )
    conn.commit()


def store_statements(conn, rows, loaded_at):
    """Ganti isi official_statements dengan baris dari CSV."""
    create_tables(conn)
    conn.execute("DELETE FROM official_statements")
    conn.executemany(
        f"INSERT INTO official_statements ({', '.join(COLUMNS)}, loaded_at) "
        f"VALUES ({', '.join('?' for _ in COLUMNS)}, ?)",
        [tuple(row[key] for key in COLUMNS) + (loaded_at,) for row in rows],
    )
    conn.commit()


# --- D3 dan D4 ---
def _same(field, a, b):
    if field == "attack_type":
        return set(flows.attack_types(b)) <= set(flows.attack_types(a))
    return " ".join(str(a).lower().split()) == " ".join(str(b).lower().split())


def latest_statements(rows):
    """Pernyataan terbaru per incident, beserta jumlah dan lembaga semua pernyataannya."""
    by_incident = {}
    for row in rows:
        by_incident.setdefault(row["incident_id"], []).append(row)
    result = {}
    for incident_id, items in by_incident.items():
        items.sort(key=lambda r: (r["statement_date"], r["statement_id"]))
        result[incident_id] = (items[-1], items)
    return result


def d3_row(card, statement, items):
    """Keluaran D3 dari kartu D1 dan pernyataan terbaru."""
    values, verdicts = {}, {}
    for field in flows.FIELDS:
        stated = statement.get(field) if field in SURVEY_FIELDS else None
        values[field] = stated or card.get(field)
        if stated:
            verdicts[field] = "dikonfirmasi" if card.get(field) and _same(field, card.get(field), stated) else "dibantah"
    keys = [k.strip() for k in (statement["prevention_keys"] or "").split(";") if k.strip()]
    prevention = None
    if keys or statement["prevention_text"]:
        prevention = {"steps": keys, "text": statement["prevention_text"]}
    return {
        **values,
        "field_status": verdicts,
        "status": statement["status"],
        "tier": None,
        "prevention": prevention,
        "basis": {
            "statement_id": statement["statement_id"],
            "institution": statement["institution"],
            "statement_date": statement["statement_date"],
            "statements": len(items),
            "institutions": sorted({r["institution"] for r in items}),
        },
        "source_ref": statement["source_url"],
        "reason": statement["reason"],
    }


def _json_columns(row):
    stored = dict(row)
    for key in ("field_status", "prevention", "basis"):
        if isinstance(stored.get(key), (dict, list)):
            stored[key] = json.dumps(stored[key], ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return stored


def latest_rows(conn, flow):
    """Baris terakhir satu alur per incident (kolom lengkap)."""
    cursor = conn.execute(
        """
        SELECT o.* FROM flow_outputs o
        JOIN (SELECT incident_id, MAX(output_id) AS last_id
              FROM flow_outputs WHERE flow = ? GROUP BY incident_id) m
          ON m.last_id = o.output_id
        """,
        (flow,),
    )
    names = [d[0] for d in cursor.description]
    return {row[1]: dict(zip(names, row)) for row in cursor.fetchall()}


def record_official(conn, rows, recorded_at=None):
    """Catat D3 dan D4 yang berubah; kembalikan (D3 baru, D4 baru, incident tidak dikenal)."""
    flows.create_tables(conn)
    recorded_at = recorded_at or get_timestamp()
    version = pipeline_stamp()
    cards = latest_d1(conn)
    previous_d3 = flows.latest_hashes(conn, "D3")
    previous_d4 = latest_rows(conn, "D4")
    new_d3 = new_d4 = 0
    unknown = []
    for incident_id, (statement, items) in latest_statements(rows).items():
        card = cards.get(incident_id)
        if card is None:
            unknown.append(incident_id)
            continue
        row = _json_columns(d3_row(card, statement, items))
        known = previous_d3.get(incident_id)
        if not known or known[0] != flows.output_hash(row):
            flows.record_output(conn, incident_id, "D3", row, recorded_at, version)
            new_d3 += 1
        if statement["status"] not in OFFICIAL_TIER or not statement["reason"]:
            continue
        record = {**row, "tier": OFFICIAL_TIER[statement["status"]]}
        prior = previous_d4.get(incident_id)
        if prior:
            # isi sama dengan catatan terakhir (supersedes ikut disamakan) = tidak ada catatan baru
            if flows.output_hash({**record, "supersedes": prior["supersedes"]}) == prior["output_hash"]:
                continue
            record["supersedes"] = prior["output_id"]
        flows.record_output(conn, incident_id, "D4", record, recorded_at, version)
        new_d4 += 1
    conn.commit()
    return new_d3, new_d4, unknown


# --- Kandidat untuk tim ---
def candidates(conn, limit=500):
    """Incident yang kemungkinan punya pernyataan resmi, sebagai baris CSV setengah jadi."""
    cards = latest_d1(conn)
    like = " OR ".join("a.title LIKE ?" for _ in INSTITUTION_WORDS)
    cursor = conn.execute(
        f"""
        SELECT d.incident_id, a.title, COALESCE(a.resolved_url, a.article_url), a.published_date,
               a.source_type
        FROM v05_incident_documents d JOIN articles a ON a.article_id = d.article_id
        WHERE a.source_type = 'OFFICIAL' OR {like}
        ORDER BY a.published_date DESC
        """,
        [f"%{word}%" for word in INSTITUTION_WORDS],
    )
    rows, seen = [], set()
    for incident_id, title, url, published, source_type in cursor.fetchall():
        if incident_id in seen or incident_id not in cards:
            continue
        seen.add(incident_id)
        card = cards[incident_id]
        institution = next((w.strip() for w in INSTITUTION_WORDS if w.lower() in (title or "").lower()), "")
        rows.append({
            "statement_id": "", "incident_id": incident_id, "institution": institution,
            "status": "", "statement_date": (published or "")[:10],
            "source_url": url if source_type == "OFFICIAL" else "", "reason": "",
            **{field: "" for field in SURVEY_FIELDS},
            "prevention_text": "", "prevention_keys": "", "recorded_by": "",
            "card_attack_type": card.get("attack_type") or "", "card_target": card.get("target") or "",
            "card_threat_actor": card.get("threat_actor") or "", "hint_title": title or "", "hint_url": url or "",
        })
        if len(rows) >= limit:
            break
    return rows


def write_candidates(path, limit=500):
    conn = get_connection()
    try:
        rows = candidates(conn, limit)
    finally:
        conn.close()
    fieldnames = list(COLUMNS) + ["card_attack_type", "card_target", "card_threat_actor", "hint_title", "hint_url"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def run():
    """Jalankan tahap alur D3 dan D4 dari CSV pernyataan lembaga."""
    print("\n==================================================")
    print("   ALUR D3/D4 - PERNYATAAN LEMBAGA")
    print("==================================================")
    started_at = get_timestamp()
    rows, errors = load_statements()
    conn = get_connection()
    try:
        store_statements(conn, rows, started_at)
        new_d3, new_d4, unknown = record_official(conn, rows)
        record_run(conn, "flows_d3_d4", started_at, new_d3 + new_d4)
    finally:
        conn.close()
    print(f"Pernyataan valid     : {len(rows)}")
    for message in errors:
        print(f"   ⚠️ {message}")
    for incident_id in unknown:
        print(f"   ⚠️ incident tidak dikenal: {incident_id}")
    print(f"Snapshot D3 baru     : {new_d3}")
    print(f"Catatan resmi D4 baru: {new_d4}")
    print("==================================================")
    print("   ✅ ALUR D3/D4 SELESAI")
    print("==================================================")


if __name__ == "__main__":
    run()
