# ============================================================
# V0.4 - ENTITY RESOLUTION
# ============================================================
#
# CSAIS - Cyber Social Attack Intelligence System
#
# Fungsi:
#   1. Mengambil hasil V0.3
#   2. Mengekstrak entity mention
#   3. Melakukan entity resolution
#   4. Menghubungkan mention dengan canonical entity
#   5. Menyimpan entity dan entity mention
#   6. Menandai article sebagai sudah diproses
#
# IMPORTANT:
#   Artikel yang tidak memiliki entity tetap dianggap
#   sebagai artikel yang sudah diproses.
#
#   Hal ini mencegah infinite loop pada proses batch.
#
# ============================================================


# ============================================================
# IMPORT LIBRARY
# ============================================================

import sqlite3
import re
import hashlib
import math
from datetime import datetime, timezone


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = "database/csais.db"

BATCH_SIZE = 500

FUZZY_THRESHOLD = 0.85

MAX_ENTITY_NAME_LENGTH = 300


# ============================================================
# ENTITY TYPES
# ============================================================

ENTITY_TYPES = [
    "ORGANIZATION",
    "THREAT_ACTOR",
    "LOCATION"
]


# ============================================================
# KNOWN ENTITY ALIASES
# ============================================================
#
# Dictionary ini merupakan baseline.
#
# Tujuan:
#   Beberapa nama berbeda dapat mengarah ke entity
#   yang sama.
#
# ============================================================

KNOWN_ENTITY_ALIASES = {

    # ========================================================
    # ORGANIZATIONS
    # ========================================================

    "Bank Mandiri": [
        "bank mandiri",
        "pt bank mandiri",
        "mandiri",
        "mandiri bank",
        "bank mandiri persero"
    ],

    "Microsoft": [
        "microsoft",
        "microsoft corporation",
        "microsoft corp",
        "microsoft corp."
    ],

    "Google": [
        "google",
        "google llc",
        "google inc",
        "google corporation"
    ],

    "Apple": [
        "apple",
        "apple inc",
        "apple inc.",
        "apple corporation"
    ],

    "Amazon": [
        "amazon",
        "amazon.com",
        "amazon web services",
        "aws"
    ],

    "Rostelecom": [
        "rostelecom",
        "rostelcom",
        "pjsc rostelecom"
    ],

    "AT&T": [
        "at&t",
        "att",
        "at and t"
    ],

    "Verizon": [
        "verizon",
        "verizon communications",
        "verizon wireless"
    ],

    "T-Mobile": [
        "t-mobile",
        "t mobile",
        "t-mobile us"
    ],

    "Meta": [
        "meta",
        "meta platforms",
        "meta platforms inc",
        "facebook",
        "facebook inc"
    ],

    "TikTok": [
        "tiktok",
        "tiktok inc",
        "bytedance",
        "byte dance"
    ],

    "Telegram": [
        "telegram",
        "telegram messenger"
    ],

    "WhatsApp": [
        "whatsapp",
        "whatsapp messenger"
    ],

    "Cloudflare": [
        "cloudflare",
        "cloudflare inc"
    ],

    "Cisco": [
        "cisco",
        "cisco systems",
        "cisco systems inc"
    ],

    "IBM": [
        "ibm",
        "international business machines"
    ],

    "Oracle": [
        "oracle",
        "oracle corporation"
    ],

    "Intel": [
        "intel",
        "intel corporation"
    ],

    "NVIDIA": [
        "nvidia",
        "nvidia corporation"
    ],

    "OpenAI": [
        "openai",
        "openai inc"
    ],

    "CrowdStrike": [
        "crowdstrike",
        "crowdstrike holdings"
    ],

    "Palo Alto Networks": [
        "palo alto networks",
        "palo alto",
        "pan"
    ],

    "Fortinet": [
        "fortinet",
        "fortinet inc"
    ],

    "Kaspersky": [
        "kaspersky",
        "kaspersky lab",
        "kaspersky laboratory"
    ],

    "ESET": [
        "eset",
        "eset spol"
    ],

    "Recorded Future": [
        "recorded future"
    ],

    "Mandiant": [
        "mandiant",
        "mandiant inc"
    ],

    "FireEye": [
        "fireeye",
        "fireeye inc"
    ],

    "Cisco Talos": [
        "cisco talos",
        "talos"
    ],

    # ========================================================
    # THREAT ACTORS
    # ========================================================

    "APT28": [
        "apt28",
        "fancy bear",
        "sofacy",
        "sednit",
        "strontium"
    ],

    "APT29": [
        "apt29",
        "cozy bear",
        "the dukes",
        "midnight blizzard"
    ],

    "Lazarus Group": [
        "lazarus group",
        "lazarus",
        "hidden cobra"
    ],

    "Sandworm": [
        "sandworm",
        "sandworm team"
    ],

    "LockBit": [
        "lockbit",
        "lockbit group",
        "lockbit 3.0"
    ],

    "Cl0p": [
        "cl0p",
        "clop",
        "cl0p ransomware"
    ],

    "BlackCat": [
        "blackcat",
        "blackcat ransomware",
        "alphv",
        "alphransomware"
    ],

    "Scattered Spider": [
        "scattered spider",
        "octo tempest",
        "0ktapus"
    ],

    "Anonymous": [
        "anonymous",
        "anonymous collective"
    ],

    "KillNet": [
        "killnet",
        "kill net"
    ],

    "NoName057(16)": [
        "noname057(16)",
        "noname05716",
        "noname057"
    ]
}


# ============================================================
# LOCATION ALIASES
# ============================================================

LOCATION_ALIASES = {

    "United States": [
        "united states",
        "united states of america",
        "usa",
        "u.s.",
        "u.s.a.",
        "america"
    ],

    "United Kingdom": [
        "united kingdom",
        "uk",
        "u.k.",
        "great britain",
        "england"
    ],

    "Russia": [
        "russia",
        "russian federation"
    ],

    "Ukraine": [
        "ukraine"
    ],

    "China": [
        "china",
        "people's republic of china",
        "prc"
    ],

    "Indonesia": [
        "indonesia",
        "republic of indonesia"
    ],

    "Singapore": [
        "singapore"
    ],

    "Malaysia": [
        "malaysia"
    ],

    "Australia": [
        "australia"
    ],

    "India": [
        "india"
    ],

    "Japan": [
        "japan"
    ],

    "South Korea": [
        "south korea",
        "republic of korea",
        "korea"
    ],

    "North Korea": [
        "north korea",
        "dprk"
    ],

    "Vietnam": [
        "vietnam",
        "viet nam"
    ],

    "Thailand": [
        "thailand"
    ],

    "Philippines": [
        "philippines"
    ],

    "Brazil": [
        "brazil"
    ],

    "Canada": [
        "canada"
    ],

    "Germany": [
        "germany"
    ],

    "France": [
        "france"
    ],

    "Italy": [
        "italy"
    ],

    "Spain": [
        "spain"
    ],

    "Netherlands": [
        "netherlands",
        "the netherlands",
        "holland"
    ],

    "Israel": [
        "israel"
    ],

    "Iran": [
        "iran",
        "islamic republic of iran"
    ],

    "Turkey": [
        "turkey",
        "türkiye"
    ],

    "Taiwan": [
        "taiwan"
    ],

    "Hong Kong": [
        "hong kong"
    ]
}


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():

    conn = sqlite3.connect(DB_PATH)

    conn.execute("PRAGMA journal_mode=WAL")

    conn.execute("PRAGMA synchronous=NORMAL")

    conn.execute("PRAGMA busy_timeout=30000")

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
# NORMALIZE ENTITY NAME
# ============================================================

def normalize_entity_name(name):

    if name is None:
        return ""

    name = str(name)

    name = name.lower()

    name = name.strip()

    name = re.sub(
        r"[\"'`]",
        "",
        name
    )

    name = re.sub(
        r"[(),;:]+",
        " ",
        name
    )

    name = re.sub(
        r"\s+",
        " ",
        name
    )

    return name.strip()


# ============================================================
# GENERATE ENTITY ID
# ============================================================

def generate_entity_id(
    entity_type,
    canonical_name
):

    raw = (
        f"{entity_type}|"
        f"{normalize_entity_name(canonical_name)}"
    )

    return hashlib.sha1(
        raw.encode("utf-8")
    ).hexdigest()[:20]


# ============================================================
# TOKENIZE
# ============================================================

def tokenize(text):

    text = normalize_entity_name(text)

    if not text:
        return set()

    return set(
        token
        for token in text.split()
        if token
    )


# ============================================================
# JACCARD SIMILARITY
# ============================================================

def jaccard_similarity(
    text_a,
    text_b
):

    tokens_a = tokenize(text_a)

    tokens_b = tokenize(text_b)

    if not tokens_a or not tokens_b:
        return 0.0

    intersection = tokens_a.intersection(
        tokens_b
    )

    union = tokens_a.union(
        tokens_b
    )

    if not union:
        return 0.0

    return len(intersection) / len(union)


# ============================================================
# CHARACTER SIMILARITY
# ============================================================

def character_similarity(
    text_a,
    text_b
):

    a = normalize_entity_name(text_a)

    b = normalize_entity_name(text_b)

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    distance = levenshtein_distance(
        a,
        b
    )

    max_length = max(
        len(a),
        len(b)
    )

    if max_length == 0:
        return 0.0

    return 1.0 - (
        distance / max_length
    )


# ============================================================
# LEVENSHTEIN DISTANCE
# ============================================================

def levenshtein_distance(
    text_a,
    text_b
):

    if text_a == text_b:
        return 0

    if len(text_a) == 0:
        return len(text_b)

    if len(text_b) == 0:
        return len(text_a)

    previous_row = list(
        range(len(text_b) + 1)
    )

    for i, char_a in enumerate(
        text_a,
        start=1
    ):

        current_row = [i]

        for j, char_b in enumerate(
            text_b,
            start=1
        ):

            insertion = (
                current_row[j - 1] + 1
            )

            deletion = (
                previous_row[j] + 1
            )

            substitution = (
                previous_row[j - 1]
                + (
                    0
                    if char_a == char_b
                    else 1
                )
            )

            current_row.append(
                min(
                    insertion,
                    deletion,
                    substitution
                )
            )

        previous_row = current_row

    return previous_row[-1]


# ============================================================
# FUZZY SIMILARITY
# ============================================================

def calculate_similarity(
    mention,
    canonical_name
):

    normalized_mention = normalize_entity_name(
        mention
    )

    normalized_canonical = normalize_entity_name(
        canonical_name
    )

    if not normalized_mention:
        return 0.0

    if not normalized_canonical:
        return 0.0

    if normalized_mention == normalized_canonical:
        return 1.0

    jaccard = jaccard_similarity(
        normalized_mention,
        normalized_canonical
    )

    character = character_similarity(
        normalized_mention,
        normalized_canonical
    )

    return (
        (jaccard * 0.50)
        + (character * 0.50)
    )


# ============================================================
# LOAD KNOWN ALIASES
# ============================================================

def build_alias_index():

    alias_index = {}

    for canonical_name, aliases in (
        KNOWN_ENTITY_ALIASES.items()
    ):

        for alias in aliases:

            alias_index[
                normalize_entity_name(alias)
            ] = (
                "ORGANIZATION",
                canonical_name
            )

    for canonical_name, aliases in (
        LOCATION_ALIASES.items()
    ):

        for alias in aliases:

            alias_index[
                normalize_entity_name(alias)
            ] = (
                "LOCATION",
                canonical_name
            )

    return alias_index


# ============================================================
# GET CANONICAL ALIAS
# ============================================================

def resolve_known_alias(
    entity_type,
    mention,
    alias_index
):

    normalized = normalize_entity_name(
        mention
    )

    result = alias_index.get(
        normalized
    )

    if result is None:
        return None

    result_type, canonical_name = result

    if result_type != entity_type:
        return None

    return canonical_name


# ============================================================
# CREATE DATABASE TABLES
# ============================================================

def create_tables(conn):

    cursor = conn.cursor()

    # ========================================================
    # ENTITY TABLE
    # ========================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS v04_entities (

            entity_id TEXT PRIMARY KEY,

            entity_type TEXT NOT NULL,

            canonical_name TEXT NOT NULL,

            normalized_name TEXT NOT NULL,

            mention_count INTEGER DEFAULT 0,

            resolution_method TEXT,

            created_at TEXT,

            updated_at TEXT
        )
        """
    )

    # ========================================================
    # ENTITY MENTION TABLE
    # ========================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS v04_entity_mentions (

            mention_id INTEGER PRIMARY KEY AUTOINCREMENT,

            article_id INTEGER NOT NULL,

            entity_id TEXT NOT NULL,

            entity_type TEXT NOT NULL,

            original_name TEXT NOT NULL,

            canonical_name TEXT NOT NULL,

            resolution_score REAL,

            resolution_confidence REAL,

            resolution_method TEXT,

            resolved_at TEXT,

            UNIQUE (
                article_id,
                entity_id,
                entity_type,
                original_name
            )
        )
        """
    )

    # ========================================================
    # PROCESSED ARTICLE TABLE
    # ========================================================
    #
    # IMPORTANT:
    #
    # Jangan menggunakan v04_entity_mentions sebagai indikator
    # apakah sebuah artikel sudah diproses.
    #
    # Artikel bisa saja tidak memiliki entity.
    #
    # Karena itu kita membutuhkan tabel khusus.
    #
    # ========================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS v04_processed_articles (

            article_id INTEGER PRIMARY KEY,

            processed_at TEXT NOT NULL
        )
        """
    )

    # ========================================================
    # INDEXES
    # ========================================================

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_v04_mentions_article
        ON v04_entity_mentions(article_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_v04_mentions_entity
        ON v04_entity_mentions(entity_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_v04_processed_article
        ON v04_processed_articles(article_id)
        """
    )

    conn.commit()


# ============================================================
# RECOVER PREVIOUSLY PROCESSED ARTICLES
# ============================================================
#
# Karena versi V04 sebelumnya tidak mempunyai
# v04_processed_articles, 500 artikel yang sudah menghasilkan
# mention perlu dimigrasikan menjadi processed.
#
# ============================================================

def recover_previous_processed_articles(conn):

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO
        v04_processed_articles (
            article_id,
            processed_at
        )

        SELECT DISTINCT
            article_id,
            ?
        FROM v04_entity_mentions
        """,
        (
            get_timestamp(),
        )
    )

    recovered = cursor.rowcount

    conn.commit()

    return recovered


# ============================================================
# GET NEXT BATCH
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
            v03.location

        FROM v03_information_extraction v03

        LEFT JOIN v04_processed_articles p

            ON v03.article_id = p.article_id

        WHERE p.article_id IS NULL

        ORDER BY v03.article_id

        LIMIT ?
        """,
        (
            BATCH_SIZE,
        )
    )

    return cursor.fetchall()


# ============================================================
# FIND EXISTING ENTITY
# ============================================================

def find_existing_entity(
    conn,
    entity_type,
    mention
):

    cursor = conn.cursor()

    normalized_mention = normalize_entity_name(
        mention
    )

    if not normalized_mention:
        return None

    # ========================================================
    # STEP 1 - EXACT MATCH
    # ========================================================

    cursor.execute(
        """
        SELECT

            entity_id,
            canonical_name,
            normalized_name

        FROM v04_entities

        WHERE entity_type = ?

        AND normalized_name = ?

        LIMIT 1
        """,
        (
            entity_type,
            normalized_mention
        )
    )

    row = cursor.fetchone()

    if row:

        return {
            "entity_id": row[0],
            "canonical_name": row[1],
            "score": 1.0,
            "method": "EXACT_MATCH"
        }

    # ========================================================
    # STEP 2 - FUZZY MATCH
    # ========================================================

    cursor.execute(
        """
        SELECT

            entity_id,
            canonical_name,
            normalized_name

        FROM v04_entities

        WHERE entity_type = ?
        """,
        (
            entity_type,
        )
    )

    candidates = cursor.fetchall()

    best_match = None

    best_score = 0.0

    for candidate in candidates:

        entity_id = candidate[0]

        canonical_name = candidate[1]

        score = calculate_similarity(
            mention,
            canonical_name
        )

        if score > best_score:

            best_score = score

            best_match = {
                "entity_id": entity_id,
                "canonical_name": canonical_name,
                "score": score,
                "method": "FUZZY_MATCH"
            }

    if (
        best_match is not None
        and best_score >= FUZZY_THRESHOLD
    ):

        return best_match

    return None


# ============================================================
# CREATE ENTITY
# ============================================================

def create_entity(
    conn,
    entity_type,
    canonical_name,
    resolution_method
):

    entity_id = generate_entity_id(
        entity_type,
        canonical_name
    )

    now = get_timestamp()

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO v04_entities (

            entity_id,
            entity_type,
            canonical_name,
            normalized_name,
            mention_count,
            resolution_method,
            created_at,
            updated_at

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entity_id,
            entity_type,
            canonical_name,
            normalize_entity_name(
                canonical_name
            ),
            0,
            resolution_method,
            now,
            now
        )
    )

    return entity_id


# ============================================================
# UPDATE ENTITY TIMESTAMP
# ============================================================

def update_entity_timestamp(
    conn,
    entity_id
):

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE v04_entities

        SET updated_at = ?

        WHERE entity_id = ?
        """,
        (
            get_timestamp(),
            entity_id
        )
    )


# ============================================================
# SAVE ENTITY MENTION
# ============================================================
#
# IMPORTANT:
#
# INSERT OR IGNORE digunakan untuk memastikan mention yang
# sama tidak dimasukkan berkali-kali.
#
# mention_count hanya bertambah jika INSERT benar-benar terjadi.
#
# ============================================================

def save_entity_mention(
    conn,
    article_id,
    entity_type,
    original_name,
    canonical_name,
    entity_id,
    resolution_score,
    resolution_confidence,
    resolution_method
):

    cursor = conn.cursor()

    now = get_timestamp()

    cursor.execute(
        """
        INSERT OR IGNORE INTO
        v04_entity_mentions (

            article_id,
            entity_id,
            entity_type,
            original_name,
            canonical_name,
            resolution_score,
            resolution_confidence,
            resolution_method,
            resolved_at

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            article_id,
            entity_id,
            entity_type,
            original_name,
            canonical_name,
            resolution_score,
            resolution_confidence,
            resolution_method,
            now
        )
    )

    inserted = cursor.rowcount

    # ========================================================
    # UPDATE MENTION COUNT
    # ========================================================
    #
    # Hanya dilakukan jika mention benar-benar baru.
    #
    # ========================================================

    if inserted == 1:

        cursor.execute(
            """
            UPDATE v04_entities

            SET mention_count =
                COALESCE(mention_count, 0) + 1,

                updated_at = ?

            WHERE entity_id = ?
            """,
            (
                now,
                entity_id
            )
        )

    return inserted


# ============================================================
# MARK ARTICLE AS PROCESSED
# ============================================================

def mark_article_processed(
    conn,
    article_id
):

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO
        v04_processed_articles (

            article_id,
            processed_at

        )

        VALUES (?, ?)
        """,
        (
            article_id,
            get_timestamp()
        )
    )


# ============================================================
# EXTRACT MENTION FROM FIELD
# ============================================================

def extract_field_mentions(
    value
):

    if value is None:
        return []

    value = str(value).strip()

    if not value:
        return []

    # ========================================================
    # HANDLE UNKNOWN VALUES
    # ========================================================

    unknown_values = {
        "",
        "unknown",
        "none",
        "null",
        "n/a",
        "na",
        "-"
    }

    if normalize_entity_name(value) in unknown_values:
        return []

    # ========================================================
    # SPLIT MULTIPLE VALUES
    # ========================================================

    parts = re.split(
        r"\s*[;,|]\s*",
        value
    )

    results = []

    for part in parts:

        part = part.strip()

        if not part:
            continue

        if len(part) > MAX_ENTITY_NAME_LENGTH:
            continue

        results.append(part)

    return results


# ============================================================
# RESOLVE ONE MENTION
# ============================================================

def resolve_mention(
    conn,
    entity_type,
    mention,
    alias_index
):

    mention = mention.strip()

    if not mention:
        return None

    # ========================================================
    # STEP 1 - KNOWN ALIAS
    # ========================================================

    known_canonical = resolve_known_alias(
        entity_type,
        mention,
        alias_index
    )

    if known_canonical:

        existing = find_existing_entity(
            conn,
            entity_type,
            known_canonical
        )

        if existing:

            return {
                "entity_id": existing["entity_id"],
                "canonical_name": existing["canonical_name"],
                "score": 1.0,
                "confidence": 1.0,
                "method": "EXACT_MATCH"
            }

        entity_id = create_entity(
            conn,
            entity_type,
            known_canonical,
            "KNOWN_ALIAS"
        )

        return {
            "entity_id": entity_id,
            "canonical_name": known_canonical,
            "score": 1.0,
            "confidence": 1.0,
            "method": "KNOWN_ALIAS"
        }

    # ========================================================
    # STEP 2 - EXISTING ENTITY
    # ========================================================

    existing = find_existing_entity(
        conn,
        entity_type,
        mention
    )

    if existing:

        score = existing["score"]

        confidence = min(
            max(score, 0.0),
            1.0
        )

        return {
            "entity_id": existing["entity_id"],
            "canonical_name": existing["canonical_name"],
            "score": score,
            "confidence": confidence,
            "method": existing["method"]
        }

    # ========================================================
    # STEP 3 - CREATE NEW ENTITY
    # ========================================================

    entity_id = create_entity(
        conn,
        entity_type,
        mention,
        "NEW_ENTITY"
    )

    return {
        "entity_id": entity_id,
        "canonical_name": mention,
        "score": 1.0,
        "confidence": 1.0,
        "method": "NEW_ENTITY"
    }


# ============================================================
# PROCESS ARTICLE
# ============================================================

def process_article(
    conn,
    row,
    alias_index
):

    (
        article_id,
        attack_type,
        target,
        target_organization,
        threat_actor,
        location
    ) = row

    mentions_found = 0

    # ========================================================
    # ORGANIZATION
    # ========================================================

    organization_values = []

    organization_values.extend(
        extract_field_mentions(
            target_organization
        )
    )

    organization_values.extend(
        extract_field_mentions(
            target
        )
    )

    # Remove duplicates while preserving order

    organization_values = list(
        dict.fromkeys(
            organization_values
        )
    )

    for mention in organization_values:

        entity_result = resolve_mention(
            conn,
            "ORGANIZATION",
            mention,
            alias_index
        )

        if entity_result is None:
            continue

        inserted = save_entity_mention(
            conn,
            article_id,
            "ORGANIZATION",
            mention,
            entity_result["canonical_name"],
            entity_result["entity_id"],
            entity_result["score"],
            entity_result["confidence"],
            entity_result["method"]
        )

        if inserted:

            mentions_found += 1

            print(
                "\nEntity Mention"
            )

            print(
                f"    Article ID : {article_id}"
            )

            print(
                f"    Type       : ORGANIZATION"
            )

            print(
                f"    Mention    : {mention}"
            )

            print(
                f"    Canonical  : "
                f"{entity_result['canonical_name']}"
            )

            print(
                f"    Entity ID  : "
                f"{entity_result['entity_id']}"
            )

            print(
                f"    Score      : "
                f"{entity_result['score']:.2f}"
            )

            print(
                f"    Method     : "
                f"{entity_result['method']}"
            )

    # ========================================================
    # THREAT ACTOR
    # ========================================================

    threat_actor_values = (
        extract_field_mentions(
            threat_actor
        )
    )

    threat_actor_values = list(
        dict.fromkeys(
            threat_actor_values
        )
    )

    for mention in threat_actor_values:

        entity_result = resolve_mention(
            conn,
            "THREAT_ACTOR",
            mention,
            alias_index
        )

        if entity_result is None:
            continue

        inserted = save_entity_mention(
            conn,
            article_id,
            "THREAT_ACTOR",
            mention,
            entity_result["canonical_name"],
            entity_result["entity_id"],
            entity_result["score"],
            entity_result["confidence"],
            entity_result["method"]
        )

        if inserted:

            mentions_found += 1

            print(
                "\nEntity Mention"
            )

            print(
                f"    Article ID : {article_id}"
            )

            print(
                f"    Type       : THREAT_ACTOR"
            )

            print(
                f"    Mention    : {mention}"
            )

            print(
                f"    Canonical  : "
                f"{entity_result['canonical_name']}"
            )

            print(
                f"    Entity ID  : "
                f"{entity_result['entity_id']}"
            )

            print(
                f"    Score      : "
                f"{entity_result['score']:.2f}"
            )

            print(
                f"    Method     : "
                f"{entity_result['method']}"
            )

    # ========================================================
    # LOCATION
    # ========================================================

    location_values = (
        extract_field_mentions(
            location
        )
    )

    location_values = list(
        dict.fromkeys(
            location_values
        )
    )

    for mention in location_values:

        entity_result = resolve_mention(
            conn,
            "LOCATION",
            mention,
            alias_index
        )

        if entity_result is None:
            continue

        inserted = save_entity_mention(
            conn,
            article_id,
            "LOCATION",
            mention,
            entity_result["canonical_name"],
            entity_result["entity_id"],
            entity_result["score"],
            entity_result["confidence"],
            entity_result["method"]
        )

        if inserted:

            mentions_found += 1

            print(
                "\nEntity Mention"
            )

            print(
                f"    Article ID : {article_id}"
            )

            print(
                f"    Type       : LOCATION"
            )

            print(
                f"    Mention    : {mention}"
            )

            print(
                f"    Canonical  : "
                f"{entity_result['canonical_name']}"
            )

            print(
                f"    Entity ID  : "
                f"{entity_result['entity_id']}"
            )

            print(
                f"    Score      : "
                f"{entity_result['score']:.2f}"
            )

            print(
                f"    Method     : "
                f"{entity_result['method']}"
            )

    # ========================================================
    # VERY IMPORTANT
    # ========================================================
    #
    # Artikel ditandai processed WALAU:
    #
    # mentions_found == 0
    #
    # Ini yang mencegah infinite loop.
    #
    # ========================================================

    mark_article_processed(
        conn,
        article_id
    )

    return mentions_found


# ============================================================
# PROCESS BATCH
# ============================================================

def process_batch(
    conn,
    rows,
    alias_index
):

    batch_articles = 0

    batch_mentions = 0

    for row in rows:

        article_id = row[0]

        try:

            mentions_found = process_article(
                conn,
                row,
                alias_index
            )

            batch_articles += 1

            batch_mentions += mentions_found

        except Exception as error:

            print(
                "\n⚠️ ERROR"
            )

            print(
                f"    Article ID : {article_id}"
            )

            print(
                f"    Error      : {error}"
            )

            # =================================================
            # IMPORTANT
            # =================================================
            #
            # Jangan tandai article sebagai processed jika
            # proses artikel mengalami exception.
            #
            # Artikel tersebut akan dicoba kembali pada
            # proses berikutnya.
            #
            # =================================================

            continue

    # ========================================================
    # COMMIT SATU BATCH
    # ========================================================

    conn.commit()

    return (
        batch_articles,
        batch_mentions
    )


# ============================================================
# DATABASE SUMMARY
# ============================================================

def database_summary(
    conn
):

    cursor = conn.cursor()

    # ========================================================
    # V03 TOTAL
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM v03_information_extraction
        """
    )

    total_v03 = cursor.fetchone()[0]

    # ========================================================
    # PROCESSED ARTICLES
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM v04_processed_articles
        """
    )

    total_processed = cursor.fetchone()[0]

    # ========================================================
    # ENTITIES
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM v04_entities
        """
    )

    total_entities = cursor.fetchone()[0]

    # ========================================================
    # MENTIONS
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM v04_entity_mentions
        """
    )

    total_mentions = cursor.fetchone()[0]

    # ========================================================
    # REMAINING
    # ========================================================

    remaining = (
        total_v03
        - total_processed
    )

    if remaining < 0:
        remaining = 0

    return (
        total_v03,
        total_processed,
        remaining,
        total_entities,
        total_mentions
    )


# ============================================================
# RUN V04
# ============================================================

def run():

    print(
        "\n=================================================="
    )

    print(
        "   V0.4 ENTITY RESOLUTION"
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
    # RECOVER PREVIOUS DATA
    # ========================================================
    #
    # 500 artikel yang sudah mempunyai mention dari V04 lama
    # akan otomatis dianggap sudah diproses.
    #
    # ========================================================

    recovered = recover_previous_processed_articles(
        conn
    )

    if recovered > 0:

        print(
            f"\n♻️ Recovery:"
            f" {recovered} artikel lama"
            f" ditandai sebagai PROCESSED."
        )

    # ========================================================
    # ALIAS INDEX
    # ========================================================

    alias_index = build_alias_index()

    # ========================================================
    # INITIAL SUMMARY
    # ========================================================

    (
        total_v03,
        total_processed,
        remaining,
        total_entities,
        total_mentions
    ) = database_summary(
        conn
    )

    print(
        "\n=================================================="
    )

    print(
        "   V0.4 DATABASE STATUS"
    )

    print(
        "=================================================="
    )

    print(
        f"V03 candidates      : {total_v03}"
    )

    print(
        f"Already processed   : {total_processed}"
    )

    print(
        f"Remaining           : {remaining}"
    )

    print(
        f"Entities            : {total_entities}"
    )

    print(
        f"Entity mentions     : {total_mentions}"
    )

    print(
        "=================================================="
    )

    # ========================================================
    # MAIN BATCH LOOP
    # ========================================================

    total_articles_processed = 0

    total_mentions_created = 0

    try:

        while True:

            rows = get_next_batch(
                conn
            )

            # =================================================
            # NO MORE DATA
            # =================================================

            if not rows:

                break

            # =================================================
            # PROCESS BATCH
            # =================================================

            (
                batch_articles,
                batch_mentions
            ) = process_batch(
                conn,
                rows,
                alias_index
            )

            # =================================================
            # UPDATE COUNTERS
            # =================================================

            total_articles_processed += (
                batch_articles
            )

            total_mentions_created += (
                batch_mentions
            )

            # =================================================
            # CURRENT STATUS
            # =================================================

            (
                current_v03,
                current_processed,
                current_remaining,
                current_entities,
                current_mentions
            ) = database_summary(
                conn
            )

            print(
                "\n--------------------------------------------------"
            )

            print(
                f"Batch articles  : {batch_articles}"
            )

            print(
                f"Batch mentions  : {batch_mentions}"
            )

            print(
                f"Total articles  : "
                f"{current_processed}"
            )

            print(
                f"Total mentions  : "
                f"{current_mentions}"
            )

            print(
                f"Remaining       : "
                f"{current_remaining}"
            )

            print(
                "--------------------------------------------------"
            )

    except KeyboardInterrupt:

        # ====================================================
        # USER INTERRUPT
        # ====================================================

        conn.commit()

        print(
            "\n\n⚠️ V0.4 dihentikan oleh user."
        )

        print(
            "Data batch yang sudah selesai telah disimpan."
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
        final_entities,
        final_mentions
    ) = database_summary(
        conn
    )

    conn.close()

    print(
        "\n=================================================="
    )

    print(
        "   V0.4 ANALYSIS SUMMARY"
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
        f"Remaining articles  : "
        f"{final_remaining}"
    )

    print(
        f"Total entities      : "
        f"{final_entities}"
    )

    print(
        f"Total mentions      : "
        f"{final_mentions}"
    )

    print(
        f"Articles processed "
        f"this run           : "
        f"{total_articles_processed}"
    )

    print(
        f"New mentions this "
        f"run                 : "
        f"{total_mentions_created}"
    )

    print(
        "=================================================="
    )

    if final_remaining == 0:

        print(
            "   ✅ V0.4 ENTITY RESOLUTION SELESAI"
        )

    else:

        print(
            "   ⏸️ V0.4 BELUM SELESAI"
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