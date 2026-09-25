"""CSAIS - Cyber Social Attack Intelligence System.

V0.2 - Information Relevance Detection (deteksi relevansi informasi).

Menilai setiap artikel pada tabel ``articles`` yang belum dianalisis, memberi
label RELEVANT / UNCERTAIN / NOT_RELEVANT berdasarkan pencocokan kata kunci
(rule based) pada judul dan ringkasan, lalu menyimpan label, skor, dan tingkat
keyakinannya ke tabel ``v02_relevance``.
"""

import json
import os

from csais.config import DATABASE_FILE
from csais.db import get_connection, get_timestamp
from csais.provenance import pipeline_stamp
from csais.schema import ensure_column, record_run
from csais.text import drop_overlapping_keywords, find_keywords, normalize_text


# --- Konfigurasi ---
BATCH_SIZE = 500

RELEVANT_THRESHOLD = 0.60
UNCERTAIN_THRESHOLD = 0.40


# --- Kata kunci relevansi ---
# Daftar kata kunci disimpan di file JSON pada folder csais/data agar dapat
# diubah tanpa menyentuh kode. Penjelasan setiap kunci ada di csais/data/README.md.
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _load_keywords(name):
    """Baca satu file data kata kunci JSON dari folder csais/data."""
    with open(os.path.join(_DATA_DIR, name), encoding="utf-8") as fh:
        return json.load(fh)


_RELEVANCE = _load_keywords("relevance_keywords.json")

# Kata kunci serangan siber
ATTACK_KEYWORDS = _RELEVANCE["attack_keywords"]

# Indikator bahwa serangan benar-benar terjadi (bahasa kejadian/insiden)
EVENT_INDICATORS = _RELEVANCE["event_indicators"]

# Indikator pembahasan umum / bukan insiden (acara, edukasi, panduan)
NON_INCIDENT_INDICATORS = _RELEVANCE["non_incident_indicators"]

# Kata kunci serangan yang juga lazim di luar konteks siber: "worm" (cacing),
# "Trojan" (tim olahraga), "zero day" (film), "exploitation" (eksploitasi anak).
# Hanya dihitung bila teks juga memuat kata konteks siber.
WEAK_ATTACK_KEYWORDS = set(_RELEVANCE["weak_attack_keywords"])
CYBER_CONTEXT_KEYWORDS = _RELEVANCE["cyber_context_keywords"]


# --- Pencocokan kata kunci dan analisis relevansi ---
def find_matches(text, keywords):
    """Kata kunci yang muncul sebagai kata utuh, tanpa yang saling tumpang tindih.

    Pencocokan memakai batas kata sehingga "rce" tidak cocok dengan "forced",
    dan "phishing" tidak dihitung lagi bila "spear phishing" sudah cocok.
    """
    return drop_overlapping_keywords(find_keywords(text, keywords))


def analyze_relevance(title, summary):
    """Hitung label, skor, dan keyakinan relevansi dari judul dan ringkasan."""
    title_text = normalize_text(title)
    summary_text = normalize_text(summary)
    full_text = f"{title_text} {summary_text}".strip()

    if not full_text:
        return {
            "label": "NOT_RELEVANT",
            "score": 0.0,
            "confidence": 0.0,
            "method": "RULE_BASED",
            "attack_matches": [],
            "event_matches": [],
            "non_incident_matches": [],
        }

    attack_matches = find_matches(full_text, ATTACK_KEYWORDS)
    event_matches = find_matches(full_text, EVENT_INDICATORS)
    non_incident_matches = find_matches(full_text, NON_INCIDENT_INDICATORS)
    title_attack_matches = find_matches(title_text, ATTACK_KEYWORDS)
    title_event_matches = find_matches(title_text, EVENT_INDICATORS)

    # Kata kunci ambigu saja, tanpa konteks siber: bukan serangan siber
    if (
        attack_matches
        and all(keyword in WEAK_ATTACK_KEYWORDS for keyword in attack_matches)
        and not find_keywords(full_text, CYBER_CONTEXT_KEYWORDS)
    ):
        attack_matches = []
        title_attack_matches = []

    # Skor dasar
    score = 0.0

    # Ada kata kunci serangan siber
    if attack_matches:
        score += 0.40

    # Beberapa konsep serangan sekaligus
    if len(attack_matches) >= 2:
        score += 0.15
    if len(attack_matches) >= 4:
        score += 0.10

    # Bahasa kejadian/insiden nyata
    if event_matches:
        score += 0.20

    # Bukti lebih kuat bila muncul di judul
    if title_attack_matches:
        score += 0.10
    if title_event_matches:
        score += 0.10

    # Penalti untuk pembahasan umum; dua penanda atau lebih (misalnya artikel
    # imbauan "waspada ... jangan klik link video viral") dipenalti dua kali
    if non_incident_matches:
        score -= 0.15 * min(len(non_incident_matches), 2)

    # Normalisasi skor ke rentang 0..1
    if score < 0:
        score = 0.0
    if score > 1:
        score = 1.0

    # Klasifikasi
    if score >= RELEVANT_THRESHOLD:
        label = "RELEVANT"
    elif score >= UNCERTAIN_THRESHOLD:
        label = "UNCERTAIN"
    else:
        label = "NOT_RELEVANT"

    # Keyakinan: jarak skor dari titik tengah 0.50
    confidence = abs(score - 0.50) * 2

    return {
        "label": label,
        "score": round(score, 4),
        "confidence": round(confidence, 4),
        "method": "RULE_BASED",
        "attack_matches": attack_matches,
        "event_matches": event_matches,
        "non_incident_matches": non_incident_matches,
    }


# --- Database ---
def initialize_v02_database():
    """Buat tabel dan indeks V0.2 bila belum ada."""
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS v02_relevance (
            article_id INTEGER PRIMARY KEY,
            relevance_label TEXT,
            relevance_score REAL,
            relevance_confidence REAL,
            relevance_method TEXT,
            attack_matches TEXT,
            event_matches TEXT,
            non_incident_matches TEXT,
            analyzed_at TEXT
        )
        """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_v02_relevance_label
        ON v02_relevance(relevance_label)
        """)

    connection.commit()
    ensure_column(connection, "v02_relevance", "pipeline_version", "TEXT")
    connection.close()


def get_total_articles():
    """Jumlah seluruh artikel di tabel articles."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM articles")
    total = cursor.fetchone()[0]
    connection.close()
    return total


def get_analyzed_articles():
    """Jumlah artikel yang sudah dianalisis di tabel v02_relevance."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM v02_relevance")
    total = cursor.fetchone()[0]
    connection.close()
    return total


def get_next_batch():
    """Ambil batch artikel berikutnya yang belum dianalisis."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT a.article_id, a.title, a.summary, a.language
        FROM articles a
        LEFT JOIN v02_relevance v ON a.article_id = v.article_id
        WHERE v.article_id IS NULL
        ORDER BY a.article_id
        LIMIT ?
        """,
        (BATCH_SIZE,),
    )
    rows = cursor.fetchall()
    connection.close()
    return rows


def save_analysis(cursor, article_id, result):
    """Simpan hasil analisis satu artikel lewat cursor batch (tanpa commit)."""
    analyzed_at = get_timestamp()

    cursor.execute(
        """
        INSERT OR REPLACE INTO v02_relevance (
            article_id,
            relevance_label,
            relevance_score,
            relevance_confidence,
            relevance_method,
            attack_matches,
            event_matches,
            non_incident_matches,
            analyzed_at,
            pipeline_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            article_id,
            result["label"],
            result["score"],
            result["confidence"],
            result["method"],
            " | ".join(result["attack_matches"]),
            " | ".join(result["event_matches"]),
            " | ".join(result["non_incident_matches"]),
            analyzed_at,
            pipeline_stamp(),
        ),
    )


def process_batch(rows):
    """Analisis dan simpan satu batch artikel dalam satu transaksi."""
    processed = 0
    relevant = 0
    uncertain = 0
    not_relevant = 0
    connection = get_connection()
    cursor = connection.cursor()

    for row in rows:
        article_id = row[0]
        title = row[1] or ""
        summary = row[2] or ""
        language = row[3] or "unknown"

        result = analyze_relevance(title, summary)
        save_analysis(cursor, article_id, result)
        processed += 1

        if result["label"] == "RELEVANT":
            relevant += 1
        elif result["label"] == "UNCERTAIN":
            uncertain += 1
        else:
            not_relevant += 1

        # Tampilkan contoh hasil
        if processed <= 10:
            print(f"\n[{processed}] Article ID : {article_id}")
            print(f"    Language   : {language}")
            print(f"    Title      : {title[:120]}")
            print(f"    Relevance  : {result['label']}")
            print(f"    Score      : {result['score']:.2f}")
            print(f"    Confidence : {result['confidence']:.2f}")

    connection.commit()
    connection.close()
    return processed, relevant, uncertain, not_relevant


def get_v02_summary():
    """Jumlah artikel per label relevansi di tabel v02_relevance."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT relevance_label, COUNT(*)
        FROM v02_relevance
        GROUP BY relevance_label
        """)
    rows = cursor.fetchall()
    connection.close()

    summary = {"RELEVANT": 0, "UNCERTAIN": 0, "NOT_RELEVANT": 0}
    for label, count in rows:
        if label in summary:
            summary[label] = count
    return summary


# --- Program utama V0.2 ---
def run():
    """Jalankan deteksi relevansi untuk semua artikel yang belum dianalisis."""
    print("\n==================================================")
    print("   CSAIS V0.2 - RELEVANCE DETECTION")
    print("==================================================")

    # Periksa database
    if not os.path.exists(DATABASE_FILE):
        print("\n❌ Database tidak ditemukan:")
        print(f"   {DATABASE_FILE}")
        return

    started_at = get_timestamp()
    initialize_v02_database()

    # Ringkasan awal
    total_articles = get_total_articles()
    analyzed_articles = get_analyzed_articles()

    print(f"\nTotal articles      : {total_articles}")
    print(f"Sudah dianalisis    : {analyzed_articles}")
    print(f"Belum dianalisis    : {total_articles - analyzed_articles}")

    # Proses artikel per batch
    total_processed = 0

    while True:
        rows = get_next_batch()
        if not rows:
            break

        processed, relevant, uncertain, not_relevant = process_batch(rows)
        total_processed += processed

        print(f"\nBatch processed : {processed}")
        print(f"Total processed : {total_processed}")

    # Ringkasan akhir
    summary = get_v02_summary()

    print("\n==================================================")
    print("   V0.2 ANALYSIS SUMMARY")
    print("==================================================")

    print(f"\nTotal articles       : {total_articles}")
    print(f"Total analyzed       : {analyzed_articles + total_processed}")

    print(f"\nRELEVANT             : {summary['RELEVANT']}")
    print(f"UNCERTAIN            : {summary['UNCERTAIN']}")
    print(f"NOT_RELEVANT         : {summary['NOT_RELEVANT']}")

    connection = get_connection()
    record_run(connection, "v02_relevance_detection", started_at, total_processed)
    connection.close()

    print("\n==================================================")
    print("   ✅ V0.2 RELEVANCE DETECTION SELESAI")
    print("==================================================")


if __name__ == "__main__":
    run()
