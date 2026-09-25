"""V0.5 - Incident Clustering.

CSAIS - Cyber Social Attack Intelligence System.

Fungsi:
  1. Mengambil hasil V0.3 Information Extraction
  2. Menggunakan canonical entity dari V0.4
  3. Mengelompokkan artikel yang kemungkinan membahas incident cyber attack
     yang sama
  4. Membuat incident baru jika tidak ditemukan incident yang sesuai
  5. Menyimpan hubungan article -> incident
  6. Menandai article sebagai sudah diproses

IMPORTANT:
Satu article_id hanya boleh diproses satu kali. Jangan menggunakan
v05_incident_documents sebagai satu-satunya indikator bahwa article sudah
diproses. Karena itu digunakan tabel v05_processed_articles.
"""

import hashlib
from datetime import datetime, timezone

from csais.db import get_connection, get_timestamp
from csais.text import jaccard_index, normalize_text


# --- Konfigurasi ---
BATCH_SIZE = 500
INCIDENT_SIMILARITY_THRESHOLD = 0.70
DATE_WINDOW_DAYS = 14

# Bobot similarity
TARGET_WEIGHT = 0.30
ATTACK_TYPE_WEIGHT = 0.20
THREAT_ACTOR_WEIGHT = 0.20
LOCATION_WEIGHT = 0.10
ATTACK_DATE_WEIGHT = 0.10
ATTACK_METHOD_WEIGHT = 0.10

# Tipe entity dari V0.4
TARGET_ENTITY_TYPE = "ORGANIZATION"
THREAT_ACTOR_ENTITY_TYPE = "THREAT_ACTOR"
LOCATION_ENTITY_TYPE = "LOCATION"

UNKNOWN_VALUES = {"", "unknown", "none", "null", "n/a", "na", "-"}


# --- Normalisasi nilai ---
def is_unknown(value):
    """True jika nilai None atau termasuk UNKNOWN_VALUES setelah dinormalisasi."""
    if value is None:
        return True
    return normalize_text(value) in UNKNOWN_VALUES


def normalize_value(value):
    """Normalisasi teks; nilai unknown menjadi None."""
    if is_unknown(value):
        return None
    return normalize_text(value)


def parse_date(value):
    """Parse tanggal ISO 8601 atau YYYY-MM-DD menjadi datetime UTC."""
    if is_unknown(value):
        return None
    value = str(value).strip()

    # Format ISO
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        pass

    # Hanya tanggal
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
        return parsed.replace(tzinfo=timezone.utc)
    except Exception:
        pass

    return None


# --- Similarity ---
def calculate_date_similarity(date_a, date_b):
    """Kemiripan tanggal, turun linear menjadi 0 setelah DATE_WINDOW_DAYS."""
    parsed_a = parse_date(date_a)
    parsed_b = parse_date(date_b)
    if parsed_a is None or parsed_b is None:
        return 0.0
    difference = abs((parsed_a - parsed_b).total_seconds())
    difference_days = difference / 86400.0
    if difference_days > DATE_WINDOW_DAYS:
        return 0.0
    return 1.0 - (difference_days / DATE_WINDOW_DAYS)


def calculate_field_similarity(value_a, value_b):
    """Kemiripan dua nilai teks: exact match 1.0, selain itu Jaccard token."""
    normalized_a = normalize_value(value_a)
    normalized_b = normalize_value(value_b)
    # Salah satu (atau keduanya) unknown: tidak dapat dibandingkan.
    if normalized_a is None or normalized_b is None:
        return None
    if normalized_a == normalized_b:
        return 1.0
    return jaccard_index(set(normalized_a.split()), set(normalized_b.split()))


# --- Skema database ---
def create_tables(conn):
    """Buat tabel V0.5 jika belum ada."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS v05_incidents (
            incident_id TEXT PRIMARY KEY,
            attack_type TEXT,
            target TEXT,
            target_entity_id TEXT,
            threat_actor TEXT,
            threat_actor_entity_id TEXT,
            location TEXT,
            attack_date TEXT,
            attack_method TEXT,
            document_count INTEGER DEFAULT 0,
            incident_confidence REAL DEFAULT 0.0,
            clustering_method TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS v05_incident_documents (
            relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            article_id INTEGER NOT NULL,
            similarity_score REAL,
            similarity_confidence REAL,
            clustering_method TEXT,
            assigned_at TEXT,
            UNIQUE (article_id)
        )
        """)
    # Tabel terpenting: satu article_id hanya boleh muncul satu kali.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS v05_processed_articles (
            article_id INTEGER PRIMARY KEY,
            incident_id TEXT,
            processed_at TEXT NOT NULL
        )
        """)
    conn.commit()


def migrate_existing_tables(conn):
    """Tambahkan kolom V0.5 yang belum ada pada tabel buatan versi lama."""
    cursor = conn.cursor()

    # v05_incidents
    cursor.execute("PRAGMA table_info(v05_incidents)")
    incident_columns = {row[1] for row in cursor.fetchall()}
    required_incident_columns = {
        "attack_type": "TEXT",
        "target": "TEXT",
        "target_entity_id": "TEXT",
        "threat_actor": "TEXT",
        "threat_actor_entity_id": "TEXT",
        "location": "TEXT",
        "attack_date": "TEXT",
        "attack_method": "TEXT",
        "document_count": "INTEGER DEFAULT 0",
        "incident_confidence": "REAL DEFAULT 0.0",
        "clustering_method": "TEXT",
        "created_at": "TEXT",
        "updated_at": "TEXT",
    }
    for column_name, column_type in required_incident_columns.items():
        if column_name not in incident_columns:
            cursor.execute(
                f"ALTER TABLE v05_incidents ADD COLUMN {column_name} {column_type}"
            )

    # v05_incident_documents: CREATE TABLE IF NOT EXISTS tidak mengubah tabel
    # lama, jadi schema lama diperiksa satu per satu. Kolom assigned_at adalah
    # penyebab error sebelumnya.
    cursor.execute("PRAGMA table_info(v05_incident_documents)")
    document_columns = {row[1] for row in cursor.fetchall()}
    required_document_columns = {
        "similarity_score": "REAL",
        "similarity_confidence": "REAL",
        "clustering_method": "TEXT",
        "assigned_at": "TEXT",
    }
    for column_name, column_type in required_document_columns.items():
        if column_name not in document_columns:
            cursor.execute(
                f"ALTER TABLE v05_incident_documents "
                f"ADD COLUMN {column_name} {column_type}"
            )

    # v05_processed_articles
    cursor.execute("PRAGMA table_info(v05_processed_articles)")
    processed_columns = {row[1] for row in cursor.fetchall()}
    if "incident_id" not in processed_columns:
        cursor.execute("ALTER TABLE v05_processed_articles ADD COLUMN incident_id TEXT")
    if "processed_at" not in processed_columns:
        cursor.execute(
            "ALTER TABLE v05_processed_articles ADD COLUMN processed_at TEXT"
        )

    conn.commit()


def create_v05_indexes(conn):
    """Buat index V0.5. Dibuat SETELAH migrasi karena kolom bisa belum ada."""
    cursor = conn.cursor()
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_v05_incident_documents_incident "
        "ON v05_incident_documents(incident_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_v05_incident_documents_article "
        "ON v05_incident_documents(article_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_v05_processed_article "
        "ON v05_processed_articles(article_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_v05_incidents_target "
        "ON v05_incidents(target_entity_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_v05_incidents_attack_type "
        "ON v05_incidents(attack_type)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_v05_incidents_actor "
        "ON v05_incidents(threat_actor_entity_id)"
    )
    conn.commit()


# --- Pemulihan hasil versi lama ---
def recover_previous_processed_articles(conn):
    """Tandai artikel yang sudah ada di v05_incident_documents sebagai processed."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO v05_processed_articles (
            article_id, incident_id, processed_at
        )
        SELECT article_id, incident_id, COALESCE(assigned_at, ?)
        FROM v05_incident_documents
        """,
        (get_timestamp(),),
    )
    recovered = cursor.rowcount
    conn.commit()
    return recovered


def recover_document_counts(conn):
    """Samakan document_count di v05_incidents dengan jumlah relasi sebenarnya."""
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE v05_incidents
        SET document_count = (
            SELECT COUNT(*)
            FROM v05_incident_documents d
            WHERE d.incident_id = v05_incidents.incident_id
        )
        """)
    conn.commit()


# --- Pengambilan data ---
def get_next_batch(conn):
    """Ambil batch artikel V0.3 yang belum ada di v05_processed_articles."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            v03.article_id, v03.attack_type, v03.target, v03.target_organization,
            v03.threat_actor, v03.location, v03.attack_date, v03.attack_method
        FROM v03_information_extraction v03
        LEFT JOIN v05_processed_articles p ON v03.article_id = p.article_id
        WHERE p.article_id IS NULL
        ORDER BY v03.article_id
        LIMIT ?
        """,
        (BATCH_SIZE,),
    )
    return cursor.fetchall()


def get_canonical_entity(conn, article_id, entity_type):
    """Ambil (entity_id, canonical_name) V0.4 dengan resolution_score tertinggi."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT m.entity_id, m.canonical_name
        FROM v04_entity_mentions m
        WHERE m.article_id = ? AND m.entity_type = ?
        ORDER BY m.resolution_score DESC
        LIMIT 1
        """,
        (article_id, entity_type),
    )
    row = cursor.fetchone()
    if row is None:
        return None, None
    return row[0], row[1]


def prepare_article(conn, row):
    """Susun dict artikel dengan canonical entity V0.4 dan nilai ternormalisasi."""
    (
        article_id,
        attack_type,
        target,
        target_organization,
        threat_actor,
        location,
        attack_date,
        attack_method,
    ) = row

    # Target: canonical V0.4, fallback ke target_organization lalu target V0.3
    target_entity_id, canonical_target = get_canonical_entity(
        conn, article_id, TARGET_ENTITY_TYPE
    )
    if canonical_target is None:
        if not is_unknown(target_organization):
            canonical_target = target_organization
        elif not is_unknown(target):
            canonical_target = target

    # Threat actor
    threat_actor_entity_id, canonical_actor = get_canonical_entity(
        conn, article_id, THREAT_ACTOR_ENTITY_TYPE
    )
    if canonical_actor is None:
        canonical_actor = None if is_unknown(threat_actor) else threat_actor

    # Location
    location_entity_id, canonical_location = get_canonical_entity(
        conn, article_id, LOCATION_ENTITY_TYPE
    )
    if canonical_location is None:
        canonical_location = None if is_unknown(location) else location

    return {
        "article_id": article_id,
        "attack_type": normalize_value(attack_type),
        "target": normalize_value(canonical_target),
        "target_entity_id": target_entity_id,
        "threat_actor": normalize_value(canonical_actor),
        "threat_actor_entity_id": threat_actor_entity_id,
        "location": normalize_value(canonical_location),
        "attack_date": normalize_value(attack_date),
        "attack_method": normalize_value(attack_method),
    }


# --- Pencarian incident ---
def get_existing_incidents(conn, article):
    """Kandidat incident lewat blocking sederhana, bukan seluruh tabel."""
    cursor = conn.cursor()
    target_entity_id = article["target_entity_id"]
    attack_type = article["attack_type"]
    threat_actor_entity_id = article["threat_actor_entity_id"]
    candidates = []

    # Strategi 1: target entity
    if target_entity_id:
        cursor.execute(
            """
            SELECT
                incident_id, attack_type, target, target_entity_id, threat_actor,
                threat_actor_entity_id, location, attack_date, attack_method,
                document_count, incident_confidence
            FROM v05_incidents
            WHERE target_entity_id = ?
            ORDER BY updated_at DESC
            """,
            (target_entity_id,),
        )
        candidates.extend(cursor.fetchall())

    # Strategi 2: threat actor
    if threat_actor_entity_id:
        cursor.execute(
            """
            SELECT
                incident_id, attack_type, target, target_entity_id, threat_actor,
                threat_actor_entity_id, location, attack_date, attack_method,
                document_count, incident_confidence
            FROM v05_incidents
            WHERE threat_actor_entity_id = ?
            ORDER BY updated_at DESC
            """,
            (threat_actor_entity_id,),
        )
        candidates.extend(cursor.fetchall())

    # Strategi 3: attack type, hanya jika dua strategi di atas tidak menghasilkan
    if attack_type and not candidates:
        cursor.execute(
            """
            SELECT
                incident_id, attack_type, target, target_entity_id, threat_actor,
                threat_actor_entity_id, location, attack_date, attack_method,
                document_count, incident_confidence
            FROM v05_incidents
            WHERE attack_type = ?
            ORDER BY updated_at DESC
            LIMIT 1000
            """,
            (attack_type,),
        )
        candidates.extend(cursor.fetchall())

    # Hapus duplikat berdasarkan incident_id
    unique = {}
    for candidate in candidates:
        unique[candidate[0]] = candidate
    return list(unique.values())


def passes_hard_constraints(article, incident):
    """Cegah incident yang jelas berbeda digabung."""
    (
        incident_id,
        incident_attack_type,
        incident_target,
        incident_target_entity_id,
        incident_actor,
        incident_actor_entity_id,
        incident_location,
        incident_date,
        incident_method,
        document_count,
        incident_confidence,
    ) = incident

    # Canonical target berbeda: jangan merge
    article_target_id = article["target_entity_id"]
    if (
        article_target_id
        and incident_target_entity_id
        and article_target_id != incident_target_entity_id
    ):
        return False

    # Threat actor berbeda
    article_actor_id = article["threat_actor_entity_id"]
    if (
        article_actor_id
        and incident_actor_entity_id
        and article_actor_id != incident_actor_entity_id
    ):
        return False

    # Attack type berbeda
    article_attack_type = article["attack_type"]
    if (
        article_attack_type
        and incident_attack_type
        and article_attack_type != incident_attack_type
    ):
        return False

    # Tanggal di luar jendela DATE_WINDOW_DAYS
    article_date = article["attack_date"]
    if article_date and incident_date:
        date_similarity = calculate_date_similarity(article_date, incident_date)
        if date_similarity == 0.0:
            return False

    return True


def calculate_incident_similarity(article, incident):
    """Skor kemiripan berbobot antara artikel dan incident."""
    (
        incident_id,
        incident_attack_type,
        incident_target,
        incident_target_entity_id,
        incident_actor,
        incident_actor_entity_id,
        incident_location,
        incident_date,
        incident_method,
        document_count,
        incident_confidence,
    ) = incident

    # Target: bandingkan entity id jika keduanya ada, selain itu teksnya
    if article["target_entity_id"] and incident_target_entity_id:
        target_similarity = (
            1.0 if article["target_entity_id"] == incident_target_entity_id else 0.0
        )
    else:
        target_similarity = calculate_field_similarity(
            article["target"], incident_target
        )

    attack_type_similarity = calculate_field_similarity(
        article["attack_type"], incident_attack_type
    )

    # Threat actor: bandingkan entity id jika keduanya ada, selain itu teksnya
    if article["threat_actor_entity_id"] and incident_actor_entity_id:
        actor_similarity = (
            1.0
            if article["threat_actor_entity_id"] == incident_actor_entity_id
            else 0.0
        )
    else:
        actor_similarity = calculate_field_similarity(
            article["threat_actor"], incident_actor
        )

    location_similarity = calculate_field_similarity(
        article["location"], incident_location
    )
    date_similarity = calculate_date_similarity(article["attack_date"], incident_date)
    method_similarity = calculate_field_similarity(
        article["attack_method"], incident_method
    )

    # Skor berbobot: hanya field yang dapat dibandingkan yang ikut dihitung
    weighted_values = []
    weighted_weights = []
    if target_similarity is not None:
        weighted_values.append(target_similarity)
        weighted_weights.append(TARGET_WEIGHT)
    if attack_type_similarity is not None:
        weighted_values.append(attack_type_similarity)
        weighted_weights.append(ATTACK_TYPE_WEIGHT)
    if actor_similarity is not None:
        weighted_values.append(actor_similarity)
        weighted_weights.append(THREAT_ACTOR_WEIGHT)
    if location_similarity is not None:
        weighted_values.append(location_similarity)
        weighted_weights.append(LOCATION_WEIGHT)
    if date_similarity > 0:
        weighted_values.append(date_similarity)
        weighted_weights.append(ATTACK_DATE_WEIGHT)
    if method_similarity is not None:
        weighted_values.append(method_similarity)
        weighted_weights.append(ATTACK_METHOD_WEIGHT)

    if not weighted_weights:
        return 0.0
    total_weight = sum(weighted_weights)
    weighted_score = sum(
        value * weight for value, weight in zip(weighted_values, weighted_weights)
    )
    if total_weight == 0:
        return 0.0
    return weighted_score / total_weight


def find_best_incident(conn, article):
    """Incident dengan skor tertinggi yang lolos hard constraint dan threshold."""
    candidates = get_existing_incidents(conn, article)
    best_incident = None
    best_score = 0.0
    for incident in candidates:
        if not passes_hard_constraints(article, incident):
            continue
        score = calculate_incident_similarity(article, incident)
        if score > best_score:
            best_score = score
            best_incident = incident
    if best_incident is not None and best_score >= INCIDENT_SIMILARITY_THRESHOLD:
        return best_incident, best_score
    return None, 0.0


# --- Penyimpanan incident ---
def generate_incident_id(article_id):
    """ID incident dari sha1(article_id + timestamp), 12 hex huruf besar."""
    raw = f"INCIDENT|{article_id}|{get_timestamp()}"
    hash_value = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12].upper()
    return f"INCIDENT_{hash_value}"


def create_incident(conn, article, confidence):
    """Simpan incident baru dari artikel dan kembalikan incident_id."""
    incident_id = generate_incident_id(article["article_id"])
    now = get_timestamp()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO v05_incidents (
            incident_id, attack_type, target, target_entity_id, threat_actor,
            threat_actor_entity_id, location, attack_date, attack_method,
            document_count, incident_confidence, clustering_method,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            incident_id,
            article["attack_type"],
            article["target"],
            article["target_entity_id"],
            article["threat_actor"],
            article["threat_actor_entity_id"],
            article["location"],
            article["attack_date"],
            article["attack_method"],
            0,
            confidence,
            "RULE_BASED",
            now,
            now,
        ),
    )
    return incident_id


def save_incident_document(
    conn,
    incident_id,
    article_id,
    similarity_score,
    similarity_confidence,
    clustering_method,
):
    """Simpan relasi article -> incident; kembalikan jumlah baris yang masuk."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO v05_incident_documents (
            incident_id, article_id, similarity_score, similarity_confidence,
            clustering_method, assigned_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            incident_id,
            article_id,
            similarity_score,
            similarity_confidence,
            clustering_method,
            get_timestamp(),
        ),
    )
    inserted = cursor.rowcount

    # Perbarui document_count
    if inserted == 1:
        cursor.execute(
            """
            UPDATE v05_incidents
            SET document_count = (
                SELECT COUNT(*)
                FROM v05_incident_documents d
                WHERE d.incident_id = v05_incidents.incident_id
            ),
            updated_at = ?
            WHERE incident_id = ?
            """,
            (get_timestamp(), incident_id),
        )

    return inserted


def update_incident(conn, incident_id, article, similarity_score):
    """Lengkapi field incident yang masih kosong dengan informasi artikel baru."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            attack_type, target, target_entity_id, threat_actor,
            threat_actor_entity_id, location, attack_date, attack_method,
            incident_confidence
        FROM v05_incidents
        WHERE incident_id = ?
        """,
        (incident_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return

    (
        old_attack_type,
        old_target,
        old_target_entity_id,
        old_actor,
        old_actor_entity_id,
        old_location,
        old_date,
        old_method,
        old_confidence,
    ) = row

    # Nilai lama dipertahankan jika sudah ada
    attack_type = old_attack_type or article["attack_type"]
    target = old_target or article["target"]
    target_entity_id = old_target_entity_id or article["target_entity_id"]
    actor = old_actor or article["threat_actor"]
    actor_entity_id = old_actor_entity_id or article["threat_actor_entity_id"]
    location = old_location or article["location"]
    attack_date = old_date or article["attack_date"]
    attack_method = old_method or article["attack_method"]

    if old_confidence is None:
        new_confidence = similarity_score
    else:
        new_confidence = max(old_confidence, similarity_score)

    cursor.execute(
        """
        UPDATE v05_incidents
        SET
            attack_type = ?,
            target = ?,
            target_entity_id = ?,
            threat_actor = ?,
            threat_actor_entity_id = ?,
            location = ?,
            attack_date = ?,
            attack_method = ?,
            incident_confidence = ?,
            updated_at = ?
        WHERE incident_id = ?
        """,
        (
            attack_type,
            target,
            target_entity_id,
            actor,
            actor_entity_id,
            location,
            attack_date,
            attack_method,
            new_confidence,
            get_timestamp(),
            incident_id,
        ),
    )


def mark_article_processed(conn, article_id, incident_id):
    """Tandai article sebagai sudah diproses."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO v05_processed_articles (
            article_id, incident_id, processed_at
        )
        VALUES (?, ?, ?)
        """,
        (article_id, incident_id, get_timestamp()),
    )


# --- Pemrosesan ---
def process_article(conn, row):
    """Kelompokkan satu artikel ke incident lama atau buat incident baru."""
    article = prepare_article(conn, row)
    article_id = article["article_id"]

    # Pengaman ganda: walaupun get_next_batch() sudah memfilter, cek lagi.
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT incident_id
        FROM v05_processed_articles
        WHERE article_id = ?
        LIMIT 1
        """,
        (article_id,),
    )
    already_processed = cursor.fetchone()
    if already_processed:
        return {
            "status": "ALREADY_PROCESSED",
            "incident_id": already_processed[0],
            "score": 1.0,
            "method": "SKIP",
        }

    best_incident, best_score = find_best_incident(conn, article)

    # Incident lama
    if best_incident is not None:
        incident_id = best_incident[0]
        update_incident(conn, incident_id, article, best_score)
        save_incident_document(
            conn,
            incident_id,
            article_id,
            best_score,
            best_score,
            "RULE_BASED_CLUSTERING",
        )
        mark_article_processed(conn, article_id, incident_id)
        return {
            "status": "EXISTING_INCIDENT",
            "incident_id": incident_id,
            "score": best_score,
            "method": "EXISTING_INCIDENT",
        }

    # Incident baru
    incident_id = create_incident(conn, article, 1.0)
    save_incident_document(conn, incident_id, article_id, 1.0, 1.0, "NEW_INCIDENT")
    mark_article_processed(conn, article_id, incident_id)
    return {
        "status": "NEW_INCIDENT",
        "incident_id": incident_id,
        "score": 1.0,
        "method": "NEW_INCIDENT",
    }


def process_batch(conn, rows):
    """Proses satu batch artikel; kembalikan tuple penghitung batch."""
    batch_articles = 0
    batch_new_incidents = 0
    batch_existing_incidents = 0
    batch_skipped = 0

    for row in rows:
        article_id = row[0]
        try:
            result = process_article(conn, row)
            status = result["status"]
            if status == "NEW_INCIDENT":
                batch_new_incidents += 1
            elif status == "EXISTING_INCIDENT":
                batch_existing_incidents += 1
            elif status == "ALREADY_PROCESSED":
                batch_skipped += 1
            if status != "ALREADY_PROCESSED":
                batch_articles += 1

            print("\n--------------------------------------------------")
            print(f"Article ID : {article_id}")
            print(f"Attack     : {row[1] or 'UNKNOWN'}")
            print(f"Target     : {row[2] or 'UNKNOWN'}")
            print(f"Actor      : {row[4] or 'UNKNOWN'}")
            print(f"Date       : {row[6] or 'UNKNOWN'}")
            print(f"Incident   : {result['incident_id']}")
            print(f"Score      : {result['score']:.2f}")
            print(f"Method     : {result['method']}")
        except Exception as error:
            print("\n⚠️ ERROR")
            print(f"Article ID : {article_id}")
            print(f"Error      : {error}")
            # Artikel tidak ditandai processed agar dicoba kembali pada run
            # berikutnya.
            continue

    conn.commit()
    return (
        batch_articles,
        batch_new_incidents,
        batch_existing_incidents,
        batch_skipped,
    )


def database_summary(conn):
    """Hitung jumlah kandidat V0.3, artikel terproses, sisa, incident, dokumen."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM v03_information_extraction")
    total_v03 = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM v05_processed_articles")
    processed_articles = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM v05_incidents")
    total_incidents = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM v05_incident_documents")
    total_documents = cursor.fetchone()[0]

    remaining = total_v03 - processed_articles
    if remaining < 0:
        remaining = 0

    return (
        total_v03,
        processed_articles,
        remaining,
        total_incidents,
        total_documents,
    )


def run():
    """Jalankan V0.5 Incident Clustering sampai tidak ada artikel tersisa."""
    print("\n==================================================")
    print("   V0.5 INCIDENT CLUSTERING")
    print("==================================================")

    conn = get_connection()
    create_tables(conn)
    migrate_existing_tables(conn)
    create_v05_indexes(conn)  # setelah migrasi

    # Pulihkan hasil versi lama
    recovered = recover_previous_processed_articles(conn)
    if recovered > 0:
        print("\n♻️ Recovery:")
        print(f"   {recovered} artikel lama ditandai sebagai PROCESSED.")
    recover_document_counts(conn)

    # Status awal
    (
        total_v03,
        processed_articles,
        remaining,
        total_incidents,
        total_documents,
    ) = database_summary(conn)
    print("\n==================================================")
    print("   V0.5 DATABASE STATUS")
    print("==================================================")
    print(f"V03 candidates      : {total_v03}")
    print(f"Processed articles  : {processed_articles}")
    print(f"Remaining           : {remaining}")
    print(f"Incidents           : {total_incidents}")
    print(f"Incident documents  : {total_documents}")
    print("==================================================")

    total_articles_processed = 0
    total_new_incidents = 0
    total_existing_incidents = 0
    total_skipped = 0

    try:
        while True:
            rows = get_next_batch(conn)
            if not rows:
                break

            (
                batch_articles,
                batch_new_incidents,
                batch_existing_incidents,
                batch_skipped,
            ) = process_batch(conn, rows)
            total_articles_processed += batch_articles
            total_new_incidents += batch_new_incidents
            total_existing_incidents += batch_existing_incidents
            total_skipped += batch_skipped

            (
                current_v03,
                current_processed,
                current_remaining,
                current_incidents,
                current_documents,
            ) = database_summary(conn)
            print("\n==================================================")
            print(f"Batch articles      : {batch_articles}")
            print(f"New incidents       : {batch_new_incidents}")
            print(f"Existing incidents  : {batch_existing_incidents}")
            print(f"Skipped             : {batch_skipped}")
            print(f"Total processed     : {current_processed}")
            print(f"Total incidents     : {current_incidents}")
            print(f"Total documents     : {current_documents}")
            print(f"Remaining           : {current_remaining}")
            print("==================================================")
    except KeyboardInterrupt:
        conn.commit()
        print("\n\n⚠️ V0.5 dihentikan oleh user.")
        print("Batch yang sudah selesai telah disimpan.")
        print("Jalankan kembali untuk melanjutkan.")
    finally:
        conn.close()

    # Ringkasan akhir
    conn = get_connection()
    (
        final_v03,
        final_processed,
        final_remaining,
        final_incidents,
        final_documents,
    ) = database_summary(conn)
    conn.close()

    print("\n==================================================")
    print("   V0.5 ANALYSIS SUMMARY")
    print("==================================================")
    print(f"V03 candidates      : {final_v03}")
    print(f"Processed articles  : {final_processed}")
    print(f"Remaining           : {final_remaining}")
    print(f"Total incidents     : {final_incidents}")
    print(f"Incident documents  : {final_documents}")
    print(f"Articles processed this run           : {total_articles_processed}")
    print(f"New incidents this run            : {total_new_incidents}")
    print(f"Existing incidents this run            : {total_existing_incidents}")
    print("==================================================")
    if final_remaining == 0:
        print("   ✅ V0.5 INCIDENT CLUSTERING SELESAI")
    else:
        print("   ⏸️ V0.5 BELUM SELESAI")
        print("   Jalankan kembali untuk melanjutkan.")
    print("==================================================")


if __name__ == "__main__":
    run()
