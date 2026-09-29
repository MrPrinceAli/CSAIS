"""V0.7 - Trust Score: indeks kepercayaan awal per incident.

Rumus ini semula dihitung di aplikasi web saat halaman dirender
(web/lib/trust.ts). Dipindahkan ke pipeline agar skor tersimpan bersama versi
pipeline, bisa dibandingkan antar versi, dan ikut dalam paket hasil yang akan
dijangkarkan ke rantai. Web membaca tabel ``v07_trust`` bila ada dan hanya
menghitung sendiri sebagai cadangan.

Lima sinyal (bobot), semua dalam rentang 0..1:
  corroboration 0,30  jumlah sumber berbeda: (sumber - 1) / 4; sumber = domain
                      media asli, atau penerbit dari judul Google News
  independence  0,30  rata-rata evidence_independence_score V0.6;
                      0,35 untuk incident satu artikel (tidak ada pasangan)
  claim         0,20  keyakinan tertinggi field target V0.3 antar artikel
  content       0,10  porsi artikel yang teks penuhnya terambil
  clustering    0,10  incident_confidence V0.5
Tingkat: tinggi >= 0,72; sedang >= 0,45; selain itu rendah.

Skor di atas adalah skor mesin (``machine_score``). Setelah alur D2 - D4
selesai, ``apply_verification`` menggeser skor akhir dengan verifikasi:
  skor = (1 - b) * skor mesin + b * verifikasi
  D4 dikonfirmasi lembaga  verifikasi 1,0  b 0,60
  D4 dibantah lembaga      verifikasi 0,0  b 0,60
  D2 survei publik         verifikasi = porsi jawaban sesuai  b 0,25
  belum diverifikasi       b 0 (skor = skor mesin)
D1 tetap memakai tingkat skor mesin agar perbandingan antar alur adil. Seluruh incident dihitung ulang setiap run karena semua
masukannya bisa berubah (artikel baru, isi terambil, ekstraksi ulang).
"""

import json
from itertools import groupby

from csais.db import get_connection, get_timestamp
from csais.provenance import pipeline_stamp
from csais.schema import ensure_column, record_run
from csais.sources import AGGREGATOR_HOSTS, publisher_domains, source_identity

WEIGHTS = {
    "corroboration": 0.30,
    "independence": 0.30,
    "claim": 0.20,
    "content": 0.10,
    "clustering": 0.10,
}
SINGLE_SOURCE_INDEPENDENCE = 0.35  # artikel tunggal: tidak ada pasangan untuk dibandingkan
LEVEL_HIGH = 0.72
LEVEL_MEDIUM = 0.45
PARTS = tuple(WEIGHTS)
OFFICIAL_WEIGHT = 0.60
PUBLIC_WEIGHT = 0.25
VERIFICATION_COLUMNS = (
    ("machine_score", "REAL"),
    ("verification", "REAL"),
    ("verification_weight", "REAL"),
    ("verification_source", "TEXT"),
)


def _clamp(value):
    return min(1.0, max(0.0, float(value or 0.0)))


def score_incident(independence, domains, docs, target_confidence, content_share, clustering):
    """Hitung skor, tingkat, dan nilai tiap sinyal; harus sama dengan web/lib/trust.ts."""
    parts = {
        "corroboration": _clamp((domains - 1) / 4),
        "independence": _clamp(independence) if docs >= 2 else SINGLE_SOURCE_INDEPENDENCE,
        "claim": _clamp(target_confidence),
        "content": _clamp(content_share),
        "clustering": _clamp(clustering),
    }
    if docs >= 2 and independence is None:
        parts["independence"] = 0.0
    score = sum(parts[key] * WEIGHTS[key] for key in PARTS)
    return {"score": round(score, 4), "level": level_of(score), "parts": parts}


# --- Database ---
def create_tables(conn):
    """Buat tabel v07_trust bila belum ada."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS v07_trust (
            incident_id TEXT PRIMARY KEY,
            score REAL NOT NULL,
            level TEXT NOT NULL,
            corroboration REAL NOT NULL,
            independence REAL NOT NULL,
            claim REAL NOT NULL,
            content REAL NOT NULL,
            clustering REAL NOT NULL,
            document_count INTEGER NOT NULL,
            domain_count INTEGER NOT NULL,
            pipeline_version TEXT NOT NULL,
            computed_at TEXT NOT NULL
        )
        """)
    conn.commit()
    for column, definition in VERIFICATION_COLUMNS:
        ensure_column(conn, "v07_trust", column, definition)


_DOCUMENT_SQL = """
    SELECT d.incident_id, a.content_status, e.source_domain,
           COALESCE(a.resolved_url, a.article_url), a.title, a.source_name,
           e.evidence_independence_score, x.target, x.field_confidence
    FROM v05_incident_documents d
    JOIN articles a ON a.article_id = d.article_id
    LEFT JOIN v06_evidence e
        ON e.incident_id = d.incident_id AND e.article_id = d.article_id
    LEFT JOIN v03_information_extraction x ON x.article_id = d.article_id
    ORDER BY d.incident_id
"""


def _target_confidence(target, field_confidence):
    """Keyakinan field target dari JSON field_confidence; 0 bila target tidak ada."""
    if not target or target == "UNKNOWN" or not field_confidence:
        return 0.0
    try:
        return float(json.loads(field_confidence).get("target", 0.0) or 0.0)
    except (ValueError, TypeError, AttributeError):
        return 0.0


def incident_inputs(rows, publishers=None):
    """Masukan skor dari baris artikel satu incident (hasil _DOCUMENT_SQL).

    Domain berbeda dihitung dari identitas sumber: domain media asli, atau
    penerbit dari akhiran judul Google News (``sources.source_identity``).
    """
    docs = 0
    with_content = 0
    domains = set()
    independence_values = []
    best_target = 0.0
    for _, content_status, source_domain, url, title, source_name, independence, target, confidence in rows:
        docs += 1
        if content_status == "ok":
            with_content += 1
        domain = source_identity(url, title, publishers)
        if not domain or domain in AGGREGATOR_HOSTS:
            domain = (source_domain if source_domain not in AGGREGATOR_HOSTS else None) or domain or source_name or ""
        if domain:
            domains.add(domain)
        if independence is not None:
            independence_values.append(float(independence))
        best_target = max(best_target, _target_confidence(target, confidence))
    average = sum(independence_values) / len(independence_values) if independence_values else None
    return {
        "independence": average,
        "domains": len(domains),
        "docs": docs,
        "target_confidence": best_target,
        "content_share": with_content / docs if docs else 0.0,
    }


def compute_all(conn):
    """Hitung ulang skor seluruh incident; kembalikan jumlah incident yang dinilai."""
    create_tables(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT incident_id, incident_confidence FROM v05_incidents")
    clustering = {incident_id: confidence or 0.0 for incident_id, confidence in cursor.fetchall()}

    stamp = pipeline_stamp()
    now = get_timestamp()
    rows_out = []
    publishers = publisher_domains(conn)
    cursor.execute(_DOCUMENT_SQL)
    for incident_id, rows in groupby(cursor.fetchall(), key=lambda row: row[0]):
        if incident_id not in clustering:
            continue
        inputs = incident_inputs(list(rows), publishers)
        result = score_incident(
            inputs["independence"],
            inputs["domains"],
            inputs["docs"],
            inputs["target_confidence"],
            inputs["content_share"],
            clustering[incident_id],
        )
        parts = result["parts"]
        rows_out.append((
            incident_id, result["score"], result["level"],
            round(parts["corroboration"], 4), round(parts["independence"], 4),
            round(parts["claim"], 4), round(parts["content"], 4), round(parts["clustering"], 4),
            inputs["docs"], inputs["domains"], stamp, now,
        ))

    cursor.execute("DELETE FROM v07_trust")
    cursor.executemany(
        """
        INSERT INTO v07_trust (
            incident_id, score, level, corroboration, independence, claim, content,
            clustering, document_count, domain_count, pipeline_version, computed_at, machine_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [row + (row[1],) for row in rows_out],
    )
    conn.commit()
    return len(rows_out)


def level_of(score):
    return "tinggi" if score >= LEVEL_HIGH else "sedang" if score >= LEVEL_MEDIUM else "rendah"


def verification_signal(d2, d4):
    """(nilai, bobot, sumber) verifikasi dari snapshot D2/D4 terakhir; None bila belum ada."""
    if d4 and d4.get("tier") == "rekomendasi_resmi":
        return 1.0, OFFICIAL_WEIGHT, "D4"
    if d4 and d4.get("tier") == "peringatan_hoaks":
        return 0.0, OFFICIAL_WEIGHT, "D4"
    if d2 and d2.get("status") in ("sesuai", "tidak_sesuai"):
        try:
            counts = json.loads(d2.get("basis") or "{}").get("counts", {})
        except ValueError:
            counts = {}
        agree = sum(c.get("sesuai", 0) for c in counts.values())
        decisive = agree + sum(c.get("tidak_sesuai", 0) for c in counts.values())
        if decisive:
            return round(agree / decisive, 4), PUBLIC_WEIGHT, "D2"
    return None


def apply_verification(conn):
    """Geser skor akhir v07_trust dengan verifikasi D2/D4; kembalikan jumlah incident yang tergeser."""
    from csais.official import latest_rows

    create_tables(conn)
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'flow_outputs'").fetchone()
    d2 = latest_rows(conn, "D2") if exists else {}
    d4 = latest_rows(conn, "D4") if exists else {}
    rows = conn.execute("SELECT incident_id, COALESCE(machine_score, score) FROM v07_trust").fetchall()
    updates, shifted = [], 0
    for incident_id, machine in rows:
        signal = verification_signal(d2.get(incident_id), d4.get(incident_id))
        if signal:
            value, weight, source = signal
            final = round((1 - weight) * machine + weight * value, 4)
            shifted += 1
        else:
            value = weight = source = None
            final = machine
        updates.append((final, level_of(final), machine, value, weight, source, incident_id))
    conn.executemany(
        """
        UPDATE v07_trust SET score = ?, level = ?, machine_score = ?, verification = ?,
            verification_weight = ?, verification_source = ? WHERE incident_id = ?
        """,
        updates,
    )
    conn.commit()
    return shifted


def verification_run():
    """Tahap pipeline: skor akhir = skor mesin digeser verifikasi publik dan lembaga."""
    print("\n==================================================")
    print("   V0.7 VERIFIKASI - SKOR AKHIR")
    print("==================================================")
    started_at = get_timestamp()
    conn = get_connection()
    try:
        shifted = apply_verification(conn)
        summary = level_summary(conn)
        record_run(conn, "v07_verification", started_at, shifted)
    finally:
        conn.close()
    print(f"Incident tergeser verifikasi: {shifted}")
    for level in ("tinggi", "sedang", "rendah"):
        print(f"   {level:8s} {summary.get(level, 0)}")
    print("==================================================")


def level_summary(conn):
    """Jumlah incident per tingkat kepercayaan."""
    cursor = conn.cursor()
    cursor.execute("SELECT level, COUNT(*) FROM v07_trust GROUP BY level")
    return dict(cursor.fetchall())


def run():
    """Jalankan V0.7: hitung ulang indeks kepercayaan seluruh incident."""
    print("\n==================================================")
    print("   V0.7 TRUST SCORE")
    print("==================================================")
    started_at = get_timestamp()
    conn = get_connection()
    try:
        total = compute_all(conn)
        summary = level_summary(conn)
        record_run(conn, "v07_trust_score", started_at, total)
    finally:
        conn.close()
    print(f"Incident dinilai : {total}")
    for level in ("tinggi", "sedang", "rendah"):
        print(f"   {level:8s} {summary.get(level, 0)}")
    print("==================================================")
    print("   ✅ V0.7 TRUST SCORE SELESAI")
    print("==================================================")


if __name__ == "__main__":
    run()
