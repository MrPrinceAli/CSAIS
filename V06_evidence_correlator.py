# ============================================================
# V0.6 - EVIDENCE CORRELATION
# ============================================================
#
# CSAIS - Cyber Social Attack Intelligence System
#
# Fungsi:
#   1. Mengambil incident hasil V0.5
#   2. Mengambil seluruh artikel dalam incident
#   3. Membandingkan hubungan antar sumber
#   4. Mendeteksi kemungkinan duplicate / reproduced evidence
#   5. Mengidentifikasi kemungkinan independent evidence
#   6. Menghasilkan evidence independence score
#
# IMPORTANT:
#
# V0.6 tidak menentukan apakah informasi benar atau salah.
#
# V0.6 menentukan:
#
#   - apakah evidence kemungkinan duplicate
#   - apakah evidence kemungkinan reproduced
#   - apakah evidence kemungkinan independent
#   - seberapa kuat hubungan antar evidence
#
# ============================================================


# ============================================================
# IMPORT LIBRARY
# ============================================================

import sqlite3
import re
import hashlib
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import urlparse


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = "database/csais.db"

BATCH_SIZE = 100

TEXT_SIMILARITY_THRESHOLD = 0.80

HIGH_SIMILARITY_THRESHOLD = 0.90

LOW_SIMILARITY_THRESHOLD = 0.40

TITLE_SIMILARITY_THRESHOLD = 0.85

MAX_TEXT_LENGTH = 10000


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

    text = re.sub(
        r"https?://\S+",
        " ",
        text
    )

    text = re.sub(
        r"www\.\S+",
        " ",
        text
    )

    text = re.sub(
        r"[^\w\s]",
        " ",
        text,
        flags=re.UNICODE
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# TOKENIZE
# ============================================================

def tokenize(text):

    normalized = normalize_text(
        text
    )

    if not normalized:
        return set()

    return set(
        token
        for token in normalized.split()
        if len(token) > 2
    )


# ============================================================
# JACCARD SIMILARITY
# ============================================================

def jaccard_similarity(
    text_a,
    text_b
):

    tokens_a = tokenize(
        text_a
    )

    tokens_b = tokenize(
        text_b
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
# SEQUENCE SIMILARITY
# ============================================================

def sequence_similarity(
    text_a,
    text_b
):

    a = normalize_text(
        text_a
    )

    b = normalize_text(
        text_b
    )

    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    if len(a) > MAX_TEXT_LENGTH:

        a = a[:MAX_TEXT_LENGTH]

    if len(b) > MAX_TEXT_LENGTH:

        b = b[:MAX_TEXT_LENGTH]

    return SequenceMatcher(
        None,
        a,
        b
    ).ratio()


# ============================================================
# COMBINED TEXT SIMILARITY
# ============================================================

def calculate_text_similarity(
    text_a,
    text_b
):

    jaccard = jaccard_similarity(
        text_a,
        text_b
    )

    sequence = sequence_similarity(
        text_a,
        text_b
    )

    return (
        (jaccard * 0.50)
        +
        (sequence * 0.50)
    )


# ============================================================
# TITLE SIMILARITY
# ============================================================

def calculate_title_similarity(
    title_a,
    title_b
):

    return sequence_similarity(
        title_a,
        title_b
    )


# ============================================================
# DOMAIN EXTRACTION
# ============================================================

def extract_domain(
    url
):

    if not url:
        return ""

    try:

        parsed = urlparse(
            url
        )

        domain = (
            parsed.netloc
            or ""
        )

        domain = domain.lower()

        domain = re.sub(
            r"^www\.",
            "",
            domain
        )

        return domain

    except Exception:

        return ""


# ============================================================
# CONTENT FINGERPRINT
# ============================================================

def generate_content_fingerprint(
    title,
    summary,
    content
):

    combined = " ".join(
        [
            title or "",
            summary or "",
            content or ""
        ]
    )

    normalized = normalize_text(
        combined
    )

    if not normalized:
        return ""

    return hashlib.sha256(
        normalized.encode(
            "utf-8"
        )
    ).hexdigest()


# ============================================================
# CREATE DATABASE TABLES
# ============================================================

def create_tables(
    conn
):

    cursor = conn.cursor()

    # ========================================================
    # EVIDENCE TABLE
    # ========================================================

    cursor.execute(
        """
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

            UNIQUE (
                incident_id,
                article_id
            )
        )
        """
    )

    # ========================================================
    # SOURCE RELATION TABLE
    # ========================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS
        v06_source_relations (

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

            UNIQUE (
                incident_id,
                article_id_a,
                article_id_b
            )
        )
        """
    )

    # ========================================================
    # PROCESSED INCIDENT TABLE
    # ========================================================

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS
        v06_processed_incidents (

            incident_id TEXT PRIMARY KEY,

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
        idx_v06_evidence_incident

        ON v06_evidence(
            incident_id
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_v06_evidence_article

        ON v06_evidence(
            article_id
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_v06_relation_incident

        ON v06_source_relations(
            incident_id
        )
        """
    )

    conn.commit()


# ============================================================
# GET INCIDENT BATCH
# ============================================================

def get_next_incident_batch(
    conn
):

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT

            i.incident_id

        FROM v05_incidents i

        LEFT JOIN
        v06_processed_incidents p

            ON i.incident_id =
               p.incident_id

        WHERE p.incident_id IS NULL

        ORDER BY i.incident_id

        LIMIT ?
        """,
        (
            BATCH_SIZE,
        )
    )

    return [
        row[0]
        for row in cursor.fetchall()
    ]


# ============================================================
# GET INCIDENT DOCUMENTS
# ============================================================

def get_incident_documents(
    conn,
    incident_id
):

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT

            d.article_id,

            a.source_name,

            a.source_type,

            a.source_url,

            a.title,

            a.summary,

            a.content,

            a.published_date,

            a.article_url

        FROM v05_incident_documents d

        INNER JOIN articles a

            ON d.article_id =
               a.article_id

        WHERE d.incident_id = ?

        ORDER BY
            a.published_date ASC,
            a.article_id ASC
        """,
        (
            incident_id,
        )
    )

    return cursor.fetchall()


# ============================================================
# PARSE DATETIME
# ============================================================

def parse_datetime(
    value
):

    if not value:
        return None

    value = str(
        value
    ).strip()

    if not value:
        return None

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
    # SIMPLE DATE
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
# TIME DIFFERENCE
# ============================================================

def calculate_time_difference_hours(
    date_a,
    date_b
):

    datetime_a = parse_datetime(
        date_a
    )

    datetime_b = parse_datetime(
        date_b
    )

    if (
        datetime_a is None
        or datetime_b is None
    ):

        return None

    difference = (
        datetime_a
        -
        datetime_b
    )

    return abs(
        difference.total_seconds()
        /
        3600.0
    )


# ============================================================
# RELATION CLASSIFICATION
# ============================================================

def classify_relation(
    text_similarity,
    title_similarity,
    domain_same,
    time_difference_hours
):

    # ========================================================
    # HIGH SIMILARITY
    # ========================================================

    if (
        text_similarity
        >= HIGH_SIMILARITY_THRESHOLD
    ):

        return (
            "LIKELY_DUPLICATE",
            0.95
        )

    # ========================================================
    # REPRODUCED / SYNDICATED
    # ========================================================

    if (
        text_similarity
        >= TEXT_SIMILARITY_THRESHOLD
        and
        title_similarity
        >= TITLE_SIMILARITY_THRESHOLD
    ):

        return (
            "LIKELY_REPRODUCED",
            0.90
        )

    # ========================================================
    # HIGH TITLE + MODERATE TEXT
    # ========================================================

    if (
        title_similarity
        >= TITLE_SIMILARITY_THRESHOLD
        and
        text_similarity
        >= 0.65
    ):

        return (
            "POSSIBLE_REPRODUCED",
            0.80
        )

    # ========================================================
    # SAME DOMAIN + HIGH TEXT
    # ========================================================

    if (
        domain_same
        and
        text_similarity
        >= 0.70
    ):

        return (
            "POSSIBLE_DUPLICATE",
            0.80
        )

    # ========================================================
    # LOW SIMILARITY
    # ========================================================

    if (
        text_similarity
        <= LOW_SIMILARITY_THRESHOLD
    ):

        return (
            "LIKELY_INDEPENDENT",
            0.75
        )

    # ========================================================
    # OTHERWISE
    # ========================================================

    return (
        "UNCERTAIN_RELATION",
        0.50
    )


# ============================================================
# CALCULATE INDEPENDENCE SCORE
# ============================================================

def calculate_independence_score(
    text_similarity,
    title_similarity,
    domain_same
):

    # ========================================================
    # BASE SCORE
    # ========================================================

    score = 1.0

    # ========================================================
    # TEXT SIMILARITY PENALTY
    # ========================================================

    score -= (
        text_similarity
        * 0.60
    )

    # ========================================================
    # TITLE SIMILARITY PENALTY
    # ========================================================

    score -= (
        title_similarity
        * 0.25
    )

    # ========================================================
    # SAME DOMAIN PENALTY
    # ========================================================

    if domain_same:

        score -= 0.10

    # ========================================================
    # NORMALIZE
    # ========================================================

    score = max(
        0.0,
        min(
            1.0,
            score
        )
    )

    return score


# ============================================================
# SAVE SOURCE RELATION
# ============================================================

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
    relation_confidence
):

    # ========================================================
    # ORDER ARTICLE IDS
    # ========================================================

    if article_id_a > article_id_b:

        article_id_a, article_id_b = (
            article_id_b,
            article_id_a
        )

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO
        v06_source_relations (

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
            get_timestamp()
        )
    )


# ============================================================
# SAVE EVIDENCE
# ============================================================

def save_evidence(
    conn,
    incident_id,
    article,
    evidence_type,
    independence_score,
    evidence_confidence,
    fingerprint
):

    (
        article_id,
        source_name,
        source_type,
        source_url,
        title,
        summary,
        content,
        published_date,
        article_url
    ) = article

    source_domain = extract_domain(
        article_url
        or source_url
    )

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO
        v06_evidence (

            incident_id,

            article_id,

            source_name,

            source_type,

            source_domain,

            evidence_type,

            evidence_independence_score,

            evidence_confidence,

            publication_date,

            content_fingerprint,

            analyzed_at

        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            get_timestamp()
        )
    )


# ============================================================
# DETERMINE EVIDENCE TYPES
# ============================================================

def determine_evidence_types(
    relations
):

    evidence_types = {}

    for relation in relations:

        article_a = relation[
            "article_id_a"
        ]

        article_b = relation[
            "article_id_b"
        ]

        relation_type = relation[
            "relation_type"
        ]

        # ====================================================
        # INITIALIZE
        # ====================================================

        if article_a not in evidence_types:

            evidence_types[
                article_a
            ] = []

        if article_b not in evidence_types:

            evidence_types[
                article_b
            ] = []

        # ====================================================
        # DUPLICATE
        # ====================================================

        if relation_type in [
            "LIKELY_DUPLICATE",
            "POSSIBLE_DUPLICATE"
        ]:

            evidence_types[
                article_a
            ].append(
                "DUPLICATE_OR_REPEATED"
            )

            evidence_types[
                article_b
            ].append(
                "DUPLICATE_OR_REPEATED"
            )

        # ====================================================
        # REPRODUCED
        # ====================================================

        elif relation_type in [
            "LIKELY_REPRODUCED",
            "POSSIBLE_REPRODUCED"
        ]:

            evidence_types[
                article_a
            ].append(
                "REPRODUCED_OR_SYNDICATED"
            )

            evidence_types[
                article_b
            ].append(
                "REPRODUCED_OR_SYNDICATED"
            )

        # ====================================================
        # INDEPENDENT
        # ====================================================

        elif relation_type == "LIKELY_INDEPENDENT":

            evidence_types[
                article_a
            ].append(
                "INDEPENDENT_SUPPORT"
            )

            evidence_types[
                article_b
            ].append(
                "INDEPENDENT_SUPPORT"
            )

    return evidence_types


# ============================================================
# PROCESS INCIDENT
# ============================================================

def process_incident(
    conn,
    incident_id
):

    articles = get_incident_documents(
        conn,
        incident_id
    )

    if not articles:

        return {
            "articles": 0,
            "relations": 0,
            "independent": 0,
            "reproduced": 0
        }

    # ========================================================
    # ARTICLE CACHE
    # ========================================================

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
            article_url
        ) = article

        text = " ".join(
            [
                title or "",
                summary or "",
                content or ""
            ]
        )

        fingerprint = (
            generate_content_fingerprint(
                title,
                summary,
                content
            )
        )

        domain = extract_domain(
            article_url
            or source_url
        )

        article_data[
            article_id
        ] = {
            "article": article,
            "text": text,
            "fingerprint": fingerprint,
            "domain": domain
        }

    # ========================================================
    # RELATION STORAGE
    # ========================================================

    relations = []

    # ========================================================
    # PAIRWISE COMPARISON
    # ========================================================

    article_ids = list(
        article_data.keys()
    )

    for i in range(
        len(article_ids)
    ):

        article_id_a = article_ids[i]

        data_a = article_data[
            article_id_a
        ]

        for j in range(
            i + 1,
            len(article_ids)
        ):

            article_id_b = article_ids[j]

            data_b = article_data[
                article_id_b
            ]

            # =================================================
            # TEXT SIMILARITY
            # =================================================

            text_similarity = (
                calculate_text_similarity(
                    data_a["text"],
                    data_b["text"]
                )
            )

            # =================================================
            # TITLE SIMILARITY
            # =================================================

            title_a = data_a[
                "article"
            ][4]

            title_b = data_b[
                "article"
            ][4]

            title_similarity = (
                calculate_title_similarity(
                    title_a,
                    title_b
                )
            )

            # =================================================
            # DOMAIN
            # =================================================

            domain_same = (
                bool(
                    data_a["domain"]
                )
                and
                bool(
                    data_b["domain"]
                )
                and
                data_a["domain"]
                ==
                data_b["domain"]
            )

            # =================================================
            # TIME
            # =================================================

            date_a = data_a[
                "article"
            ][7]

            date_b = data_b[
                "article"
            ][7]

            time_difference_hours = (
                calculate_time_difference_hours(
                    date_a,
                    date_b
                )
            )

            # =================================================
            # CLASSIFY
            # =================================================

            (
                relation_type,
                relation_confidence
            ) = classify_relation(
                text_similarity,
                title_similarity,
                domain_same,
                time_difference_hours
            )

            # =================================================
            # INDEPENDENCE
            # =================================================

            independence_score = (
                calculate_independence_score(
                    text_similarity,
                    title_similarity,
                    domain_same
                )
            )

            # =================================================
            # SAVE
            # =================================================

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
                relation_confidence
            )

            relations.append(
                {
                    "article_id_a":
                        article_id_a,

                    "article_id_b":
                        article_id_b,

                    "relation_type":
                        relation_type,

                    "independence_score":
                        independence_score
                }
            )

    # ========================================================
    # EVIDENCE TYPES
    # ========================================================

    evidence_types = (
        determine_evidence_types(
            relations
        )
    )

    # ========================================================
    # SAVE EVIDENCE PER ARTICLE
    # ========================================================

    independent_count = 0

    reproduced_count = 0

    for article_id in article_ids:

        data = article_data[
            article_id
        ]

        types = evidence_types.get(
            article_id,
            []
        )

        if not types:

            evidence_type = (
                "SINGLE_SOURCE"
            )

            independence_score = 1.0

            evidence_confidence = 0.60

        elif (
            "INDEPENDENT_SUPPORT"
            in types
        ):

            evidence_type = (
                "INDEPENDENT_SUPPORT"
            )

            independence_score = 0.80

            evidence_confidence = 0.75

            independent_count += 1

        elif (
            "REPRODUCED_OR_SYNDICATED"
            in types
        ):

            evidence_type = (
                "REPRODUCED_OR_SYNDICATED"
            )

            independence_score = 0.30

            evidence_confidence = 0.75

            reproduced_count += 1

        elif (
            "DUPLICATE_OR_REPEATED"
            in types
        ):

            evidence_type = (
                "DUPLICATE_OR_REPEATED"
            )

            independence_score = 0.10

            evidence_confidence = 0.85

            reproduced_count += 1

        else:

            evidence_type = (
                "UNCERTAIN"
            )

            independence_score = 0.50

            evidence_confidence = 0.50

        save_evidence(
            conn,
            incident_id,
            data["article"],
            evidence_type,
            independence_score,
            evidence_confidence,
            data["fingerprint"]
        )

    # ========================================================
    # MARK INCIDENT AS PROCESSED
    # ========================================================

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO
        v06_processed_incidents (

            incident_id,
            processed_at

        )

        VALUES (?, ?)
        """,
        (
            incident_id,
            get_timestamp()
        )
    )

    return {
        "articles": len(articles),
        "relations": len(relations),
        "independent": independent_count,
        "reproduced": reproduced_count
    }


# ============================================================
# PROCESS BATCH
# ============================================================

def process_batch(
    conn,
    incident_ids
):

    batch_incidents = 0

    batch_articles = 0

    batch_relations = 0

    batch_independent = 0

    batch_reproduced = 0

    for incident_id in incident_ids:

        try:

            result = process_incident(
                conn,
                incident_id
            )

            batch_incidents += 1

            batch_articles += (
                result["articles"]
            )

            batch_relations += (
                result["relations"]
            )

            batch_independent += (
                result["independent"]
            )

            batch_reproduced += (
                result["reproduced"]
            )

        except Exception as error:

            print(
                "\n⚠️ ERROR"
            )

            print(
                f"    Incident ID : "
                f"{incident_id}"
            )

            print(
                f"    Error       : "
                f"{error}"
            )

            continue

    # ========================================================
    # COMMIT
    # ========================================================

    conn.commit()

    return (
        batch_incidents,
        batch_articles,
        batch_relations,
        batch_independent,
        batch_reproduced
    )


# ============================================================
# DATABASE SUMMARY
# ============================================================

def database_summary(
    conn
):

    cursor = conn.cursor()

    # ========================================================
    # V05 INCIDENTS
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
    # PROCESSED INCIDENTS
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM v06_processed_incidents
        """
    )

    processed_incidents = (
        cursor.fetchone()[0]
    )

    # ========================================================
    # EVIDENCE
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM v06_evidence
        """
    )

    total_evidence = (
        cursor.fetchone()[0]
    )

    # ========================================================
    # RELATIONS
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM v06_source_relations
        """
    )

    total_relations = (
        cursor.fetchone()[0]
    )

    # ========================================================
    # INDEPENDENT
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM v06_evidence

        WHERE evidence_type =
            'INDEPENDENT_SUPPORT'
        """
    )

    independent_evidence = (
        cursor.fetchone()[0]
    )

    # ========================================================
    # REPRODUCED
    # ========================================================

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM v06_evidence

        WHERE evidence_type IN (

            'REPRODUCED_OR_SYNDICATED',

            'DUPLICATE_OR_REPEATED'

        )
        """
    )

    reproduced_evidence = (
        cursor.fetchone()[0]
    )

    remaining = (
        total_incidents
        -
        processed_incidents
    )

    if remaining < 0:

        remaining = 0

    return (
        total_incidents,
        processed_incidents,
        remaining,
        total_evidence,
        total_relations,
        independent_evidence,
        reproduced_evidence
    )


# ============================================================
# RUN V06
# ============================================================

def run():

    print(
        "\n=================================================="
    )

    print(
        "   V0.6 EVIDENCE CORRELATION"
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
    # INITIAL SUMMARY
    # ========================================================

    (
        total_incidents,
        processed_incidents,
        remaining,
        total_evidence,
        total_relations,
        independent_evidence,
        reproduced_evidence
    ) = database_summary(
        conn
    )

    print(
        "\n=================================================="
    )

    print(
        "   V0.6 DATABASE STATUS"
    )

    print(
        "=================================================="
    )

    print(
        f"V05 incidents       : "
        f"{total_incidents}"
    )

    print(
        f"Processed incidents : "
        f"{processed_incidents}"
    )

    print(
        f"Remaining           : "
        f"{remaining}"
    )

    print(
        f"Evidence records    : "
        f"{total_evidence}"
    )

    print(
        f"Source relations    : "
        f"{total_relations}"
    )

    print(
        f"Independent         : "
        f"{independent_evidence}"
    )

    print(
        f"Reproduced          : "
        f"{reproduced_evidence}"
    )

    print(
        "=================================================="
    )

    total_incidents_processed = 0

    total_articles_processed = 0

    total_relations_created = 0

    total_independent_created = 0

    total_reproduced_created = 0

    try:

        while True:

            # =================================================
            # GET INCIDENT BATCH
            # =================================================

            incident_ids = (
                get_next_incident_batch(
                    conn
                )
            )

            if not incident_ids:

                break

            # =================================================
            # PROCESS
            # =================================================

            (
                batch_incidents,
                batch_articles,
                batch_relations,
                batch_independent,
                batch_reproduced
            ) = process_batch(
                conn,
                incident_ids
            )

            # =================================================
            # UPDATE COUNTERS
            # =================================================

            total_incidents_processed += (
                batch_incidents
            )

            total_articles_processed += (
                batch_articles
            )

            total_relations_created += (
                batch_relations
            )

            total_independent_created += (
                batch_independent
            )

            total_reproduced_created += (
                batch_reproduced
            )

            # =================================================
            # CURRENT STATUS
            # =================================================

            (
                current_incidents,
                current_processed,
                current_remaining,
                current_evidence,
                current_relations,
                current_independent,
                current_reproduced
            ) = database_summary(
                conn
            )

            print(
                "\n--------------------------------------------------"
            )

            print(
                f"Batch incidents : "
                f"{batch_incidents}"
            )

            print(
                f"Batch articles  : "
                f"{batch_articles}"
            )

            print(
                f"Batch relations : "
                f"{batch_relations}"
            )

            print(
                f"Total incidents : "
                f"{current_processed}"
            )

            print(
                f"Total evidence  : "
                f"{current_evidence}"
            )

            print(
                f"Total relations : "
                f"{current_relations}"
            )

            print(
                f"Independent     : "
                f"{current_independent}"
            )

            print(
                f"Reproduced      : "
                f"{current_reproduced}"
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
            "\n\n⚠️ V0.6 dihentikan oleh user."
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
        final_incidents,
        final_processed,
        final_remaining,
        final_evidence,
        final_relations,
        final_independent,
        final_reproduced
    ) = database_summary(
        conn
    )

    conn.close()

    print(
        "\n=================================================="
    )

    print(
        "   V0.6 ANALYSIS SUMMARY"
    )

    print(
        "=================================================="
    )

    print(
        f"V05 incidents       : "
        f"{final_incidents}"
    )

    print(
        f"Processed incidents : "
        f"{final_processed}"
    )

    print(
        f"Remaining           : "
        f"{final_remaining}"
    )

    print(
        f"Evidence records    : "
        f"{final_evidence}"
    )

    print(
        f"Source relations    : "
        f"{final_relations}"
    )

    print(
        f"Independent         : "
        f"{final_independent}"
    )

    print(
        f"Reproduced          : "
        f"{final_reproduced}"
    )

    print(
        f"Incidents processed "
        f"this run            : "
        f"{total_incidents_processed}"
    )

    print(
        f"Articles processed "
        f"this run            : "
        f"{total_articles_processed}"
    )

    print(
        f"Relations created "
        f"this run            : "
        f"{total_relations_created}"
    )

    print(
        "=================================================="
    )

    if final_remaining == 0:

        print(
            "   ✅ V0.6 EVIDENCE CORRELATION SELESAI"
        )

    else:

        print(
            "   ⏸️ V0.6 BELUM SELESAI"
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