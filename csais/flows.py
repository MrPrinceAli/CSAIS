"""Keluaran alur D1 - D4 dalam satu tabel agar bisa dibandingkan per incident.

Keempat alur menilai incident yang sama (kunci ``incident_id``) dan menulis
kolom yang sama ke ``flow_outputs``:

  D1  mesin: pipeline V0.1 - V0.7 atas semua berita (diisi tahap ini)
  D2  kartu inti + survei publik (sesuai / tidak sesuai / tidak tahu per kolom)
  D3  kartu inti + pernyataan lembaga atau kementerian
  D4  catatan resmi: hanya D3 yang dikonfirmasi atau dibantah, dengan
      reason statement lembaga; revisi menjadi entri baru (``supersedes``)

Tabel ini tambah-saja dan tidak ikut ``--reset``: setiap baris adalah
snapshot keluaran satu alur pada satu waktu. D1 hanya menambah baris bila
isinya berubah dibanding snapshot D1 terakhir incident itu (dibandingkan lewat
``output_hash``), sehingga riwayat tetap kecil. Incident yang hilang dari V0.5
(misalnya tergabung ke incident lain) diberi satu baris berstatus ``dihapus``.

Perbandingan untuk laporan dihitung oleh ``eval/compare_flows.py``; web
menampilkan snapshot terakhir tiap alur di halaman detail incident.
"""

import hashlib
import json
import os
from collections import Counter

from csais.config import PROJECT_ROOT
from csais.db import get_connection, get_timestamp
from csais.provenance import pipeline_stamp
from csais.schema import record_run

FLOWS = ("D1", "D2", "D3", "D4")
FIELDS = ("attack_type", "target", "threat_actor", "attack_date", "location", "target_group")
TIERS = ("peringatan_dini", "waspada", "rekomendasi_resmi", "peringatan_hoaks")
REMOVED = "dihapus"
NO_SCORE = "tanpa_skor"

# Panduan pencegahan dipakai bersama dengan web (web/lib/prevention.ts)
PREVENTION_FILE = os.path.join(PROJECT_ROOT, "web", "lib", "prevention.json")
with open(PREVENTION_FILE, encoding="utf-8") as _fh:
    PREVENTION = json.load(_fh)

# Kolom isi yang ikut dihitung dalam output_hash (urutan tetap)
_HASHED = FIELDS + ("field_status", "status", "tier", "prevention", "basis", "source_ref", "reason", "supersedes")


# --- Pencegahan ---
def prevention_for(group, types):
    """Kunci langkah dan kanal pelaporan; harus sama dengan preventionKeys di web."""
    by_type = PREVENTION["by_type"]
    alias = PREVENTION["alias"]
    steps = []
    if group in PREVENTION["by_group"]:
        steps.append(f"group:{group}")
    known = [t for t in (alias.get(t, t) for t in types) if t in by_type]
    pool = []
    for i, attack_type in enumerate(known or ["cyber_attack"]):
        take = 2 if i == 0 else 1
        pool.extend(f"type:{attack_type}:{j}" for j in range(min(take, len(by_type[attack_type]))))
    for key in pool:
        if len(steps) >= 3:
            break
        if key not in steps:
            steps.append(key)
    channels = []
    if group in PREVENTION["finance_groups"] or "investment_scam" in types:
        channels.append("ojk")
    if (
        any(t in PREVENTION["scam_types"] for t in types)
        or group in ("JOB_SEEKERS", "ELDERLY")
    ):
        channels.append("rekening")
    if any(t in PREVENTION["link_types"] for t in types):
        channels.append("konten")
    channels.append("patrol")
    return {"steps": steps, "channels": channels}


# --- Database ---
def create_tables(conn):
    """Buat tabel flow_outputs bila belum ada."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS flow_outputs (
            output_id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            flow TEXT NOT NULL,
            attack_type TEXT,
            target TEXT,
            threat_actor TEXT,
            attack_date TEXT,
            location TEXT,
            target_group TEXT,
            field_status TEXT,
            status TEXT NOT NULL,
            tier TEXT,
            prevention TEXT,
            basis TEXT,
            source_ref TEXT,
            reason TEXT,
            supersedes INTEGER,
            output_hash TEXT NOT NULL,
            pipeline_version TEXT,
            recorded_at TEXT NOT NULL
        )
        """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_flow_outputs_incident ON flow_outputs(incident_id, flow)"
    )
    conn.commit()


def _canonical(value):
    """JSON kanonis untuk kolom JSON; None tetap None."""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def output_hash(row):
    """SHA-256 isi satu keluaran (tanpa waktu, versi, dan output_id)."""
    payload = {key: row.get(key) for key in _HASHED}
    return hashlib.sha256(_canonical(payload).encode("ascii")).hexdigest()


def record_output(conn, incident_id, flow, row, recorded_at=None, version=None):
    """Tambahkan satu keluaran alur mana pun; kembalikan output_id.

    ``row`` berisi kolom FIELDS dan kolom isi lain; kolom JSON (field_status,
    prevention, basis) boleh berupa dict dan disimpan kanonis.
    """
    if flow not in FLOWS:
        raise ValueError(f"Alur tidak dikenal: {flow}")
    tier = row.get("tier")
    if tier is not None and tier not in TIERS:
        raise ValueError(f"Tingkat tidak dikenal: {tier}")
    stored = {key: row.get(key) for key in _HASHED}
    for key in ("field_status", "prevention", "basis"):
        if isinstance(stored[key], (dict, list)):
            stored[key] = _canonical(stored[key])
    digest = output_hash(stored)
    columns = ("incident_id", "flow") + _HASHED + ("output_hash", "pipeline_version", "recorded_at")
    values = (incident_id, flow) + tuple(stored[key] for key in _HASHED) + (
        digest,
        version or pipeline_stamp(),
        recorded_at or get_timestamp(),
    )
    cursor = conn.execute(
        f"INSERT INTO flow_outputs ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
        values,
    )
    return cursor.lastrowid


def latest_hashes(conn, flow):
    """Snapshot terakhir satu alur: incident_id -> (output_hash, status)."""
    cursor = conn.execute(
        """
        SELECT o.incident_id, o.output_hash, o.status
        FROM flow_outputs o
        JOIN (SELECT incident_id, MAX(output_id) AS last_id
              FROM flow_outputs WHERE flow = ? GROUP BY incident_id) m
          ON m.last_id = o.output_id
        """,
        (flow,),
    )
    return {incident_id: (digest, status) for incident_id, digest, status in cursor.fetchall()}


# --- D1 ---
def _clean(value):
    """Nilai kosong dan UNKNOWN menjadi None."""
    if value is None:
        return None
    text = str(value).strip()
    return None if not text or text.upper() == "UNKNOWN" else text


def attack_types(value):
    """Daftar jenis serangan dari kolom V0.5 ("ransomware, malware"), huruf kecil, urutan tetap."""
    return [t.strip().lower() for t in (value or "").split(",") if t.strip()]


def _has_table(conn, name):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()
    return row is not None


def main_groups(conn):
    """Kelompok sasaran terbanyak per incident (dari V0.3 artikel anggotanya)."""
    counts = {}
    cursor = conn.execute("""
        SELECT d.incident_id, x.target_group
        FROM v05_incident_documents d
        JOIN v03_information_extraction x ON x.article_id = d.article_id
        WHERE x.target_group IS NOT NULL AND x.target_group NOT IN ('', 'UNKNOWN')
        """)
    for incident_id, groups in cursor.fetchall():
        counter = counts.setdefault(incident_id, Counter())
        counter.update(g.strip() for g in groups.split(",") if g.strip())
    return {
        incident_id: min(counter.items(), key=lambda item: (-item[1], item[0]))[0]
        for incident_id, counter in counts.items()
    }


def d1_rows(conn):
    """Keluaran D1 per incident dari V0.5, V0.3, dan V0.7."""
    groups = main_groups(conn)
    trust = {}
    if _has_table(conn, "v07_trust"):
        cursor = conn.execute(
            "SELECT incident_id, score, level, document_count, domain_count FROM v07_trust"
        )
        trust = {row[0]: row[1:] for row in cursor.fetchall()}
    cursor = conn.execute("""
        SELECT incident_id, attack_type, target, threat_actor, attack_date, location,
               document_count
        FROM v05_incidents
        """)
    rows = {}
    for incident_id, attack_type, target, actor, attack_date, location, docs in cursor.fetchall():
        attack_type = _clean(attack_type)
        types = attack_types(attack_type)
        group = groups.get(incident_id)
        score, level, trust_docs, domains = trust.get(incident_id, (None, None, None, None))
        rows[incident_id] = {
            "attack_type": attack_type,
            "target": _clean(target),
            "threat_actor": _clean(actor),
            "attack_date": _clean(attack_date),
            "location": _clean(location),
            "target_group": group,
            "status": level or NO_SCORE,
            "tier": "peringatan_dini",
            "prevention": prevention_for(group or "", types),
            "basis": {
                "trust_score": score,
                "documents": trust_docs if trust_docs is not None else docs,
                "domains": domains,
            },
        }
    return rows


def record_d1(conn, recorded_at=None):
    """Catat snapshot D1 yang berubah; kembalikan (baru/berubah, dihapus, total)."""
    create_tables(conn)
    recorded_at = recorded_at or get_timestamp()
    version = pipeline_stamp()
    previous = latest_hashes(conn, "D1")
    current = d1_rows(conn)
    changed = 0
    for incident_id, row in current.items():
        stored = dict(row)
        for key in ("prevention", "basis"):
            stored[key] = _canonical(stored[key])
        known = previous.get(incident_id)
        if known and known[0] == output_hash(stored):
            continue
        record_output(conn, incident_id, "D1", stored, recorded_at, version)
        changed += 1
    removed = 0
    for incident_id, (_, status) in previous.items():
        if incident_id not in current and status != REMOVED:
            record_output(conn, incident_id, "D1", {"status": REMOVED}, recorded_at, version)
            removed += 1
    conn.commit()
    return changed, removed, len(current)


def flow_summary(conn):
    """Jumlah incident dengan snapshot per alur (tanpa yang dihapus)."""
    create_tables(conn)
    summary = {}
    for flow in FLOWS:
        summary[flow] = sum(
            1 for _, status in latest_hashes(conn, flow).values() if status != REMOVED
        )
    return summary


def run():
    """Jalankan tahap alur D1: catat keluaran mesin per incident."""
    print("\n==================================================")
    print("   ALUR D1 - KELUARAN MESIN PER INCIDENT")
    print("==================================================")
    started_at = get_timestamp()
    conn = get_connection()
    try:
        changed, removed, total = record_d1(conn)
        summary = flow_summary(conn)
        record_run(conn, "flows_d1", started_at, changed + removed)
    finally:
        conn.close()
    print(f"Incident D1          : {total}")
    print(f"Snapshot baru/berubah: {changed}")
    print(f"Ditandai dihapus     : {removed}")
    print("Incident per alur    : " + ", ".join(f"{k} {v}" for k, v in summary.items()))
    print("==================================================")
    print("   ✅ ALUR D1 SELESAI")
    print("==================================================")


if __name__ == "__main__":
    run()
