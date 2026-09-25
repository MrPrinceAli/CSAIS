"""V0.6 - Evidence Correlation.

CSAIS - Cyber Social Attack Intelligence System.

Fungsi:
  1. Mengambil incident hasil V0.5
  2. Mengambil seluruh artikel dalam incident
  3. Membandingkan hubungan antar sumber
  4. Mendeteksi kemungkinan duplicate / reproduced evidence
  5. Mengidentifikasi kemungkinan independent evidence
  6. Menghasilkan evidence independence score

IMPORTANT:
V0.6 tidak menentukan apakah informasi benar atau salah.

V0.6 menentukan:
  - apakah evidence kemungkinan duplicate
  - apakah evidence kemungkinan reproduced
  - apakah evidence kemungkinan independent
  - seberapa kuat hubungan antar evidence
"""

import hashlib
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import urlparse

from csais.db import get_connection, get_timestamp
from csais.provenance import pipeline_stamp
from csais.schema import ensure_column, ensure_evidence_uids, evidence_uid, record_run
from csais.text import jaccard_index


# --- Konfigurasi ---
BATCH_SIZE = 100
TEXT_SIMILARITY_THRESHOLD = 0.80
HIGH_SIMILARITY_THRESHOLD = 0.90
LOW_SIMILARITY_THRESHOLD = 0.40
TITLE_SIMILARITY_THRESHOLD = 0.85
MAX_TEXT_LENGTH = 10000


# --- Pengolahan teks ---
def clean_text(text):
    """Huruf kecil, buang URL, token www. dan tanda baca, lalu rapatkan spasi.

    Berbeda dengan ``csais.text.normalize_text`` yang hanya merapikan spasi.
    """
    if text is None:
        return ""
    text = str(text).lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"www\.\S+", " ", text)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text):
    """Himpunan token (panjang > 2) dari teks yang sudah dibersihkan."""
    normalized = clean_text(text)
    if not normalized:
        return set()
    return {token for token in normalized.split() if len(token) > 2}


def jaccard_similarity(text_a, text_b):
    """Jaccard similarity antara token dua teks."""
    return jaccard_index(tokenize(text_a), tokenize(text_b))


def sequence_similarity(text_a, text_b):
    """Rasio SequenceMatcher pada teks bersih, dipotong MAX_TEXT_LENGTH."""
    a = clean_text(text_a)
    b = clean_text(text_b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if len(a) > MAX_TEXT_LENGTH:
        a = a[:MAX_TEXT_LENGTH]
    if len(b) > MAX_TEXT_LENGTH:
        b = b[:MAX_TEXT_LENGTH]
    return SequenceMatcher(None, a, b).ratio()


def calculate_text_similarity(text_a, text_b):
    """Gabungan 50% Jaccard dan 50% sequence similarity."""
    jaccard = jaccard_similarity(text_a, text_b)
    sequence = sequence_similarity(text_a, text_b)
    return (jaccard * 0.50) + (sequence * 0.50)


def calculate_title_similarity(title_a, title_b):
    """Kemiripan judul memakai sequence similarity."""
    return sequence_similarity(title_a, title_b)


def extract_domain(url):
    """Ambil domain (tanpa awalan www.) dari URL; kosong bila gagal."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        domain = (parsed.netloc or "").lower()
        return re.sub(r"^www\.", "", domain)
    except Exception:
        return ""


def generate_content_fingerprint(title, summary, content):
    """SHA-256 dari gabungan judul, ringkasan, dan isi yang sudah dibersihkan."""
    combined = " ".join([title or "", summary or "", content or ""])
    normalized = clean_text(combined)
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# --- Database ---
def create_tables(conn):
    """Buat tabel dan indeks V0.6 bila belum ada."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS v06_evidence (
            evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            article_id INTEGER NOT NULL,
            source_name TEXT,
            source_type TEXT,
            source_domain TEXT,
            evidence_type TEXT,
            evidence_independence_score REAL,
            evidence_confidence REAL,
            publication_date TEXT,
            content_fingerprint TEXT,
            analyzed_at TEXT,
            UNIQUE (incident_id, article_id)
        )
        """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS v06_source_relations (
            relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            article_id_a INTEGER NOT NULL,
            article_id_b INTEGER NOT NULL,
            relation_type TEXT,
            text_similarity REAL,
            title_similarity REAL,
            domain_same INTEGER,
            time_difference_hours REAL,
            independence_score REAL,
            relation_confidence REAL,
            analyzed_at TEXT,
            UNIQUE (incident_id, article_id_a, article_id_b)
        )
        """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS v06_processed_incidents (
            incident_id TEXT PRIMARY KEY,
            processed_at TEXT NOT NULL
        )
        """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_v06_evidence_incident "
        "ON v06_evidence(incident_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_v06_evidence_article "
        "ON v06_evidence(article_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_v06_relation_incident "
        "ON v06_source_relations(incident_id)"
    )
    conn.commit()
    # ID deterministik bukti dan versi pipeline (migrasi untuk tabel lama)
    ensure_column(conn, "v06_evidence", "evidence_uid", "TEXT")
    ensure_column(conn, "v06_evidence", "pipeline_version", "TEXT")
    filled = ensure_evidence_uids(conn)
    if filled:
        print(f"\n[*] evidence_uid diisi untuk {filled} bukti lama.")


def get_next_incident_batch(conn):
    """Ambil incident V0.5 yang belum diproses V0.6, maksimal BATCH_SIZE."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT i.incident_id
        FROM v05_incidents i
        LEFT JOIN v06_processed_incidents p ON i.incident_id = p.incident_id
        WHERE p.incident_id IS NULL
        ORDER BY i.incident_id
        LIMIT ?
        """,
        (BATCH_SIZE,),
    )
    return [row[0] for row in cursor.fetchall()]


def get_incident_documents(conn, incident_id):
    """Ambil seluruh artikel dalam satu incident, urut tanggal terbit."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT d.article_id, a.source_name, a.source_type, a.source_url,
               a.title, a.summary, a.content, a.published_date, a.article_url,
               a.article_uid
        FROM v05_incident_documents d
        INNER JOIN articles a ON d.article_id = a.article_id
        WHERE d.incident_id = ?
        ORDER BY a.published_date ASC, a.article_id ASC
        """,
        (incident_id,),
    )
    return cursor.fetchall()


# --- Waktu ---
def parse_datetime(value):
    """Parse tanggal ISO 8601 atau YYYY-MM-DD menjadi datetime UTC."""
    if not value:
        return None
    value = str(value).strip()
    if not value:
        return None
    # Format ISO
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        pass
    # Tanggal sederhana
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
        return parsed.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    return None


def calculate_time_difference_hours(date_a, date_b):
    """Selisih absolut dua tanggal dalam jam; None bila salah satu gagal parse."""
    datetime_a = parse_datetime(date_a)
    datetime_b = parse_datetime(date_b)
    if datetime_a is None or datetime_b is None:
        return None
    difference = datetime_a - datetime_b
    return abs(difference.total_seconds() / 3600.0)


# --- Klasifikasi ---
def classify_relation(
    text_similarity, title_similarity, domain_same, time_difference_hours
):
    """Klasifikasi hubungan dua artikel beserta confidence-nya."""
    # Kemiripan sangat tinggi
    if text_similarity >= HIGH_SIMILARITY_THRESHOLD:
        return "LIKELY_DUPLICATE", 0.95
    # Reproduced / syndicated
    if (
        text_similarity >= TEXT_SIMILARITY_THRESHOLD
        and title_similarity >= TITLE_SIMILARITY_THRESHOLD
    ):
        return "LIKELY_REPRODUCED", 0.90
    # Judul sangat mirip + teks cukup mirip
    if title_similarity >= TITLE_SIMILARITY_THRESHOLD and text_similarity >= 0.65:
        return "POSSIBLE_REPRODUCED", 0.80
    # Domain sama + teks mirip
    if domain_same and text_similarity >= 0.70:
        return "POSSIBLE_DUPLICATE", 0.80
    # Kemiripan rendah
    if text_similarity <= LOW_SIMILARITY_THRESHOLD:
        return "LIKELY_INDEPENDENT", 0.75
    return "UNCERTAIN_RELATION", 0.50


def calculate_independence_score(text_similarity, title_similarity, domain_same):
    """Skor independensi 0-1, dikurangi kemiripan teks, judul, dan domain sama."""
    score = 1.0
    score -= text_similarity * 0.60
    score -= title_similarity * 0.25
    if domain_same:
        score -= 0.10
    return max(0.0, min(1.0, score))


# --- Penyimpanan ---
def save_source_relation(
    conn,
    incident_id,
    article_id_a,
    article_id_b,
    relation_type,
    text_similarity,
    title_similarity,
    domain_same,
    time_difference_hours,
    independence_score,
    relation_confidence,
):
    """Simpan relasi dua artikel; id diurutkan agar pasangan selalu unik."""
    if article_id_a > article_id_b:
        article_id_a, article_id_b = article_id_b, article_id_a
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO v06_source_relations (
            incident_id, article_id_a, article_id_b, relation_type,
            text_similarity, title_similarity, domain_same,
            time_difference_hours, independence_score, relation_confidence,
            analyzed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            incident_id,
            article_id_a,
            article_id_b,
            relation_type,
            text_similarity,
            title_similarity,
            int(domain_same),
            time_difference_hours,
            independence_score,
            relation_confidence,
            get_timestamp(),
        ),
    )


def save_evidence(
    conn,
    incident_id,
    article,
    evidence_type,
    independence_score,
    evidence_confidence,
    fingerprint,
):
    """Simpan record evidence untuk satu artikel dalam incident."""
    (
        article_id,
        source_name,
        source_type,
        source_url,
        title,
        summary,
        content,
        published_date,
        article_url,
        uid,
    ) = article
    source_domain = extract_domain(article_url or source_url)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO v06_evidence (
            incident_id, article_id, source_name, source_type, source_domain,
            evidence_type, evidence_independence_score, evidence_confidence,
            publication_date, content_fingerprint, analyzed_at,
            evidence_uid, pipeline_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            incident_id,
            article_id,
            source_name,
            source_type,
            source_domain,
            evidence_type,
            independence_score,
            evidence_confidence,
            published_date,
            fingerprint,
            get_timestamp(),
            evidence_uid(incident_id, uid or article_id),
            pipeline_stamp(),
        ),
    )


def determine_evidence_types(relations):
    """Kumpulkan label evidence per artikel dari daftar relasi."""
    evidence_types = {}
    for relation in relations:
        article_a = relation["article_id_a"]
        article_b = relation["article_id_b"]
        relation_type = relation["relation_type"]
        if article_a not in evidence_types:
            evidence_types[article_a] = []
        if article_b not in evidence_types:
            evidence_types[article_b] = []
        if relation_type in ["LIKELY_DUPLICATE", "POSSIBLE_DUPLICATE"]:
            evidence_types[article_a].append("DUPLICATE_OR_REPEATED")
            evidence_types[article_b].append("DUPLICATE_OR_REPEATED")
        elif relation_type in ["LIKELY_REPRODUCED", "POSSIBLE_REPRODUCED"]:
            evidence_types[article_a].append("REPRODUCED_OR_SYNDICATED")
            evidence_types[article_b].append("REPRODUCED_OR_SYNDICATED")
        elif relation_type == "LIKELY_INDEPENDENT":
            evidence_types[article_a].append("INDEPENDENT_SUPPORT")
            evidence_types[article_b].append("INDEPENDENT_SUPPORT")
    return evidence_types


# --- Pemrosesan ---
def process_incident(conn, incident_id):
    """Bandingkan semua pasangan artikel dalam incident dan simpan hasilnya."""
    articles = get_incident_documents(conn, incident_id)
    if not articles:
        return {"articles": 0, "relations": 0, "independent": 0, "reproduced": 0}

    # Cache data artikel
    article_data = {}
    for article in articles:
        (
            article_id,
            source_name,
            source_type,
            source_url,
            title,
            summary,
            content,
            published_date,
            article_url,
            _uid,
        ) = article
        # Pada data lama kolom content berisi salinan summary; jangan dihitung dua kali
        parts = [title or "", summary or ""]
        if content and content != summary:
            parts.append(content)
        text = " ".join(parts)
        fingerprint = generate_content_fingerprint(title, summary, content)
        domain = extract_domain(article_url or source_url)
        article_data[article_id] = {
            "article": article,
            "text": text,
            "fingerprint": fingerprint,
            "domain": domain,
        }

    # Perbandingan berpasangan
    relations = []
    article_ids = list(article_data.keys())
    for i in range(len(article_ids)):
        article_id_a = article_ids[i]
        data_a = article_data[article_id_a]
        for j in range(i + 1, len(article_ids)):
            article_id_b = article_ids[j]
            data_b = article_data[article_id_b]

            text_similarity = calculate_text_similarity(data_a["text"], data_b["text"])
            title_a = data_a["article"][4]
            title_b = data_b["article"][4]
            title_similarity = calculate_title_similarity(title_a, title_b)
            domain_same = (
                bool(data_a["domain"])
                and bool(data_b["domain"])
                and data_a["domain"] == data_b["domain"]
            )
            date_a = data_a["article"][7]
            date_b = data_b["article"][7]
            time_difference_hours = calculate_time_difference_hours(date_a, date_b)

            relation_type, relation_confidence = classify_relation(
                text_similarity, title_similarity, domain_same, time_difference_hours
            )
            independence_score = calculate_independence_score(
                text_similarity, title_similarity, domain_same
            )
            save_source_relation(
                conn,
                incident_id,
                article_id_a,
                article_id_b,
                relation_type,
                text_similarity,
                title_similarity,
                domain_same,
                time_difference_hours,
                independence_score,
                relation_confidence,
            )
            relations.append(
                {
                    "article_id_a": article_id_a,
                    "article_id_b": article_id_b,
                    "relation_type": relation_type,
                    "independence_score": independence_score,
                }
            )

    evidence_types = determine_evidence_types(relations)

    # Simpan evidence per artikel
    independent_count = 0
    reproduced_count = 0
    for article_id in article_ids:
        data = article_data[article_id]
        types = evidence_types.get(article_id, [])
        if not types:
            evidence_type = "SINGLE_SOURCE"
            independence_score = 1.0
            evidence_confidence = 0.60
        elif "INDEPENDENT_SUPPORT" in types:
            evidence_type = "INDEPENDENT_SUPPORT"
            independence_score = 0.80
            evidence_confidence = 0.75
            independent_count += 1
        elif "REPRODUCED_OR_SYNDICATED" in types:
            evidence_type = "REPRODUCED_OR_SYNDICATED"
            independence_score = 0.30
            evidence_confidence = 0.75
            reproduced_count += 1
        elif "DUPLICATE_OR_REPEATED" in types:
            evidence_type = "DUPLICATE_OR_REPEATED"
            independence_score = 0.10
            evidence_confidence = 0.85
            reproduced_count += 1
        else:
            evidence_type = "UNCERTAIN"
            independence_score = 0.50
            evidence_confidence = 0.50
        save_evidence(
            conn,
            incident_id,
            data["article"],
            evidence_type,
            independence_score,
            evidence_confidence,
            data["fingerprint"],
        )

    # Tandai incident sudah diproses
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO v06_processed_incidents (incident_id, processed_at)
        VALUES (?, ?)
        """,
        (incident_id, get_timestamp()),
    )
    return {
        "articles": len(articles),
        "relations": len(relations),
        "independent": independent_count,
        "reproduced": reproduced_count,
    }


def process_batch(conn, incident_ids):
    """Proses satu batch incident; error per incident dicetak lalu dilewati."""
    batch_incidents = 0
    batch_articles = 0
    batch_relations = 0
    batch_independent = 0
    batch_reproduced = 0
    for incident_id in incident_ids:
        try:
            result = process_incident(conn, incident_id)
            batch_incidents += 1
            batch_articles += result["articles"]
            batch_relations += result["relations"]
            batch_independent += result["independent"]
            batch_reproduced += result["reproduced"]
        except Exception as error:
            print("\n⚠️ ERROR")
            print(f"    Incident ID : {incident_id}")
            print(f"    Error       : {error}")
            continue
    conn.commit()
    return (
        batch_incidents,
        batch_articles,
        batch_relations,
        batch_independent,
        batch_reproduced,
    )


def database_summary(conn):
    """Hitung ringkasan status database V0.5 dan V0.6."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM v05_incidents")
    total_incidents = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM v06_processed_incidents")
    processed_incidents = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM v06_evidence")
    total_evidence = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM v06_source_relations")
    total_relations = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM v06_evidence WHERE evidence_type = 'INDEPENDENT_SUPPORT'"
    )
    independent_evidence = cursor.fetchone()[0]
    cursor.execute("""
        SELECT COUNT(*) FROM v06_evidence
        WHERE evidence_type IN ('REPRODUCED_OR_SYNDICATED', 'DUPLICATE_OR_REPEATED')
        """)
    reproduced_evidence = cursor.fetchone()[0]
    remaining = total_incidents - processed_incidents
    if remaining < 0:
        remaining = 0
    return (
        total_incidents,
        processed_incidents,
        remaining,
        total_evidence,
        total_relations,
        independent_evidence,
        reproduced_evidence,
    )


def run():
    """Jalankan V0.6: korelasi evidence untuk semua incident V0.5 yang tersisa."""
    print("\n==================================================")
    print("   V0.6 EVIDENCE CORRELATION")
    print("==================================================")

    started_at = get_timestamp()
    conn = get_connection()
    create_tables(conn)

    (
        total_incidents,
        processed_incidents,
        remaining,
        total_evidence,
        total_relations,
        independent_evidence,
        reproduced_evidence,
    ) = database_summary(conn)

    print("\n==================================================")
    print("   V0.6 DATABASE STATUS")
    print("==================================================")
    print(f"V05 incidents       : {total_incidents}")
    print(f"Processed incidents : {processed_incidents}")
    print(f"Remaining           : {remaining}")
    print(f"Evidence records    : {total_evidence}")
    print(f"Source relations    : {total_relations}")
    print(f"Independent         : {independent_evidence}")
    print(f"Reproduced          : {reproduced_evidence}")
    print("==================================================")

    total_incidents_processed = 0
    total_articles_processed = 0
    total_relations_created = 0
    total_independent_created = 0
    total_reproduced_created = 0

    try:
        while True:
            incident_ids = get_next_incident_batch(conn)
            if not incident_ids:
                break

            (
                batch_incidents,
                batch_articles,
                batch_relations,
                batch_independent,
                batch_reproduced,
            ) = process_batch(conn, incident_ids)

            total_incidents_processed += batch_incidents
            total_articles_processed += batch_articles
            total_relations_created += batch_relations
            total_independent_created += batch_independent
            total_reproduced_created += batch_reproduced

            (
                current_incidents,
                current_processed,
                current_remaining,
                current_evidence,
                current_relations,
                current_independent,
                current_reproduced,
            ) = database_summary(conn)

            print("\n--------------------------------------------------")
            print(f"Batch incidents : {batch_incidents}")
            print(f"Batch articles  : {batch_articles}")
            print(f"Batch relations : {batch_relations}")
            print(f"Total incidents : {current_processed}")
            print(f"Total evidence  : {current_evidence}")
            print(f"Total relations : {current_relations}")
            print(f"Independent     : {current_independent}")
            print(f"Reproduced      : {current_reproduced}")
            print(f"Remaining       : {current_remaining}")
            print("--------------------------------------------------")
    except KeyboardInterrupt:
        # Dihentikan user
        conn.commit()
        print("\n\n⚠️ V0.6 dihentikan oleh user.")
        print("Data batch yang sudah selesai telah disimpan.")
    finally:
        conn.close()

    # Ringkasan akhir
    conn = get_connection()
    (
        final_incidents,
        final_processed,
        final_remaining,
        final_evidence,
        final_relations,
        final_independent,
        final_reproduced,
    ) = database_summary(conn)
    record_run(conn, "v06_evidence_correlation", started_at, total_incidents_processed)
    conn.close()

    print("\n==================================================")
    print("   V0.6 ANALYSIS SUMMARY")
    print("==================================================")
    print(f"V05 incidents       : {final_incidents}")
    print(f"Processed incidents : {final_processed}")
    print(f"Remaining           : {final_remaining}")
    print(f"Evidence records    : {final_evidence}")
    print(f"Source relations    : {final_relations}")
    print(f"Independent         : {final_independent}")
    print(f"Reproduced          : {final_reproduced}")
    print(f"Incidents processed this run            : {total_incidents_processed}")
    print(f"Articles processed this run            : {total_articles_processed}")
    print(f"Relations created this run            : {total_relations_created}")
    print("==================================================")
    if final_remaining == 0:
        print("   ✅ V0.6 EVIDENCE CORRELATION SELESAI")
    else:
        print("   ⏸️ V0.6 BELUM SELESAI")
        print("   Jalankan kembali untuk melanjutkan.")
    print("==================================================")


if __name__ == "__main__":
    run()
