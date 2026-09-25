# ============================================================
# V0.5 - INCIDENT CLUSTERING
# ============================================================
#
# CSAIS - Cyber Social Attack Intelligence System
#
# Fungsi:
#   1. Mengambil hasil V0.3 Information Extraction
#   2. Menggunakan canonical entity dari V0.4
#   3. Mengelompokkan artikel yang kemungkinan membahas
#      incident cyber attack yang sama
#   4. Membuat incident baru jika tidak ditemukan incident
#      yang sesuai
#   5. Menyimpan hubungan article -> incident
#   6. Menandai article sebagai sudah diproses
#
# IMPORTANT:
#
# Satu article_id hanya boleh diproses satu kali.
#
# Jangan menggunakan v05_incident_documents sebagai satu-satunya
# indikator bahwa article sudah diproses.
#
# Karena itu digunakan:
#
#   v05_processed_articles
#
# ============================================================


# ============================================================
# IMPORT LIBRARY
# ============================================================

import sqlite3
import re
import hashlib
from datetime import datetime, timezone


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = "database/csais.db"

BATCH_SIZE = 500

INCIDENT_SIMILARITY_THRESHOLD = 0.70

DATE_WINDOW_DAYS = 14


# ============================================================
# SIMILARITY WEIGHTS
# ============================================================

TARGET_WEIGHT = 0.30

ATTACK_TYPE_WEIGHT = 0.20

THREAT_ACTOR_WEIGHT = 0.20

LOCATION_WEIGHT = 0.10

ATTACK_DATE_WEIGHT = 0.10

ATTACK_METHOD_WEIGHT = 0.10


# ============================================================
# ENTITY TYPES
# ============================================================

TARGET_ENTITY_TYPE = "ORGANIZATION"

THREAT_ACTOR_ENTITY_TYPE = "THREAT_ACTOR"

LOCATION_ENTITY_TYPE = "LOCATION"


# ============================================================
# UNKNOWN VALUES
# ============================================================

UNKNOWN_VALUES = {
    "",
    "unknown",
    "none",
    "null",
    "n/a",
    "na",
    "-"
}


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():

    conn = sqlite3.connect(DB_PATH)

    conn.execute(
        "PRAGMA journal_mode=WAL"
    )

    conn.execute(
        "PRAGMA synchronous=NORMAL"
    )

    conn.execute(
        "PRAGMA busy_timeout=30000"
    )

    return conn


# ============================================================
# TIMESTAMP
# ============================================================

def get_timestamp():

    return datetime.now(
        timezone.utc
    ).isoformat()


# ============================================================
# NORMALIZE TEXT
# ============================================================

def normalize_text(text):

    if text is None:
        return ""

    text = str(text)

    text = text.lower()

    text = text.strip()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text


# ============================================================
# IS UNKNOWN
# ============================================================

def is_unknown(value):

    if value is None:
        return True

    normalized = normalize_text(
        value
    )

    return normalized in UNKNOWN_VALUES


# ============================================================
# NORMALIZE VALUE
# ============================================================

def normalize_value(value):

    if is_unknown(value):
        return None

    return normalize_text(
        value
    )


# ============================================================
# DATE PARSER
# ============================================================

def parse_date(value):

    if is_unknown(value):
        return None

    value = str(
        value
    ).strip()

    # ========================================================
    # ISO FORMAT
    # ========================================================

    try:

        parsed = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00"
            )
        )

        if parsed.tzinfo is None:

            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed

    except Exception:
        pass

    # ========================================================
    # DATE ONLY
    # ========================================================

    try:

        parsed = datetime.strptime(
            value,
            "%Y-%m-%d"
        )

        return parsed.replace(
            tzinfo=timezone.utc
        )

    except Exception:
        pass

    return None


# ============================================================
# DATE SIMILARITY
# ============================================================

def calculate_date_similarity(
    date_a,
    date_b
):

    parsed_a = parse_date(
        date_a
    )

    parsed_b = parse_date(
        date_b
    )

    if (
        parsed_a is None
        or parsed_b is None
    ):

        return 0.0

    difference = abs(
        (
            parsed_a
            -
            parsed_b
        ).total_seconds()
    )

    difference_days = (
        difference
        /
        86400.0
    )

    if difference_days > DATE_WINDOW_DAYS:

        return 0.0

    return (
        1.0
        -
        (
            difference_days
            /
            DATE_WINDOW_DAYS
        )
    )


# ============================================================
# FIELD SIMILARITY
# ============================================================

def calculate_field_similarity(
    value_a,
    value_b
):

    normalized_a = normalize_value(
        value_a
    )

    normalized_b = normalize_value(
        value_b
    )

    # ========================================================
    # BOTH UNKNOWN
    # ========================================================

    if (
        normalized_a is None
        and normalized_b is None
    ):

        return None

    # ========================================================
    # ONE UNKNOWN
    # ========================================================

    if (
        normalized_a is None
        or normalized_b is None
    ):

        return None

    # ========================================================
    # EXACT MATCH
    # ========================================================

    if normalized_a == normalized_b:

        return 1.0

    # ========================================================
    # TOKEN SIMILARITY
    # ========================================================

    tokens_a = set(
        normalized_a.split()
    )

    tokens_b = set(
        normalized_b.split()
    )

    if not tokens_a or not tokens_b:

        return 0.0

    intersection = (
        tokens_a.intersection(
            tokens_b
        )
    )

    union = (
        tokens_a.union(
            tokens_b
        )
    )

    if not union:

        return 0.0

    return (
        len(intersection)
        /
        len(union)
    )


# ============================================================
# CREATE DATABASE TABLES
# ============================================================

def create_tables(
    conn
):

    cursor = conn.cursor()

    # ========================================================
    # INCIDENT TABLE
    # ========================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS
        v05_incidents (

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
        """
    )

    # ========================================================
    # INCIDENT DOCUMENT TABLE
    # ========================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS
        v05_incident_documents (

            relation_id INTEGER PRIMARY KEY AUTOINCREMENT,

            incident_id TEXT NOT NULL,

            article_id INTEGER NOT NULL,

            similarity_score REAL,

            similarity_confidence REAL,

            clustering_method TEXT,

            assigned_at TEXT,

            UNIQUE (
                article_id
            )
        )
        """
    )

    # ========================================================
    # PROCESSED ARTICLE TABLE
    # ========================================================
    #
    # INI ADALAH BAGIAN TERPENTING.
    #
    # Satu article_id hanya boleh muncul satu kali.
    #
    # ========================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS
        v05_processed_articles (

            article_id INTEGER PRIMARY KEY,

            incident_id TEXT,

            processed_at TEXT NOT NULL
        )
        """
    )

    conn.commit()


# ============================================================
# MIGRATE EXISTING V05 STRUCTURE
# ============================================================
#
# Jika v05_incidents sudah dibuat oleh versi lama, beberapa
# kolom mungkin belum ada.
#
# ============================================================

def migrate_existing_tables(
    conn
):

    cursor = conn.cursor()

    # ========================================================
    # V05 INCIDENT TABLE
    # ========================================================

    cursor.execute(
        """
        PRAGMA table_info(
            v05_incidents
        )
        """
    )

    incident_columns = {
        row[1]
        for row in cursor.fetchall()
    }

    required_incident_columns = {

        "attack_type":
            "TEXT",

        "target":
            "TEXT",

        "target_entity_id":
            "TEXT",

        "threat_actor":
            "TEXT",

        "threat_actor_entity_id":
            "TEXT",

        "location":
            "TEXT",

        "attack_date":
            "TEXT",

        "attack_method":
            "TEXT",

        "document_count":
            "INTEGER DEFAULT 0",

        "incident_confidence":
            "REAL DEFAULT 0.0",

        "clustering_method":
            "TEXT",

        "created_at":
            "TEXT",

        "updated_at":
            "TEXT"
    }

    for column_name, column_type in (
        required_incident_columns.items()
    ):

        if column_name not in incident_columns:

            cursor.execute(
                f"""
                ALTER TABLE
                v05_incidents

                ADD COLUMN
                {column_name}
                {column_type}
                """
            )

    # ========================================================
    # V05 INCIDENT DOCUMENT TABLE
    # ========================================================
    #
    # SQLite CREATE TABLE IF NOT EXISTS tidak mengubah tabel
    # lama. Karena itu schema lama harus diperiksa satu per satu.
    #
    # Kolom assigned_at adalah penyebab error sebelumnya.
    #
    # ========================================================

    cursor.execute(
        """
        PRAGMA table_info(
            v05_incident_documents
        )
        """
    )

    document_columns = {
        row[1]
        for row in cursor.fetchall()
    }

    required_document_columns = {

        "similarity_score":
            "REAL",

        "similarity_confidence":
            "REAL",

        "clustering_method":
            "TEXT",

        "assigned_at":
            "TEXT"
    }

    for column_name, column_type in (
        required_document_columns.items()
    ):

        if column_name not in document_columns:

            cursor.execute(
                f"""
                ALTER TABLE
                v05_incident_documents

                ADD COLUMN
                {column_name}
                {column_type}
                """
            )

    # ========================================================
    # V05 PROCESSED ARTICLE TABLE
    # ========================================================

    cursor.execute(
        """
        PRAGMA table_info(
            v05_processed_articles
        )
        """
    )

    processed_columns = {
        row[1]
        for row in cursor.fetchall()
    }

    if "incident_id" not in processed_columns:

        cursor.execute(
            """
            ALTER TABLE
            v05_processed_articles

            ADD COLUMN
            incident_id TEXT
            """
        )

    if "processed_at" not in processed_columns:

        cursor.execute(
            """
            ALTER TABLE
            v05_processed_articles

            ADD COLUMN
            processed_at TEXT
            """
        )

    # ========================================================
    # COMMIT MIGRATION
    # ========================================================

    conn.commit()


# ============================================================
# CREATE V05 INDEXES
# ============================================================
#
# INDEX dibuat SETELAH migration.
# Ini penting karena database lama dapat belum mempunyai
# target_entity_id atau kolom V05 lainnya.
#
# ============================================================

def create_v05_indexes(
    conn
):

    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_v05_incident_documents_incident

        ON v05_incident_documents(
            incident_id
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_v05_incident_documents_article

        ON v05_incident_documents(
            article_id
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_v05_processed_article

        ON v05_processed_articles(
            article_id
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_v05_incidents_target

        ON v05_incidents(
            target_entity_id
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_v05_incidents_attack_type

        ON v05_incidents(
            attack_type
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_v05_incidents_actor

        ON v05_incidents(
            threat_actor_entity_id
        )
        """
    )

    conn.commit()


# ============================================================
# RECOVER PREVIOUSLY PROCESSED ARTICLES
# ============================================================
#
# Versi V05 lama belum mempunyai
# v05_processed_articles.
#
# Artikel yang sudah mempunyai relation pada
# v05_incident_documents dianggap sudah diproses.
#
# ============================================================

def recover_previous_processed_articles(
    conn
):

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO
        v05_processed_articles (

            article_id,

            incident_id,

            processed_at

        )

        SELECT

            article_id,

            incident_id,

            COALESCE(
                assigned_at,
                ?
            )

        FROM v05_incident_documents
        """,
        (
            get_timestamp(),
        )
    )

    recovered = cursor.rowcount

    conn.commit()

    return recovered


# ============================================================
# RECOVER DOCUMENT COUNTS
# ============================================================
#
# Memastikan document_count di v05_incidents sesuai dengan
# jumlah article yang benar-benar terhubung.
#
# ============================================================

def recover_document_counts(
    conn
):

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE v05_incidents

        SET document_count = (

            SELECT COUNT(*)

            FROM v05_incident_documents d

            WHERE d.incident_id =
                  v05_incidents.incident_id
        )
        """
    )

    conn.commit()


# ============================================================
# GET NEXT ARTICLE BATCH
# ============================================================

def get_next_batch(
    conn
):

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT

            v03.article_id,

            v03.attack_type,

            v03.target,

            v03.target_organization,

            v03.threat_actor,

            v03.location,

            v03.attack_date,

            v03.attack_method

        FROM v03_information_extraction v03

        LEFT JOIN
        v05_processed_articles p

            ON v03.article_id =
               p.article_id

        WHERE p.article_id IS NULL

        ORDER BY
            v03.article_id

        LIMIT ?
        """,
        (
            BATCH_SIZE,
        )
    )

    return cursor.fetchall()


# ============================================================
# GET CANONICAL ENTITY
# ============================================================

def get_canonical_entity(
    conn,
    article_id,
    entity_type
):

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT

            m.entity_id,

            m.canonical_name

        FROM v04_entity_mentions m

        WHERE m.article_id = ?

        AND m.entity_type = ?

        ORDER BY
            m.resolution_score DESC

        LIMIT 1
        """,
        (
            article_id,
            entity_type
        )
    )

    row = cursor.fetchone()

    if row is None:

        return (
            None,
            None
        )

    return (
        row[0],
        row[1]
    )


# ============================================================
# PREPARE ARTICLE DATA
# ============================================================

def prepare_article(
    conn,
    row
):

    (
        article_id,
        attack_type,
        target,
        target_organization,
        threat_actor,
        location,
        attack_date,
        attack_method
    ) = row

    # ========================================================
    # TARGET
    # ========================================================

    target_entity_id, canonical_target = (
        get_canonical_entity(
            conn,
            article_id,
            TARGET_ENTITY_TYPE
        )
    )

    if canonical_target is None:

        if not is_unknown(
            target_organization
        ):

            canonical_target = (
                target_organization
            )

        elif not is_unknown(
            target
        ):

            canonical_target = target

    # ========================================================
    # THREAT ACTOR
    # ========================================================

    threat_actor_entity_id, canonical_actor = (
        get_canonical_entity(
            conn,
            article_id,
            THREAT_ACTOR_ENTITY_TYPE
        )
    )

    if canonical_actor is None:

        canonical_actor = (
            None
            if is_unknown(
                threat_actor
            )
            else threat_actor
        )

    # ========================================================
    # LOCATION
    # ========================================================

    location_entity_id, canonical_location = (
        get_canonical_entity(
            conn,
            article_id,
            LOCATION_ENTITY_TYPE
        )
    )

    if canonical_location is None:

        canonical_location = (
            None
            if is_unknown(
                location
            )
            else location
        )

    # ========================================================
    # RETURN STRUCTURE
    # ========================================================

    return {

        "article_id":
            article_id,

        "attack_type":
            normalize_value(
                attack_type
            ),

        "target":
            normalize_value(
                canonical_target
            ),

        "target_entity_id":
            target_entity_id,

        "threat_actor":
            normalize_value(
                canonical_actor
            ),

        "threat_actor_entity_id":
            threat_actor_entity_id,

        "location":
            normalize_value(
                canonical_location
            ),

        "attack_date":
            normalize_value(
                attack_date
            ),

        "attack_method":
            normalize_value(
                attack_method
            )
    }


# ============================================================
# GET EXISTING INCIDENT CANDIDATES
# ============================================================
#
# Jangan membandingkan setiap article dengan seluruh incident.
#
# Gunakan blocking sederhana terlebih dahulu.
#
# ============================================================

def get_existing_incidents(
    conn,
    article
):

    cursor = conn.cursor()

    target_entity_id = article[
        "target_entity_id"
    ]

    attack_type = article[
        "attack_type"
    ]

    threat_actor_entity_id = article[
        "threat_actor_entity_id"
    ]

    candidates = []

    # ========================================================
    # STRATEGY 1
    # TARGET ENTITY
    # ========================================================

    if target_entity_id:

        cursor.execute(
            """
            SELECT

                incident_id,

                attack_type,

                target,

                target_entity_id,

                threat_actor,

                threat_actor_entity_id,

                location,

                attack_date,

                attack_method,

                document_count,

                incident_confidence

            FROM v05_incidents

            WHERE target_entity_id = ?

            ORDER BY
                updated_at DESC
            """,
            (
                target_entity_id,
            )
        )

        candidates.extend(
            cursor.fetchall()
        )

    # ========================================================
    # STRATEGY 2
    # THREAT ACTOR
    # ========================================================

    if threat_actor_entity_id:

        cursor.execute(
            """
            SELECT

                incident_id,

                attack_type,

                target,

                target_entity_id,

                threat_actor,

                threat_actor_entity_id,

                location,

                attack_date,

                attack_method,

                document_count,

                incident_confidence

            FROM v05_incidents

            WHERE threat_actor_entity_id = ?

            ORDER BY
                updated_at DESC
            """,
            (
                threat_actor_entity_id,
            )
        )

        candidates.extend(
            cursor.fetchall()
        )

    # ========================================================
    # STRATEGY 3
    # ATTACK TYPE
    # ========================================================

    if (
        attack_type
        and
        not candidates
    ):

        cursor.execute(
            """
            SELECT

                incident_id,

                attack_type,

                target,

                target_entity_id,

                threat_actor,

                threat_actor_entity_id,

                location,

                attack_date,

                attack_method,

                document_count,

                incident_confidence

            FROM v05_incidents

            WHERE attack_type = ?

            ORDER BY
                updated_at DESC

            LIMIT 1000
            """,
            (
                attack_type,
            )
        )

        candidates.extend(
            cursor.fetchall()
        )

    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    unique = {}

    for candidate in candidates:

        unique[
            candidate[0]
        ] = candidate

    return list(
        unique.values()
    )


# ============================================================
# HARD CONSTRAINT CHECK
# ============================================================
#
# Mencegah incident yang jelas berbeda digabung.
#
# ============================================================

def passes_hard_constraints(
    article,
    incident
):

    # ========================================================
    # INDEX INCIDENT
    # ========================================================

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
        incident_confidence
    ) = incident

    # ========================================================
    # TARGET ENTITY CONFLICT
    # ========================================================
    #
    # Jika kedua artikel memiliki canonical target berbeda,
    # jangan merge.
    #
    # ========================================================

    article_target_id = article[
        "target_entity_id"
    ]

    if (
        article_target_id
        and
        incident_target_entity_id
        and
        article_target_id
        !=
        incident_target_entity_id
    ):

        return False

    # ========================================================
    # THREAT ACTOR CONFLICT
    # ========================================================

    article_actor_id = article[
        "threat_actor_entity_id"
    ]

    if (
        article_actor_id
        and
        incident_actor_entity_id
        and
        article_actor_id
        !=
        incident_actor_entity_id
    ):

        return False

    # ========================================================
    # ATTACK TYPE CONFLICT
    # ========================================================

    article_attack_type = article[
        "attack_type"
    ]

    if (
        article_attack_type
        and
        incident_attack_type
        and
        article_attack_type
        !=
        incident_attack_type
    ):

        return False

    # ========================================================
    # DATE CONSTRAINT
    # ========================================================

    article_date = article[
        "attack_date"
    ]

    if (
        article_date
        and
        incident_date
    ):

        date_similarity = (
            calculate_date_similarity(
                article_date,
                incident_date
            )
        )

        if date_similarity == 0.0:

            return False

    return True


# ============================================================
# CALCULATE INCIDENT SIMILARITY
# ============================================================

def calculate_incident_similarity(
    article,
    incident
):

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
        incident_confidence
    ) = incident

    # ========================================================
    # TARGET
    # ========================================================

    if (
        article["target_entity_id"]
        and
        incident_target_entity_id
    ):

        target_similarity = (
            1.0
            if (
                article[
                    "target_entity_id"
                ]
                ==
                incident_target_entity_id
            )
            else 0.0
        )

    else:

        target_similarity = (
            calculate_field_similarity(
                article["target"],
                incident_target
            )
        )

    # ========================================================
    # ATTACK TYPE
    # ========================================================

    attack_type_similarity = (
        calculate_field_similarity(
            article["attack_type"],
            incident_attack_type
        )
    )

    # ========================================================
    # THREAT ACTOR
    # ========================================================

    if (
        article[
            "threat_actor_entity_id"
        ]
        and
        incident_actor_entity_id
    ):

        actor_similarity = (
            1.0
            if (
                article[
                    "threat_actor_entity_id"
                ]
                ==
                incident_actor_entity_id
            )
            else 0.0
        )

    else:

        actor_similarity = (
            calculate_field_similarity(
                article["threat_actor"],
                incident_actor
            )
        )

    # ========================================================
    # LOCATION
    # ========================================================

    location_similarity = (
        calculate_field_similarity(
            article["location"],
            incident_location
        )
    )

    # ========================================================
    # ATTACK DATE
    # ========================================================

    date_similarity = (
        calculate_date_similarity(
            article["attack_date"],
            incident_date
        )
    )

    # ========================================================
    # ATTACK METHOD
    # ========================================================

    method_similarity = (
        calculate_field_similarity(
            article["attack_method"],
            incident_method
        )
    )

    # ========================================================
    # WEIGHTED SCORE
    # ========================================================

    weighted_values = []

    weighted_weights = []

    if target_similarity is not None:

        weighted_values.append(
            target_similarity
        )

        weighted_weights.append(
            TARGET_WEIGHT
        )

    if attack_type_similarity is not None:

        weighted_values.append(
            attack_type_similarity
        )

        weighted_weights.append(
            ATTACK_TYPE_WEIGHT
        )

    if actor_similarity is not None:

        weighted_values.append(
            actor_similarity
        )

        weighted_weights.append(
            THREAT_ACTOR_WEIGHT
        )

    if location_similarity is not None:

        weighted_values.append(
            location_similarity
        )

        weighted_weights.append(
            LOCATION_WEIGHT
        )

    if date_similarity > 0:

        weighted_values.append(
            date_similarity
        )

        weighted_weights.append(
            ATTACK_DATE_WEIGHT
        )

    if method_similarity is not None:

        weighted_values.append(
            method_similarity
        )

        weighted_weights.append(
            ATTACK_METHOD_WEIGHT
        )

    if not weighted_weights:

        return 0.0

    total_weight = sum(
        weighted_weights
    )

    weighted_score = sum(
        value * weight
        for value, weight
        in zip(
            weighted_values,
            weighted_weights
        )
    )

    if total_weight == 0:

        return 0.0

    return (
        weighted_score
        /
        total_weight
    )


# ============================================================
# FIND BEST INCIDENT
# ============================================================

def find_best_incident(
    conn,
    article
):

    candidates = (
        get_existing_incidents(
            conn,
            article
        )
    )

    best_incident = None

    best_score = 0.0

    for incident in candidates:

        # ====================================================
        # HARD CONSTRAINT
        # ====================================================

        if not passes_hard_constraints(
            article,
            incident
        ):

            continue

        # ====================================================
        # SIMILARITY
        # ====================================================

        score = (
            calculate_incident_similarity(
                article,
                incident
            )
        )

        # ====================================================
        # BEST MATCH
        # ====================================================

        if score > best_score:

            best_score = score

            best_incident = incident

    # ========================================================
    # THRESHOLD
    # ========================================================

    if (
        best_incident is not None
        and
        best_score
        >=
        INCIDENT_SIMILARITY_THRESHOLD
    ):

        return (
            best_incident,
            best_score
        )

    return (
        None,
        0.0
    )


# ============================================================
# GENERATE INCIDENT ID
# ============================================================

def generate_incident_id(
    article_id
):

    raw = (
        f"INCIDENT|"
        f"{article_id}|"
        f"{get_timestamp()}"
    )

    hash_value = hashlib.sha1(
        raw.encode(
            "utf-8"
        )
    ).hexdigest()[:12].upper()

    return (
        f"INCIDENT_{hash_value}"
    )


# ============================================================
# CREATE INCIDENT
# ============================================================

def create_incident(
    conn,
    article,
    confidence
):

    incident_id = generate_incident_id(
        article["article_id"]
    )

    now = get_timestamp()

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO
        v05_incidents (

            incident_id,

            attack_type,

            target,

            target_entity_id,

            threat_actor,

            threat_actor_entity_id,

            location,

            attack_date,

            attack_method,

            document_count,

            incident_confidence,

            clustering_method,

            created_at,

            updated_at

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            incident_id,

            article[
                "attack_type"
            ],

            article[
                "target"
            ],

            article[
                "target_entity_id"
            ],

            article[
                "threat_actor"
            ],

            article[
                "threat_actor_entity_id"
            ],

            article[
                "location"
            ],

            article[
                "attack_date"
            ],

            article[
                "attack_method"
            ],

            0,

            confidence,

            "RULE_BASED",

            now,

            now
        )
    )

    return incident_id


# ============================================================
# SAVE INCIDENT DOCUMENT
# ============================================================

def save_incident_document(
    conn,
    incident_id,
    article_id,
    similarity_score,
    similarity_confidence,
    clustering_method
):

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO
        v05_incident_documents (

            incident_id,

            article_id,

            similarity_score,

            similarity_confidence,

            clustering_method,

            assigned_at

        )

        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            incident_id,

            article_id,

            similarity_score,

            similarity_confidence,

            clustering_method,

            get_timestamp()
        )
    )

    inserted = cursor.rowcount

    # ========================================================
    # UPDATE DOCUMENT COUNT
    # ========================================================

    if inserted == 1:

        cursor.execute(
            """
            UPDATE v05_incidents

            SET document_count = (
                SELECT COUNT(*)

                FROM v05_incident_documents d

                WHERE d.incident_id =
                    v05_incidents.incident_id
            ),

            updated_at = ?

            WHERE incident_id = ?
            """,
            (
                get_timestamp(),
                incident_id
            )
        )

    return inserted


# ============================================================
# UPDATE INCIDENT
# ============================================================
#
# Update beberapa field jika incident mendapatkan informasi
# baru dari article berikutnya.
#
# ============================================================

def update_incident(
    conn,
    incident_id,
    article,
    similarity_score
):

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT

            attack_type,
            target,
            target_entity_id,
            threat_actor,
            threat_actor_entity_id,
            location,
            attack_date,
            attack_method,
            incident_confidence

        FROM v05_incidents

        WHERE incident_id = ?
        """,
        (
            incident_id,
        )
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
        old_confidence
    ) = row

    # ========================================================
    # USE EXISTING VALUES WHEN AVAILABLE
    # ========================================================

    attack_type = (
        old_attack_type
        or
        article["attack_type"]
    )

    target = (
        old_target
        or
        article["target"]
    )

    target_entity_id = (
        old_target_entity_id
        or
        article[
            "target_entity_id"
        ]
    )

    actor = (
        old_actor
        or
        article["threat_actor"]
    )

    actor_entity_id = (
        old_actor_entity_id
        or
        article[
            "threat_actor_entity_id"
        ]
    )

    location = (
        old_location
        or
        article["location"]
    )

    attack_date = (
        old_date
        or
        article["attack_date"]
    )

    attack_method = (
        old_method
        or
        article["attack_method"]
    )

    # ========================================================
    # CONFIDENCE
    # ========================================================

    if old_confidence is None:

        new_confidence = (
            similarity_score
        )

    else:

        new_confidence = max(
            old_confidence,
            similarity_score
        )

    # ========================================================
    # UPDATE
    # ========================================================

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

            incident_id
        )
    )


# ============================================================
# MARK ARTICLE AS PROCESSED
# ============================================================

def mark_article_processed(
    conn,
    article_id,
    incident_id
):

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO
        v05_processed_articles (

            article_id,

            incident_id,

            processed_at

        )

        VALUES (?, ?, ?)
        """,
        (
            article_id,
            incident_id,
            get_timestamp()
        )
    )


# ============================================================
# PROCESS ARTICLE
# ============================================================

def process_article(
    conn,
    row
):

    article = prepare_article(
        conn,
        row
    )

    article_id = article[
        "article_id"
    ]

    # ========================================================
    # DOUBLE SAFETY CHECK
    # ========================================================
    #
    # Walaupun get_next_batch() sudah memfilter,
    # kita cek lagi sebelum memproses.
    #
    # ========================================================

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT incident_id

        FROM v05_processed_articles

        WHERE article_id = ?

        LIMIT 1
        """,
        (
            article_id,
        )
    )

    already_processed = (
        cursor.fetchone()
    )

    if already_processed:

        return {
            "status":
                "ALREADY_PROCESSED",

            "incident_id":
                already_processed[0],

            "score":
                1.0,

            "method":
                "SKIP"
        }

    # ========================================================
    # FIND EXISTING INCIDENT
    # ========================================================

    (
        best_incident,
        best_score
    ) = find_best_incident(
        conn,
        article
    )

    # ========================================================
    # EXISTING INCIDENT
    # ========================================================

    if best_incident is not None:

        incident_id = (
            best_incident[0]
        )

        update_incident(
            conn,
            incident_id,
            article,
            best_score
        )

        save_incident_document(
            conn,
            incident_id,
            article_id,
            best_score,
            best_score,
            "RULE_BASED_CLUSTERING"
        )

        mark_article_processed(
            conn,
            article_id,
            incident_id
        )

        return {
            "status":
                "EXISTING_INCIDENT",

            "incident_id":
                incident_id,

            "score":
                best_score,

            "method":
                "EXISTING_INCIDENT"
        }

    # ========================================================
    # NEW INCIDENT
    # ========================================================

    incident_id = create_incident(
        conn,
        article,
        1.0
    )

    save_incident_document(
        conn,
        incident_id,
        article_id,
        1.0,
        1.0,
        "NEW_INCIDENT"
    )

    mark_article_processed(
        conn,
        article_id,
        incident_id
    )

    return {
        "status":
            "NEW_INCIDENT",

        "incident_id":
            incident_id,

        "score":
            1.0,

        "method":
            "NEW_INCIDENT"
    }


# ============================================================
# PROCESS BATCH
# ============================================================

def process_batch(
    conn,
    rows
):

    batch_articles = 0

    batch_new_incidents = 0

    batch_existing_incidents = 0

    batch_skipped = 0

    for row in rows:

        article_id = row[0]

        try:

            result = process_article(
                conn,
                row
            )

            status = result[
                "status"
            ]

            if status == (
                "NEW_INCIDENT"
            ):

                batch_new_incidents += 1

            elif status == (
                "EXISTING_INCIDENT"
            ):

                batch_existing_incidents += 1

            elif status == (
                "ALREADY_PROCESSED"
            ):

                batch_skipped += 1

            if status != (
                "ALREADY_PROCESSED"
            ):

                batch_articles += 1

            # =================================================
            # DISPLAY
            # =================================================

            print(
                "\n--------------------------------------------------"
            )

            print(
                f"Article ID : {article_id}"
            )

            print(
                f"Attack     : "
                f"{row[1] or 'UNKNOWN'}"
            )

            print(
                f"Target     : "
                f"{row[2] or 'UNKNOWN'}"
            )

            print(
                f"Actor      : "
                f"{row[4] or 'UNKNOWN'}"
            )

            print(
                f"Date       : "
                f"{row[6] or 'UNKNOWN'}"
            )

            print(
                f"Incident   : "
                f"{result['incident_id']}"
            )

            print(
                f"Score      : "
                f"{result['score']:.2f}"
            )

            print(
                f"Method     : "
                f"{result['method']}"
            )

        except Exception as error:

            print(
                "\n⚠️ ERROR"
            )

            print(
                f"Article ID : {article_id}"
            )

            print(
                f"Error      : {error}"
            )

            # =================================================
            # ARTICLE TIDAK DITANDAI PROCESSED
            # =================================================
            #
            # Agar bisa dicoba kembali pada run berikutnya.
            #
            # =================================================

            continue

    # ========================================================
    # COMMIT BATCH
    # ========================================================

    conn.commit()

    return (
        batch_articles,
        batch_new_incidents,
        batch_existing_incidents,
        batch_skipped
    )


# ============================================================
# DATABASE SUMMARY
# ============================================================

def database_summary(
    conn
):

    cursor = conn.cursor()

    # ========================================================
    # V03 ARTICLES
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM v03_information_extraction
        """
    )

    total_v03 = (
        cursor.fetchone()[0]
    )

    # ========================================================
    # PROCESSED ARTICLES
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM v05_processed_articles
        """
    )

    processed_articles = (
        cursor.fetchone()[0]
    )

    # ========================================================
    # INCIDENTS
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM v05_incidents
        """
    )

    total_incidents = (
        cursor.fetchone()[0]
    )

    # ========================================================
    # INCIDENT DOCUMENTS
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM v05_incident_documents
        """
    )

    total_documents = (
        cursor.fetchone()[0]
    )

    # ========================================================
    # REMAINING
    # ========================================================

    remaining = (
        total_v03
        -
        processed_articles
    )

    if remaining < 0:

        remaining = 0

    return (
        total_v03,
        processed_articles,
        remaining,
        total_incidents,
        total_documents
    )


# ============================================================
# RUN V05
# ============================================================

def run():

    print(
        "\n=================================================="
    )

    print(
        "   V0.5 INCIDENT CLUSTERING"
    )

    print(
        "=================================================="
    )

    conn = get_connection()

    # ========================================================
    # CREATE TABLES
    # ========================================================

    create_tables(
        conn
    )

    # ========================================================
    # MIGRATE EXISTING TABLES
    # ========================================================

    migrate_existing_tables(
        conn
    )

    # ========================================================
    # CREATE INDEXES AFTER MIGRATION
    # ========================================================

    create_v05_indexes(
        conn
    )

    # ========================================================
    # RECOVER OLD RESULTS
    # ========================================================

    recovered = (
        recover_previous_processed_articles(
            conn
        )
    )

    if recovered > 0:

        print(
            "\n♻️ Recovery:"
        )

        print(
            f"   {recovered} artikel lama "
            f"ditandai sebagai PROCESSED."
        )

    # ========================================================
    # RECOVER DOCUMENT COUNTS
    # ========================================================

    recover_document_counts(
        conn
    )

    # ========================================================
    # INITIAL SUMMARY
    # ========================================================

    (
        total_v03,
        processed_articles,
        remaining,
        total_incidents,
        total_documents
    ) = database_summary(
        conn
    )

    print(
        "\n=================================================="
    )

    print(
        "   V0.5 DATABASE STATUS"
    )

    print(
        "=================================================="
    )

    print(
        f"V03 candidates      : "
        f"{total_v03}"
    )

    print(
        f"Processed articles  : "
        f"{processed_articles}"
    )

    print(
        f"Remaining           : "
        f"{remaining}"
    )

    print(
        f"Incidents           : "
        f"{total_incidents}"
    )

    print(
        f"Incident documents  : "
        f"{total_documents}"
    )

    print(
        "=================================================="
    )

    # ========================================================
    # RUN COUNTERS
    # ========================================================

    total_articles_processed = 0

    total_new_incidents = 0

    total_existing_incidents = 0

    total_skipped = 0

    # ========================================================
    # MAIN LOOP
    # ========================================================

    try:

        while True:

            # =================================================
            # GET NEXT BATCH
            # =================================================

            rows = get_next_batch(
                conn
            )

            # =================================================
            # NO MORE ARTICLES
            # =================================================

            if not rows:

                break

            # =================================================
            # PROCESS
            # =================================================

            (
                batch_articles,
                batch_new_incidents,
                batch_existing_incidents,
                batch_skipped
            ) = process_batch(
                conn,
                rows
            )

            # =================================================
            # UPDATE COUNTERS
            # =================================================

            total_articles_processed += (
                batch_articles
            )

            total_new_incidents += (
                batch_new_incidents
            )

            total_existing_incidents += (
                batch_existing_incidents
            )

            total_skipped += (
                batch_skipped
            )

            # =================================================
            # CURRENT STATUS
            # =================================================

            (
                current_v03,
                current_processed,
                current_remaining,
                current_incidents,
                current_documents
            ) = database_summary(
                conn
            )

            print(
                "\n=================================================="
            )

            print(
                f"Batch articles      : "
                f"{batch_articles}"
            )

            print(
                f"New incidents       : "
                f"{batch_new_incidents}"
            )

            print(
                f"Existing incidents  : "
                f"{batch_existing_incidents}"
            )

            print(
                f"Skipped             : "
                f"{batch_skipped}"
            )

            print(
                f"Total processed     : "
                f"{current_processed}"
            )

            print(
                f"Total incidents     : "
                f"{current_incidents}"
            )

            print(
                f"Total documents     : "
                f"{current_documents}"
            )

            print(
                f"Remaining           : "
                f"{current_remaining}"
            )

            print(
                "=================================================="
            )

    except KeyboardInterrupt:

        # ====================================================
        # USER INTERRUPT
        # ====================================================

        conn.commit()

        print(
            "\n\n⚠️ V0.5 dihentikan oleh user."
        )

        print(
            "Batch yang sudah selesai telah disimpan."
        )

        print(
            "Jalankan kembali untuk melanjutkan."
        )

    finally:

        conn.close()

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    conn = get_connection()

    (
        final_v03,
        final_processed,
        final_remaining,
        final_incidents,
        final_documents
    ) = database_summary(
        conn
    )

    conn.close()

    print(
        "\n=================================================="
    )

    print(
        "   V0.5 ANALYSIS SUMMARY"
    )

    print(
        "=================================================="
    )

    print(
        f"V03 candidates      : "
        f"{final_v03}"
    )

    print(
        f"Processed articles  : "
        f"{final_processed}"
    )

    print(
        f"Remaining           : "
        f"{final_remaining}"
    )

    print(
        f"Total incidents     : "
        f"{final_incidents}"
    )

    print(
        f"Incident documents  : "
        f"{final_documents}"
    )

    print(
        f"Articles processed "
        f"this run           : "
        f"{total_articles_processed}"
    )

    print(
        f"New incidents "
        f"this run            : "
        f"{total_new_incidents}"
    )

    print(
        f"Existing incidents "
        f"this run            : "
        f"{total_existing_incidents}"
    )

    print(
        "=================================================="
    )

    if final_remaining == 0:

        print(
            "   ✅ V0.5 INCIDENT CLUSTERING SELESAI"
        )

    else:

        print(
            "   ⏸️ V0.5 BELUM SELESAI"
        )

        print(
            "   Jalankan kembali untuk melanjutkan."
        )

    print(
        "=================================================="
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    run()