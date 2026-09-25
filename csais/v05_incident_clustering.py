"""V0.5 - Incident Clustering.

CSAIS - Cyber Social Attack Intelligence System.

Fungsi:
  1. Mengambil hasil V0.3 beserta judul, ringkasan, dan tanggal terbit artikel
  2. Menggunakan canonical entity dari V0.4
  3. Mengelompokkan artikel yang kemungkinan membahas incident cyber attack
     yang sama
  4. Membuat incident baru jika tidak ditemukan incident yang sesuai
  5. Menyimpan hubungan article -> incident
  6. Menandai article sebagai sudah diproses

Aturan penggabungan: artikel hanya digabung ke incident lama bila lolos hard
constraint (target/pelaku/jenis serangan tidak bertentangan, tanggal dalam
jendela) DAN salah satu dari:
  - ada sinyal identitas: entity/nama target sama, nama target satu sisi muncul
    di teks sisi lain, token khas (jarang di korpus) yang sama, atau pelaku sama
    dengan teks sedikit mirip; skor gabungan >= MIN_SCORE_WITH_IDENTITY
  - kemiripan judul+ringkasan >= TEXT_SIMILARITY_THRESHOLD dan skor gabungan
    >= INCIDENT_SIMILARITY_THRESHOLD
Jenis serangan yang sama saja tidak cukup untuk menggabungkan dua artikel.
Kandidat incident dibatasi pada jendela tanggal terbit PUBLISHED_WINDOW_DAYS.

IMPORTANT:
Satu article_id hanya boleh diproses satu kali. Jangan menggunakan
v05_incident_documents sebagai satu-satunya indikator bahwa article sudah
diproses. Karena itu digunakan tabel v05_processed_articles.
"""

import hashlib
from datetime import datetime, timedelta, timezone

from csais.db import get_connection, get_timestamp
from csais.provenance import pipeline_stamp
from csais.schema import ensure_article_uid, record_run
from csais.text import (
    jaccard_index,
    normalize_text,
    remove_publisher,
    split_publisher,
    tokenize,
)


# --- Konfigurasi ---
BATCH_SIZE = 500
INCIDENT_SIMILARITY_THRESHOLD = 0.70
DATE_WINDOW_DAYS = 14  # jendela tanggal serangan (attack_date)
PUBLISHED_WINDOW_DAYS = 14  # jendela tanggal terbit untuk kandidat incident
# Jaccard judul+ringkasan yang dianggap "berita yang sama". Pada sampel uji,
# pasangan 0.35-0.50 hampir semuanya liputan insiden yang sama dari media
# berbeda; di bawah 0.35 mulai bercampur dengan insiden lain yang sejenis.
TEXT_SIMILARITY_THRESHOLD = 0.35
MIN_TEXT_SIMILARITY_WITH_ACTOR = 0.30  # pelaku sama + teks cukup mirip
MIN_SCORE_WITH_IDENTITY = 0.40  # skor minimum bila ada sinyal identitas target
TARGET_IN_TEXT_SIMILARITY = 0.9  # nama target satu sisi muncul di teks sisi lain
# Nama target yang muncul di lebih dari max(TARGET_MIN_DF_LIMIT,
# TARGET_MAX_DF_RATIO * jumlah artikel) artikel (Microsoft, FBI, CISA, Google)
# terlalu umum untuk menjadi bukti identitas satu insiden.
TARGET_MAX_DF_RATIO = 0.003
TARGET_MIN_DF_LIMIT = 20
MAX_ANCHOR_TOKENS = 300  # token incident berhenti diperkaya setelah sebanyak ini
# Rantai incident: incident lanjutan dengan target khas yang sama, mulai paling
# lama CHAIN_GAP_DAYS setelah liputan terakhir incident sebelumnya, digabung.
CHAIN_GAP_DAYS = 30
# Token dianggap nama khas bila muncul di <= max(RARE_TOKEN_MAX_DF,
# RARE_TOKEN_MAX_DF_RATIO * jumlah artikel) artikel, agar batasnya ikut
# membesar pada korpus yang besar.
RARE_TOKEN_MAX_DF = 5
RARE_TOKEN_MAX_DF_RATIO = 0.00025
RARE_TOKEN_MIN_LENGTH = 5
MAX_CANDIDATES = 3000

# Token nama target yang terlalu umum untuk dijadikan bukti identitas sendiri
GENERIC_TARGET_TOKENS = {
    "the", "and", "of", "for", "inc", "ltd", "llc", "plc", "corp", "corporation",
    "company", "group", "holdings", "services", "systems", "solutions", "health",
    "healthcare", "hospital", "medical", "clinic", "school", "schools", "district",
    "university", "college", "city", "county", "state", "council", "department",
    "ministry", "bank", "government", "national", "international", "global",
    "public", "police", "center", "centre",
}

# Bobot similarity
TARGET_WEIGHT = 0.30
TEXT_WEIGHT = 0.30
THREAT_ACTOR_WEIGHT = 0.15
ATTACK_TYPE_WEIGHT = 0.10
LOCATION_WEIGHT = 0.05
ATTACK_DATE_WEIGHT = 0.05
ATTACK_METHOD_WEIGHT = 0.05

# Tipe entity dari V0.4
TARGET_ENTITY_TYPE = "ORGANIZATION"
THREAT_ACTOR_ENTITY_TYPE = "THREAT_ACTOR"
LOCATION_ENTITY_TYPE = "LOCATION"

UNKNOWN_VALUES = {"", "unknown", "none", "null", "n/a", "na", "-"}

# Kata yang terlalu umum untuk membedakan dua berita
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "after", "over", "into",
    "has", "have", "had", "was", "were", "are", "its", "his", "her", "their", "new",
    "says", "said", "will", "been", "more", "than", "about", "amid", "how", "why",
    "what", "who", "when", "cyber", "cyberattack", "cyberattacks", "attack",
    "attacks", "security", "cybersecurity", "hackers", "hacker", "data", "news",
    "com", "www", "http", "https", "yang", "dan", "dari", "untuk", "dengan", "pada",
    "oleh", "ini", "itu", "serangan", "siber", "tahun", "kata", "juga", "akan",
    "telah", "ada",
}

# Keluarga jenis serangan: satu kejadian sering diberi label berbeda oleh media
# yang berbeda (ransomware vs data_leak untuk insiden yang sama), jadi
# kecocokan jenis serangan dibandingkan per keluarga, bukan per kategori.
ATTACK_TYPE_FAMILIES = {
    "BREACH": [
        "ransomware", "malware", "cyber_extortion", "data_breach", "data_leak",
        "data_theft", "data_exfiltration", "account_takeover", "credential_attack",
        "network_intrusion", "insider_threat", "cloud_attack", "supply_chain_attack",
    ],
    "SOCIAL": [
        "phishing", "social_engineering", "online_scam", "job_scam", "investment_scam",
        "deepfake_fraud", "malicious_website", "malicious_link",
    ],
    "VULNERABILITY": [
        "zero_day", "vulnerability_exploitation", "remote_code_execution", "web_attack",
        "sql_injection", "xss", "path_traversal", "file_inclusion",
        "website_defacement", "domain_hijacking",
    ],
    "DDOS": ["ddos", "dns_attack"],
    "ESPIONAGE": ["cyber_espionage", "apt", "information_operation"],
    "INFRASTRUCTURE": [
        "critical_infrastructure_attack", "ics_scada_attack", "iot_attack", "mobile_attack",
    ],
    "CRYPTO": ["crypto_attack"],
}
_FAMILY_OF = {
    category: family
    for family, categories in ATTACK_TYPE_FAMILIES.items()
    for category in categories
}

INCIDENT_COLUMNS = [
    "incident_id", "attack_type", "target", "target_entity_id", "threat_actor",
    "threat_actor_entity_id", "location", "attack_date", "attack_method",
    "document_count", "incident_confidence", "anchor_text", "anchor_published_date",
    "last_published_date",
]
_INCIDENT_SELECT = "SELECT " + ", ".join(INCIDENT_COLUMNS) + " FROM v05_incidents"


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


def text_tokens(title, summary):
    """Token judul dan ringkasan tanpa nama media dan tanpa stopword."""
    headline, publisher = split_publisher(title)
    text = f"{headline} {remove_publisher(summary, publisher)}"
    return tokenize(text) - STOPWORDS


def attack_type_set(value):
    """Himpunan kategori dari string V0.3 seperti 'ransomware, data_breach'."""
    if not value:
        return set()
    return {part.strip() for part in value.split(",") if part.strip()}


def attack_family_set(value):
    """Himpunan keluarga jenis serangan; kategori tak dikenal menjadi keluarganya sendiri."""
    return {_FAMILY_OF.get(category, category) for category in attack_type_set(value)}


def families_compatible(value_a, value_b):
    """True bila salah satu tidak diketahui atau keluarganya beririsan."""
    families_a = attack_family_set(value_a)
    families_b = attack_family_set(value_b)
    return not families_a or not families_b or bool(families_a & families_b)


def distinctive_tokens(name):
    """Token nama target yang cukup khas untuk menjadi bukti identitas.

    Token generik dan token yang terlalu sering muncul di korpus dibuang;
    himpunan kosong berarti nama itu tidak bisa dipakai sebagai identitas.
    """
    if not name:
        return set()
    tokens = tokenize(name) - STOPWORDS - GENERIC_TARGET_TOKENS
    return {token for token in tokens if _TOKEN_DF.get(token, 0) <= _TARGET_DF_LIMIT}


def target_in_text(article, incident, anchor_tokens):
    """True bila nama target satu sisi muncul utuh di teks judul+ringkasan sisi lain."""
    article_target = distinctive_tokens(article["target"])
    if article_target and article_target <= anchor_tokens:
        return True
    incident_target = distinctive_tokens(normalize_value(incident["target"]))
    return bool(incident_target and incident_target <= article["tokens"])


# Frekuensi dokumen tiap token (judul+ringkasan) di seluruh tabel articles.
# Token yang hanya muncul di beberapa artikel (nama produk, nama grup) adalah
# bukti kuat bahwa dua artikel membahas hal yang sama.
_TOKEN_DF = {}
_RARE_DF_LIMIT = RARE_TOKEN_MAX_DF
_TARGET_DF_LIMIT = float("inf")


def load_token_document_frequency(conn):
    """Hitung di berapa artikel setiap token muncul, beserta batas-batasnya."""
    global _RARE_DF_LIMIT, _TARGET_DF_LIMIT
    _TOKEN_DF.clear()
    cursor = conn.cursor()
    cursor.execute("SELECT title, summary FROM articles")
    total = 0
    for title, summary in cursor:
        total += 1
        for token in text_tokens(title, summary):
            _TOKEN_DF[token] = _TOKEN_DF.get(token, 0) + 1
    _RARE_DF_LIMIT = max(RARE_TOKEN_MAX_DF, int(total * RARE_TOKEN_MAX_DF_RATIO))
    _TARGET_DF_LIMIT = max(TARGET_MIN_DF_LIMIT, int(total * TARGET_MAX_DF_RATIO))


def shared_rare_tokens(tokens_a, tokens_b):
    """Token khas (jarang di korpus) yang dimiliki kedua himpunan."""
    return {
        token
        for token in tokens_a & tokens_b
        if len(token) >= RARE_TOKEN_MIN_LENGTH
        and 0 < _TOKEN_DF.get(token, 0) <= _RARE_DF_LIMIT
    }


# --- Similarity ---
def calculate_date_similarity(date_a, date_b):
    """Kemiripan tanggal: None bila salah satu tidak bisa diparse, 0 di luar jendela."""
    parsed_a = parse_date(date_a)
    parsed_b = parse_date(date_b)
    if parsed_a is None or parsed_b is None:
        return None
    difference_days = abs((parsed_a - parsed_b).total_seconds()) / 86400.0
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
            anchor_article_id INTEGER,
            anchor_text TEXT,
            anchor_published_date TEXT,
            last_published_date TEXT,
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
            pipeline_version TEXT,
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
        "anchor_article_id": "INTEGER",
        "anchor_text": "TEXT",
        "anchor_published_date": "TEXT",
        "last_published_date": "TEXT",
        "created_at": "TEXT",
        "updated_at": "TEXT",
    }
    for column_name, column_type in required_incident_columns.items():
        if column_name not in incident_columns:
            cursor.execute(
                f"ALTER TABLE v05_incidents ADD COLUMN {column_name} {column_type}"
            )

    cursor.execute("PRAGMA table_info(v05_incident_documents)")
    document_columns = {row[1] for row in cursor.fetchall()}
    required_document_columns = {
        "similarity_score": "REAL",
        "similarity_confidence": "REAL",
        "clustering_method": "TEXT",
        "assigned_at": "TEXT",
        "pipeline_version": "TEXT",
    }
    for column_name, column_type in required_document_columns.items():
        if column_name not in document_columns:
            cursor.execute(
                f"ALTER TABLE v05_incident_documents "
                f"ADD COLUMN {column_name} {column_type}"
            )

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
    """Buat index V0.5 (setelah migrasi) dan buang index ganda versi lama."""
    cursor = conn.cursor()
    for legacy_index in (
        "idx_v05_documents_article",
        "idx_v05_documents_incident",
        "idx_v05_incident_target",
        "idx_v05_incident_attack_type",
        "idx_v05_incident_actor",
        "idx_v05_processed_article",  # article_id sudah PRIMARY KEY
    ):
        cursor.execute(f"DROP INDEX IF EXISTS {legacy_index}")
    indexes = {
        "idx_v05_incident_documents_incident": "v05_incident_documents(incident_id)",
        "idx_v05_incident_documents_article": "v05_incident_documents(article_id)",
        "idx_v05_incidents_target": "v05_incidents(target_entity_id)",
        "idx_v05_incidents_attack_type": "v05_incidents(attack_type)",
        "idx_v05_incidents_actor": "v05_incidents(threat_actor_entity_id)",
        "idx_v05_incidents_published": "v05_incidents(anchor_published_date)",
    }
    for name, definition in indexes.items():
        cursor.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {definition}")
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
    """Ambil batch artikel V0.3 (plus judul, ringkasan, tanggal terbit) yang belum diproses."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            v03.article_id, v03.attack_type, v03.target, v03.target_organization,
            v03.threat_actor, v03.location, v03.attack_date, v03.attack_method,
            a.title, a.summary, a.published_date, a.article_uid
        FROM v03_information_extraction v03
        INNER JOIN articles a ON a.article_id = v03.article_id
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
    """Susun dict artikel dengan canonical entity V0.4, token teks, dan nilai ternormalisasi."""
    (
        article_id,
        attack_type,
        target,
        target_organization,
        threat_actor,
        location,
        attack_date,
        attack_method,
        title,
        summary,
        published_date,
        uid,
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

    # Location (nama canonical saja; id lokasi tidak dipakai V0.5)
    _, canonical_location = get_canonical_entity(conn, article_id, LOCATION_ENTITY_TYPE)
    if canonical_location is None:
        canonical_location = None if is_unknown(location) else location

    published = parse_date(published_date)
    return {
        "article_id": article_id,
        "article_uid": uid,
        "attack_type": normalize_value(attack_type),
        "target": normalize_value(canonical_target),
        "target_entity_id": target_entity_id,
        "threat_actor": normalize_value(canonical_actor),
        "threat_actor_entity_id": threat_actor_entity_id,
        "location": normalize_value(canonical_location),
        "attack_date": normalize_value(attack_date),
        "attack_method": normalize_value(attack_method),
        "tokens": text_tokens(title, summary),
        "published": published,
        "published_date": published.isoformat() if published else None,
    }


# --- Pencarian incident ---
def get_existing_incidents(conn, article):
    """Kandidat incident lewat blocking: entity target, pelaku, atau jendela terbit."""
    cursor = conn.cursor()
    candidates = []

    # Strategi 1: target entity
    if article["target_entity_id"]:
        cursor.execute(
            f"{_INCIDENT_SELECT} WHERE target_entity_id = ?",
            (article["target_entity_id"],),
        )
        candidates.extend(cursor.fetchall())

    # Strategi 2: threat actor entity
    if article["threat_actor_entity_id"]:
        cursor.execute(
            f"{_INCIDENT_SELECT} WHERE threat_actor_entity_id = ?",
            (article["threat_actor_entity_id"],),
        )
        candidates.extend(cursor.fetchall())

    # Strategi 3: incident yang aktif di sekitar tanggal terbit artikel dengan
    # keluarga jenis serangan yang beririsan (atau salah satunya tidak
    # diketahui). Irisan diperiksa kasar lewat instr() terhadap semua kategori
    # sekeluarga; pemeriksaan tepat ada di passes_hard_constraints.
    if article["published"]:
        window = timedelta(days=PUBLISHED_WINDOW_DAYS)
        lower = (article["published"] - window).isoformat()
        upper = (article["published"] + window).isoformat()
        related = sorted(
            category
            for family in attack_family_set(article["attack_type"])
            for category in ATTACK_TYPE_FAMILIES.get(family, [family])
        )
        type_clause = "attack_type IS NULL"
        params = [lower, upper]
        if related:
            type_clause += " OR " + " OR ".join("instr(attack_type, ?) > 0" for _ in related)
            params.extend(related)
        else:
            type_clause = "1 = 1"
        params.append(MAX_CANDIDATES)
        cursor.execute(
            f"""
            {_INCIDENT_SELECT}
            WHERE last_published_date >= ?
              AND anchor_published_date <= ?
              AND ({type_clause})
            ORDER BY last_published_date DESC
            LIMIT ?
            """,
            params,
        )
        candidates.extend(cursor.fetchall())

    # Hapus duplikat berdasarkan incident_id
    unique = {}
    for row in candidates:
        incident = dict(zip(INCIDENT_COLUMNS, row))
        unique[incident["incident_id"]] = incident
    return list(unique.values())


def passes_hard_constraints(article, incident):
    """Cegah incident yang jelas berbeda digabung."""
    if (
        article["target_entity_id"]
        and incident["target_entity_id"]
        and article["target_entity_id"] != incident["target_entity_id"]
    ):
        return False
    if (
        article["threat_actor_entity_id"]
        and incident["threat_actor_entity_id"]
        and article["threat_actor_entity_id"] != incident["threat_actor_entity_id"]
    ):
        return False
    # Keluarga jenis serangan keduanya diketahui tetapi tidak beririsan; kecuali
    # targetnya jelas sama (satu insiden sering diberi label berbeda, misalnya
    # zero-day yang berujung data breach)
    if not families_compatible(article["attack_type"], incident["attack_type"]):
        anchor_tokens = set((incident["anchor_text"] or "").split())
        if not target_identity(article, incident, anchor_tokens):
            return False

    # Tanggal serangan keduanya diketahui tetapi berjauhan
    date_similarity = calculate_date_similarity(
        article["attack_date"], incident["attack_date"]
    )
    if date_similarity == 0.0:
        return False

    # Tanggal terbit di luar rentang aktif incident
    published = article["published"]
    anchor = parse_date(incident["anchor_published_date"])
    last = parse_date(incident["last_published_date"]) or anchor
    if published and anchor and last:
        window = timedelta(days=PUBLISHED_WINDOW_DAYS)
        if published < anchor - window or published > last + window:
            return False

    return True


def calculate_incident_similarity(article, incident):
    """Skor kemiripan berbobot dan rincian komponennya."""
    anchor_tokens = set((incident["anchor_text"] or "").split())
    if article["target_entity_id"] and incident["target_entity_id"]:
        target_similarity = (
            1.0 if article["target_entity_id"] == incident["target_entity_id"] else 0.0
        )
    else:
        target_similarity = calculate_field_similarity(
            article["target"], incident["target"]
        )
    if target_similarity is None and target_in_text(article, incident, anchor_tokens):
        target_similarity = TARGET_IN_TEXT_SIMILARITY

    if article["threat_actor_entity_id"] and incident["threat_actor_entity_id"]:
        actor_similarity = (
            1.0
            if article["threat_actor_entity_id"] == incident["threat_actor_entity_id"]
            else 0.0
        )
    else:
        actor_similarity = calculate_field_similarity(
            article["threat_actor"], incident["threat_actor"]
        )

    text_similarity = jaccard_index(article["tokens"], anchor_tokens)

    article_types = attack_type_set(article["attack_type"])
    incident_types = attack_type_set(incident["attack_type"])
    if article_types and incident_types:
        type_similarity = jaccard_index(article_types, incident_types)
    else:
        type_similarity = None

    components = [
        (target_similarity, TARGET_WEIGHT),
        (text_similarity, TEXT_WEIGHT),
        (actor_similarity, THREAT_ACTOR_WEIGHT),
        (type_similarity, ATTACK_TYPE_WEIGHT),
        (
            calculate_field_similarity(article["location"], incident["location"]),
            LOCATION_WEIGHT,
        ),
        (
            calculate_date_similarity(article["attack_date"], incident["attack_date"]),
            ATTACK_DATE_WEIGHT,
        ),
        (
            calculate_field_similarity(
                article["attack_method"], incident["attack_method"]
            ),
            ATTACK_METHOD_WEIGHT,
        ),
    ]

    # Hanya komponen yang dapat dibandingkan yang ikut dihitung
    total_weight = sum(weight for value, weight in components if value is not None)
    if total_weight == 0:
        score = 0.0
    else:
        score = (
            sum(value * weight for value, weight in components if value is not None)
            / total_weight
        )
    return score, {
        "target": target_similarity,
        "actor": actor_similarity,
        "text": text_similarity,
    }


def target_identity(article, incident, anchor_tokens):
    """True bila target artikel dan incident jelas sama (nama khas yang sama
    lewat entity, teks, atau kemunculan nama di teks sisi lain)."""
    incident_target = normalize_value(incident["target"])
    # Kesamaan target hanya menjadi bukti bila namanya cukup khas
    if distinctive_tokens(article["target"]):
        if (
            article["target_entity_id"]
            and article["target_entity_id"] == incident["target_entity_id"]
        ):
            return True
        if article["target"] == incident_target:
            return True
    return target_in_text(article, incident, anchor_tokens)


def has_identity_signal(article, incident, details):
    """Bukti bahwa artikel dan incident membicarakan target/pelaku yang sama.

    Termasuk bila nama target yang terekstrak di satu sisi muncul utuh di
    teks judul+ringkasan sisi lain, karena ekstraksi target sering hanya
    berhasil pada salah satu artikel.
    """
    anchor_tokens = set((incident["anchor_text"] or "").split())
    if target_identity(article, incident, anchor_tokens):
        return True
    if shared_rare_tokens(article["tokens"], anchor_tokens):
        return True

    return bool(
        article["threat_actor_entity_id"]
        and article["threat_actor_entity_id"] == incident["threat_actor_entity_id"]
        and details["text"] >= MIN_TEXT_SIMILARITY_WITH_ACTOR
    )


def find_best_incident(conn, article):
    """Incident terbaik yang lolos hard constraint dan salah satu syarat gabung.

    Syarat gabung: sinyal identitas (skor >= MIN_SCORE_WITH_IDENTITY) atau
    teks sangat mirip (skor >= INCIDENT_SIMILARITY_THRESHOLD).
    """
    best_incident = None
    best_score = 0.0
    for incident in get_existing_incidents(conn, article):
        if not passes_hard_constraints(article, incident):
            continue
        score, details = calculate_incident_similarity(article, incident)
        if has_identity_signal(article, incident, details):
            required = MIN_SCORE_WITH_IDENTITY
        elif details["text"] >= TEXT_SIMILARITY_THRESHOLD:
            required = INCIDENT_SIMILARITY_THRESHOLD
        else:
            continue
        if score >= required and score > best_score:
            best_score = score
            best_incident = incident
    if best_incident is None:
        return None, 0.0
    return best_incident, best_score


# --- Penyimpanan incident ---
def generate_incident_id(anchor_uid):
    """ID incident deterministik dari article_uid artikel pertamanya.

    Memakai article_uid (turunan URL), bukan article_id (nomor urut), agar ID
    incident sama di database mana pun yang berisi artikel yang sama.
    """
    raw = f"INCIDENT|{anchor_uid}"
    hash_value = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12].upper()
    return f"INCIDENT_{hash_value}"


def create_incident(conn, article, confidence):
    """Simpan incident baru dengan artikel ini sebagai jangkar; kembalikan incident_id."""
    incident_id = generate_incident_id(article["article_uid"] or article["article_id"])
    now = get_timestamp()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO v05_incidents (
            incident_id, attack_type, target, target_entity_id, threat_actor,
            threat_actor_entity_id, location, attack_date, attack_method,
            document_count, incident_confidence, clustering_method,
            anchor_article_id, anchor_text, anchor_published_date,
            last_published_date, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            article["article_id"],
            " ".join(sorted(article["tokens"])),
            article["published_date"],
            article["published_date"],
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
            clustering_method, assigned_at, pipeline_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            incident_id,
            article_id,
            similarity_score,
            similarity_confidence,
            clustering_method,
            get_timestamp(),
            pipeline_stamp(),
        ),
    )
    inserted = cursor.rowcount
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


def get_document_incident(conn, article_id):
    """incident_id yang sudah tercatat untuk artikel di v05_incident_documents."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT incident_id FROM v05_incident_documents WHERE article_id = ?",
        (article_id,),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def update_incident(conn, incident_id, article, similarity_score):
    """Lengkapi field incident yang kosong dan perpanjang rentang tanggal terbitnya."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            attack_type, target, target_entity_id, threat_actor,
            threat_actor_entity_id, location, attack_date, attack_method,
            incident_confidence, last_published_date, anchor_text
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
        old_last_published,
        old_anchor_text,
    ) = row

    last_published = old_last_published
    if article["published_date"] and (
        last_published is None or article["published_date"] > last_published
    ):
        last_published = article["published_date"]

    # Token teks incident diperkaya dengan artikel baru agar liputan lanjutan
    # (nama target, pelaku) ikut dikenali, dengan batas agar cluster besar
    # tidak terus "menggelinding" menyerap berita lain
    anchor_tokens = set((old_anchor_text or "").split())
    if len(anchor_tokens) < MAX_ANCHOR_TOKENS:
        anchor_tokens |= article["tokens"]
    anchor_text = " ".join(sorted(anchor_tokens))

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
            last_published_date = ?,
            anchor_text = ?,
            updated_at = ?
        WHERE incident_id = ?
        """,
        (
            old_attack_type or article["attack_type"],
            old_target or article["target"],
            old_target_entity_id or article["target_entity_id"],
            old_actor or article["threat_actor"],
            old_actor_entity_id or article["threat_actor_entity_id"],
            old_location or article["location"],
            old_date or article["attack_date"],
            old_method or article["attack_method"],
            new_confidence,
            last_published,
            anchor_text,
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


# --- Rantai incident ---
def _table_exists(conn, table):
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,))
    return cursor.fetchone() is not None


def merge_incident(conn, head, other):
    """Pindahkan seluruh artikel ``other`` ke ``head``, hapus ``other``.

    Hasil V0.6 kedua incident dihapus agar dihitung ulang pada run V0.6.
    ``head`` (dict) diperbarui di tempat.
    """
    cursor = conn.cursor()
    head_id, other_id = head["incident_id"], other["incident_id"]
    cursor.execute(
        "UPDATE v05_incident_documents SET incident_id = ?, clustering_method = 'CHAINED' "
        "WHERE incident_id = ?",
        (head_id, other_id),
    )
    cursor.execute(
        "UPDATE v05_processed_articles SET incident_id = ? WHERE incident_id = ?",
        (head_id, other_id),
    )

    anchor_tokens = set((head["anchor_text"] or "").split())
    if len(anchor_tokens) < MAX_ANCHOR_TOKENS:
        anchor_tokens |= set((other["anchor_text"] or "").split())
    head["anchor_text"] = " ".join(sorted(anchor_tokens))
    head["last_published_date"] = max(
        head["last_published_date"] or "", other["last_published_date"] or ""
    ) or None
    for field in ("attack_type", "threat_actor", "threat_actor_entity_id", "location",
                  "attack_date", "attack_method", "target_entity_id"):
        head[field] = head[field] or other[field]
    head["document_count"] = (head["document_count"] or 0) + (other["document_count"] or 0)

    cursor.execute(
        """
        UPDATE v05_incidents
        SET anchor_text = ?, last_published_date = ?, attack_type = ?, threat_actor = ?,
            threat_actor_entity_id = ?, location = ?, attack_date = ?, attack_method = ?,
            target_entity_id = ?, document_count = ?, updated_at = ?
        WHERE incident_id = ?
        """,
        (
            head["anchor_text"], head["last_published_date"], head["attack_type"],
            head["threat_actor"], head["threat_actor_entity_id"], head["location"],
            head["attack_date"], head["attack_method"], head["target_entity_id"],
            head["document_count"], get_timestamp(), head_id,
        ),
    )
    cursor.execute("DELETE FROM v05_incidents WHERE incident_id = ?", (other_id,))

    for table in ("v06_evidence", "v06_source_relations", "v06_processed_incidents"):
        if _table_exists(conn, table):
            cursor.execute(
                f"DELETE FROM {table} WHERE incident_id IN (?, ?)", (head_id, other_id)
            )


def chain_incidents(conn):
    """Gabungkan incident lanjutan bertarget sama; kembalikan jumlah penggabungan.

    Kasus yang liputannya berminggu-minggu terpecah oleh jendela
    PUBLISHED_WINDOW_DAYS; di sini incident dengan target khas yang sama dan jenis
    serangan yang tidak bertentangan dirangkai bila jaraknya <= CHAIN_GAP_DAYS.
    """
    cursor = conn.cursor()
    cursor.execute(f"{_INCIDENT_SELECT} WHERE target IS NOT NULL ORDER BY anchor_published_date")
    groups = {}
    for row in cursor.fetchall():
        incident = dict(zip(INCIDENT_COLUMNS, row))
        target = normalize_value(incident["target"])
        if not distinctive_tokens(target):
            continue
        # Kunci berdasarkan nama target; entity id tidak dipakai agar incident yang
        # targetnya dikenali V0.4 dan yang hanya berupa teks tetap satu kelompok.
        groups.setdefault(target, []).append(incident)

    merges = 0
    for items in groups.values():
        if len(items) < 2:
            continue
        head = items[0]
        for incident in items[1:]:
            head_last = parse_date(head["last_published_date"]) or parse_date(
                head["anchor_published_date"]
            )
            incident_first = parse_date(incident["anchor_published_date"])
            if head_last is None or incident_first is None:
                head = incident
                continue
            gap_days = (incident_first - head_last).days
            # Rentang liputan yang tumpang tindih (gap <= 0) berarti kejadian yang
            # sama walau labelnya berbeda; bila berurutan, keluarga jenis serangan
            # harus cocok.
            if gap_days <= CHAIN_GAP_DAYS and (
                gap_days <= 0
                or families_compatible(head["attack_type"], incident["attack_type"])
            ):
                merge_incident(conn, head, incident)
                merges += 1
            else:
                head = incident
    conn.commit()
    return merges


# --- Pemrosesan ---
def process_article(conn, row):
    """Kelompokkan satu artikel ke incident lama atau buat incident baru."""
    article = prepare_article(conn, row)
    article_id = article["article_id"]

    # Pengaman ganda: walaupun get_next_batch() sudah memfilter, cek lagi.
    cursor = conn.cursor()
    cursor.execute(
        "SELECT incident_id FROM v05_processed_articles WHERE article_id = ? LIMIT 1",
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
        incident_id = best_incident["incident_id"]
        inserted = save_incident_document(
            conn, incident_id, article_id, best_score, best_score, "RULE_BASED_CLUSTERING"
        )
        if inserted:
            update_incident(conn, incident_id, article, best_score)
        else:
            # Artikel sudah tercatat pada incident lain (data lama): ikuti itu.
            incident_id = get_document_incident(conn, article_id) or incident_id
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
    """Proses satu batch dalam satu transaksi; artikel yang gagal di-rollback."""
    batch_articles = 0
    batch_new_incidents = 0
    batch_existing_incidents = 0
    batch_skipped = 0
    if not conn.in_transaction:
        conn.execute("BEGIN")

    for row in rows:
        article_id = row[0]
        conn.execute("SAVEPOINT article")
        try:
            result = process_article(conn, row)
            conn.execute("RELEASE SAVEPOINT article")
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
            conn.execute("ROLLBACK TO SAVEPOINT article")
            conn.execute("RELEASE SAVEPOINT article")
            print("\n⚠️ ERROR")
            print(f"Article ID : {article_id}")
            print(f"Error      : {error}")
            continue

    conn.commit()
    return (
        batch_articles,
        batch_new_incidents,
        batch_existing_incidents,
        batch_skipped,
    )


def database_summary(conn):
    """Kandidat V0.3, artikel terproses, sisa, incident, dokumen, incident multi-artikel."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM v03_information_extraction")
    total_v03 = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM v05_processed_articles")
    processed_articles = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM v05_incidents")
    total_incidents = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM v05_incident_documents")
    total_documents = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM v05_incidents WHERE document_count > 1")
    multi_document = cursor.fetchone()[0]
    remaining = max(total_v03 - processed_articles, 0)
    return (
        total_v03,
        processed_articles,
        remaining,
        total_incidents,
        total_documents,
        multi_document,
    )


def print_status(title, summary):
    """Cetak blok status database V0.5."""
    total_v03, processed, remaining, incidents, documents, multi_document = summary
    print("\n==================================================")
    print(f"   {title}")
    print("==================================================")
    print(f"V03 candidates      : {total_v03}")
    print(f"Processed articles  : {processed}")
    print(f"Remaining           : {remaining}")
    print(f"Incidents           : {incidents}")
    print(f"Incident documents  : {documents}")
    print(f"Incidents 2+ docs   : {multi_document}")
    print("==================================================")


def run():
    """Jalankan V0.5 Incident Clustering sampai tidak ada artikel tersisa."""
    print("\n==================================================")
    print("   V0.5 INCIDENT CLUSTERING")
    print("==================================================")

    started_at = get_timestamp()
    conn = get_connection()
    create_tables(conn)
    migrate_existing_tables(conn)
    create_v05_indexes(conn)  # setelah migrasi
    ensure_article_uid(conn)
    load_token_document_frequency(conn)

    recovered = recover_previous_processed_articles(conn)
    if recovered > 0:
        print("\n♻️ Recovery:")
        print(f"   {recovered} artikel lama ditandai sebagai PROCESSED.")
    recover_document_counts(conn)

    print_status("V0.5 DATABASE STATUS", database_summary(conn))

    total_articles_processed = 0
    total_new_incidents = 0
    total_existing_incidents = 0

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
            if batch_articles == 0 and batch_skipped == 0:
                print("\n⚠️ Seluruh artikel dalam batch gagal diproses; berhenti.")
                break

            current = database_summary(conn)
            print("\n==================================================")
            print(f"Batch articles      : {batch_articles}")
            print(f"New incidents       : {batch_new_incidents}")
            print(f"Existing incidents  : {batch_existing_incidents}")
            print(f"Skipped             : {batch_skipped}")
            print(f"Total processed     : {current[1]}")
            print(f"Total incidents     : {current[3]}")
            print(f"Total documents     : {current[4]}")
            print(f"Remaining           : {current[2]}")
            print("==================================================")

        merged = chain_incidents(conn)
        if merged:
            print(f"\n🔗 {merged} incident lanjutan dirangkai ke incident sebelumnya.")
    except KeyboardInterrupt:
        conn.commit()
        print("\n\n⚠️ V0.5 dihentikan oleh user.")
        print("Batch yang sudah selesai telah disimpan.")
        print("Jalankan kembali untuk melanjutkan.")
    finally:
        conn.close()

    conn = get_connection()
    final = database_summary(conn)
    record_run(conn, "v05_incident_clustering", started_at, total_articles_processed)
    conn.close()

    print_status("V0.5 ANALYSIS SUMMARY", final)
    print(f"Articles processed this run  : {total_articles_processed}")
    print(f"New incidents this run       : {total_new_incidents}")
    print(f"Existing incidents this run  : {total_existing_incidents}")
    print("==================================================")
    if final[2] == 0:
        print("   ✅ V0.5 INCIDENT CLUSTERING SELESAI")
    else:
        print("   ⏸️ V0.5 BELUM SELESAI")
        print("   Jalankan kembali untuk melanjutkan.")
    print("==================================================")


if __name__ == "__main__":
    run()
