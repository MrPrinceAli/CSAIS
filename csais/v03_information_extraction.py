"""CSAIS V0.3 - Information Extraction.

Ekstraksi informasi berbasis aturan (kata kunci dan regex) dari artikel yang
dinilai RELEVANT atau UNCERTAIN oleh V0.2: jenis serangan, metode serangan,
sektor dan organisasi target, kelompok target, lokasi, tanggal serangan,
pelaku ancaman, dampak, serta indikator (CVE dan hash). Hasil disimpan ke
tabel ``v03_information_extraction`` beserta skor kepercayaan ekstraksi.
"""

import json
import os
import re
from datetime import datetime

from csais.config import DATABASE_FILE
from csais.db import get_connection, get_timestamp
from csais.provenance import pipeline_stamp
from csais.schema import ensure_column, ensure_content_columns, record_run
from csais.text import (
    contains_keyword,
    drop_overlapping_keywords,
    find_keywords,
    normalize_text,
    remove_publisher,
    split_publisher,
)


# --- Konfigurasi ---
BATCH_SIZE = 500


# --- Kata kunci ekstraksi ---
# Daftar kata kunci disimpan di file JSON pada folder csais/data agar dapat
# diubah tanpa menyentuh kode. Penjelasan setiap kunci ada di csais/data/README.md.
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _load_keywords(name):
    """Baca satu file data kata kunci JSON dari folder csais/data."""
    with open(os.path.join(_DATA_DIR, name), encoding="utf-8") as fh:
        return json.load(fh)


_EXTRACTION = _load_keywords("extraction_keywords.json")

# Kata kunci jenis serangan
ATTACK_TYPE_KEYWORDS = _EXTRACTION["attack_type_keywords"]

# Kata kunci metode serangan
ATTACK_METHOD_KEYWORDS = _EXTRACTION["attack_method_keywords"]

# Kata kunci sektor target
TARGET_SECTOR_KEYWORDS = _EXTRACTION["target_sector_keywords"]

# Kata kunci kelompok target
TARGET_GROUP_KEYWORDS = _EXTRACTION["target_group_keywords"]

# Kata kunci dampak
IMPACT_KEYWORDS = _EXTRACTION["impact_keywords"]

# Kata kunci negara / lokasi
COUNTRY_NAMES = _EXTRACTION["country_names"]


# --- Ekstraksi berbasis kata kunci ---
def find_keyword_matches(text, keyword_dictionary):
    """Kategori yang salah satu kata kuncinya muncul sebagai kata utuh di teks."""
    matches = []
    for category, keywords in keyword_dictionary.items():
        for keyword in keywords:
            if contains_keyword(text, keyword):
                matches.append(category)
                break
    return matches


def extract_attack_type(text):
    """Ekstrak jenis serangan dari teks."""
    matches = find_keyword_matches(text, ATTACK_TYPE_KEYWORDS)
    if not matches:
        return "UNKNOWN"
    return ", ".join(matches)


def extract_attack_method(text):
    """Ekstrak metode serangan dari teks."""
    matches = find_keyword_matches(text, ATTACK_METHOD_KEYWORDS)
    if not matches:
        return "UNKNOWN"
    return ", ".join(matches)


def extract_target_sector(text):
    """Ekstrak sektor target dari teks."""
    matches = find_keyword_matches(text, TARGET_SECTOR_KEYWORDS)
    if not matches:
        return "UNKNOWN"
    return ", ".join(matches)


def extract_target_group(text):
    """Ekstrak kelompok target dari teks."""
    matches = find_keyword_matches(text, TARGET_GROUP_KEYWORDS)
    if not matches:
        return "UNKNOWN"
    return ", ".join(matches)


def extract_impact(text):
    """Ekstrak dampak serangan dari teks."""
    matches = find_keyword_matches(text, IMPACT_KEYWORDS)
    if not matches:
        return "UNKNOWN"
    return ", ".join(matches)


def extract_location(text):
    """Ekstrak nama negara yang disebut di dalam teks."""
    locations = []
    for country, keywords in COUNTRY_NAMES.items():
        for keyword in keywords:
            if contains_keyword(text, keyword):
                locations.append(country)
                break
    if not locations:
        return "UNKNOWN"
    return ", ".join(locations)


# --- Pelaku ancaman yang sudah dikenal ---
# Nama grup yang cukup khas untuk dicari langsung di teks. Nama umum seperti
# "Play", "Royal", atau "Hive" hanya dicari bersama kata "ransomware".
KNOWN_THREAT_ACTORS = _EXTRACTION["known_threat_actors"]

# Kata sandang di awal nama dibuang.
_ARTICLES = {"a", "an", "the"}

# Bila kata PERTAMA hasil tangkapan regex termasuk di sini, tangkapan itu bukan
# nama (kata kerja judul berita, kata penunjuk, kata benda serangan, dll.).
_REJECT_FIRST_WORDS = {
    "this", "that", "these", "those", "it", "its", "their", "our", "his", "her",
    "several", "many", "some", "two", "three", "four", "five", "new", "another",
    "latest", "second", "third", "exclusive", "update", "breaking", "cyber",
    "cyberattack", "cyberattacks", "ransomware", "hackers", "hacker", "attack",
    "attacks", "attackers", "data", "breach", "after", "following", "amid", "why",
    "how", "what", "when", "who", "notorious", "infamous", "prolific", "suspected",
    "alleged", "takes", "take", "claims", "claim", "targets", "target", "exploits",
    "exploit", "exploited", "hits", "hit", "uses", "use", "abuses", "abuse", "deploys",
    "deploy", "leaks", "leak", "strikes", "strike", "steals", "steal", "targeting",
    "exploiting", "using", "behind", "linked", "tied", "says", "said", "warns", "warn",
    "reports", "report", "emerges", "returns", "expands", "shifts", "adds", "adopts",
    "now", "activity", "operations", "operation", "members", "leader", "affiliate",
    "affiliates", "victims", "victim", "list", "lists", "site", "sites", "website",
    "infrastructure", "threat", "tactics", "techniques", "tools", "malware", "group",
    "groups", "gang", "gangs", "name", "names", "police", "officials", "over", "more",
    "than", "most", "top", "worst", "massive", "huge", "emerging",
    # Kata fungsi yang kapital hanya karena berada di awal kalimat isi artikel
    "if", "while", "although", "though", "as", "but", "and", "or", "so", "because",
    "since", "once", "until", "unless", "before", "during", "however", "meanwhile",
    "according", "in", "on", "at", "by", "for", "from", "with", "to", "of", "there",
    "here", "they", "we", "you", "he", "she", "one", "no", "not", "yes", "also",
    "still", "even", "just", "only", "then", "today", "yesterday", "last", "first",
    "earlier", "later", "recently", "additionally", "further", "furthermore",
    "moreover", "instead", "despite", "among", "both", "each", "every", "such",
    "like", "unlike", "per", "via", "read", "learn", "see", "get", "watch", "follow",
    "sign", "subscribe", "share", "related", "sources", "source", "image", "photo",
}

# Kata umum yang tidak boleh menjadi satu-satunya isi sebuah nama. Kata benda
# lembaga boleh mengawali nama ("Bank of PNG", "University of X"), tetapi
# "Hospital" atau "Dutch" sendirian bukan nama.
_GENERIC_NAME_WORDS = _REJECT_FIRST_WORDS | {
    "company", "companies", "government", "hospital", "hospitals", "school",
    "schools", "university", "bank", "banks", "city", "county", "state", "council",
    "systems", "services", "ministry", "department", "agency", "firm", "journalists",
    "us", "u.s.", "uk", "u.k.", "european", "american", "british", "australian",
    "indian", "indonesian", "russian", "chinese", "iranian", "korean", "japanese",
    "german", "french", "dutch", "canadian", "african", "asian", "global", "local",
    "national", "international", "major", "windows", "linux", "android",
}

_NAME_TOKEN = r"[A-Z][\w&.'’-]*"
_NAME_CONNECTOR = r"(?:of|and|&|de|for|the|del|di)"
_ORG_NAME = rf"({_NAME_TOKEN}(?:\s+(?:{_NAME_CONNECTOR}\s+)?{_NAME_TOKEN}){{0,5}})"
_PASSIVE_VERBS = (
    r"(?:(?:was|were|has been|have been|had been|is|are|gets|got)\s+)?"
    r"(?:reportedly\s+|recently\s+|allegedly\s+)?"
    r"(?:hit|attacked|breached|hacked|compromised|targeted|struck|disrupted|"
    r"crippled|paralyzed|paralysed|forced)\b"
)
_SUFFERED_VERBS = (
    r"(?:suffered|suffers|experienced|experiences|confirmed|confirms|disclosed|"
    r"discloses|reported|reports|faced|faces|investigating|investigates|"
    r"responding to|responds to)\s+"
    r"(?:a\s+|an\s+)?(?:[A-Za-z][\w-]*\s+){0,3}?"
    r"(?:cyber|cyber-attack|cyberattack|ransomware|data|security|hack|zero-day|"
    r"zero day|vulnerability|exploitation|breach|attack|incident|intrusion|outage|"
    r"malware|phishing|ddos)\b"
)
_ATTACK_NOUNS = (
    r"(?:cyberattack|cyber attack|cyber-attack|ransomware attack|ransomware|hack|"
    r"data breach|breach|attack|hackers|cybercriminals)"
)
_ACTIVE_VERBS = (
    r"(?:hits|hit|targets|targeted|breaches|breached|attacks|attacked|strikes|"
    r"struck|cripples|crippled|disrupts|disrupted|paralyzes|paralyses|"
    r"compromises|compromised)"
)
_ORGANIZATION_PATTERNS = [
    re.compile(rf"{_ORG_NAME}\s+{_PASSIVE_VERBS}"),
    re.compile(rf"{_ORG_NAME}\s+{_SUFFERED_VERBS}"),
    re.compile(
        rf"{_ATTACK_NOUNS}\s+(?:on\s+|at\s+|against\s+|{_ACTIVE_VERBS}\s+)"
        rf"(?:the\s+)?{_ORG_NAME}"
    ),
]

# Kata pemicu tidak peka huruf besar (?i:...), tetapi nama pelaku harus diawali
# huruf besar agar kata biasa di tengah kalimat tidak ikut tertangkap.
_ACTOR_TERMS = (
    r"(?i:threat actors?|threat groups?|hacking groups?|hacker groups?|"
    r"ransomware groups?|ransomware gangs?|cybercrime groups?|cybercriminal groups?|"
    r"apt groups?|hacktivist groups?|extortion groups?|ransomware operations?)"
)
_ACTOR_NAME = r"([A-Z][\w-]*(?:\s+[A-Z0-9][\w-]*){0,2})"
_ACTOR_PATTERNS = [
    re.compile(
        rf"{_ACTOR_TERMS}\s+(?i:known as\s+|called\s+|named\s+|dubbed\s+|tracked as\s+)?"
        rf"[\"“']?{_ACTOR_NAME}"
    ),
    re.compile(rf"{_ACTOR_NAME}\s+{_ACTOR_TERMS}"),
    # Nama dengan huruf besar di tengah atau angka (LockBit, Cl0p, RansomHub)
    re.compile(r"([A-Z][a-z]*[A-Z0-9][\w-]*)\s+(?i:ransomware)\b"),
]


_ADJECTIVE_COMPOUND = re.compile(
    r"-(?:powered|based|linked|backed|sponsored|affiliated|related|driven)\b", re.I
)


def _clean_name(name):
    """Rapikan nama hasil regex; None bila bukan nama (kata umum saja)."""
    name = re.sub(r"\s+", " ", name).strip(" .,;:'\"“”’-")
    words = name.split()
    while words and words[0].lower() in _ARTICLES:
        words.pop(0)
    if not words or words[0].lower() in _REJECT_FIRST_WORDS:
        return None
    if all(word.lower() in _GENERIC_NAME_WORDS for word in words):
        return None
    if _ADJECTIVE_COMPOUND.search(words[0]):  # "AI-powered", "China-based"
        return None
    return " ".join(words)


# --- Ekstraksi berbasis regex ---
def extract_threat_actor(raw_text):
    """Ekstrak nama pelaku ancaman dari teks asli (huruf besar dipertahankan)."""
    actors = []
    known = drop_overlapping_keywords(find_keywords(raw_text, KNOWN_THREAT_ACTORS))
    for name in known:
        actors.append(re.sub(r"\s+ransomware$", "", name))

    for pattern in _ACTOR_PATTERNS:
        for match in pattern.finditer(raw_text):
            name = _clean_name(match.group(1))
            if name and name.lower() not in {a.lower() for a in actors}:
                actors.append(name[:100])
            if len(actors) >= 3:
                break

    if not actors:
        return "UNKNOWN"
    return ", ".join(actors[:3])


_COUNTRY_WORDS = {name.lower() for name in COUNTRY_NAMES} | {
    keyword.lower() for keywords in COUNTRY_NAMES.values() for keyword in keywords
}


def _first_organization(text):
    """Nama organisasi pertama yang cocok pola serangan di satu teks; None bila tidak ada."""
    for pattern in _ORGANIZATION_PATTERNS:
        for match in pattern.finditer(text):
            name = _clean_name(match.group(1))
            if name and name.lower() not in _COUNTRY_WORDS:
                return name[:150]
    return None


def extract_target_organization(headline, summary, content=""):
    """Ekstrak nama organisasi target dari judul, lalu ringkasan, lalu isi artikel.

    Nama negara tidak dihitung sebagai organisasi; itu urusan extract_location.
    """
    return extract_target_organization_tiered(headline, summary, content)[0]


# Keyakinan berdasarkan tempat nama ditemukan: judul paling dapat dipercaya,
# isi artikel paling rendah karena bisa menyebut organisasi lain yang dikutip.
TIER_CONFIDENCE = {"headline": 0.9, "summary": 0.8, "content": 0.6}
CONTENT_SCAN_CHARS = 3000  # bagian awal isi artikel yang dipindai regex


def extract_target_organization_tiered(headline, summary, content=""):
    """(nama organisasi, keyakinan) dari judul, ringkasan, lalu isi artikel."""
    tiers = (
        ("headline", headline or ""),
        ("summary", summary or ""),
        ("content", (content or "")[:CONTENT_SCAN_CHARS]),
    )
    for tier, text in tiers:
        if text:
            name = _first_organization(text)
            if name:
                return name, TIER_CONFIDENCE[tier]
    return "UNKNOWN", 0.0


def extract_threat_actor_tiered(headline, summary, content=""):
    """(pelaku, keyakinan): dicari di judul dulu, lalu ringkasan, lalu isi artikel."""
    tiers = (
        ("headline", headline or ""),
        ("summary", f"{headline or ''}. {summary or ''}"),
        ("content", f"{headline or ''}. {summary or ''} {(content or '')[:CONTENT_SCAN_CHARS]}"),
    )
    for tier, text in tiers:
        actor = extract_threat_actor(text)
        if actor != "UNKNOWN":
            return actor, TIER_CONFIDENCE[tier]
    return "UNKNOWN", 0.0


def _valid_date(year, month, day):
    """'YYYY-MM-DD' bila tanggal valid, selain itu None."""
    try:
        return datetime(int(year), int(month), int(day)).strftime("%Y-%m-%d")
    except ValueError:
        return None


def extract_attack_date(text):
    """Ekstrak tanggal serangan yang valid, dinormalisasi ke YYYY-MM-DD."""
    for match in re.finditer(r"\b(20\d{2})-(\d{2})-(\d{2})\b", text):
        date = _valid_date(match.group(1), match.group(2), match.group(3))
        if date:
            return date
    for match in re.finditer(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", text):
        first, second, year = match.group(1), match.group(2), match.group(3)
        # Diasumsikan d/m/Y (lazim di Indonesia); m/d/Y bila d/m/Y tidak valid.
        date = _valid_date(year, second, first) or _valid_date(year, first, second)
        if date:
            return date
    return "UNKNOWN"


def extract_indicators(text):
    """Ekstrak indikator (CVE dan hash MD5/SHA1/SHA256) tanpa duplikat."""
    indicators = []
    for match in re.findall(r"\bCVE-\d{4}-\d{4,7}\b", text, re.IGNORECASE):
        indicators.append(match.upper())
    for pattern in (r"\b[A-Fa-f0-9]{32}\b", r"\b[A-Fa-f0-9]{40}\b", r"\b[A-Fa-f0-9]{64}\b"):
        indicators.extend(match.lower() for match in re.findall(pattern, text))
    indicators = list(dict.fromkeys(indicators))
    if not indicators:
        return "UNKNOWN"
    return ", ".join(indicators)


def calculate_extraction_confidence(
    attack_type, attack_method, target_sector, location, impact
):
    """Hitung proporsi field utama yang berhasil diekstrak (bukan UNKNOWN)."""
    fields = [attack_type, attack_method, target_sector, location, impact]
    known_fields = 0
    for field in fields:
        if field != "UNKNOWN":
            known_fields += 1
    confidence = known_fields / len(fields)
    return round(confidence, 4)


def _keyword_confidence(value, title_value):
    """Keyakinan field kata kunci: 0.9 bila juga cocok di judul, 0.7 bila hanya di teks lain."""
    if value == "UNKNOWN":
        return 0.0
    return 0.9 if title_value != "UNKNOWN" else 0.7


def extract_information(article_id, title, summary, content):
    """Ekstrak seluruh field informasi dari satu artikel beserta keyakinan per field.

    Isi artikel penuh (bila sudah diambil content_fetcher) ikut dipindai;
    tanpa isi, ekstraksi bekerja pada judul dan ringkasan saja.
    """
    title_text = normalize_text(title)
    summary_text = normalize_text(summary)
    content_text = normalize_text(content)
    combined_text = f"{title_text} {summary_text} {content_text}".strip()

    attack_type = extract_attack_type(combined_text)
    attack_method = extract_attack_method(combined_text)
    target_sector = extract_target_sector(combined_text)
    target_group = extract_target_group(combined_text)
    location = extract_location(combined_text)
    impact = extract_impact(combined_text)
    attack_date = extract_attack_date(combined_text)
    indicators = extract_indicators(combined_text)

    # Teks asli (huruf besar dipertahankan) tanpa nama media Google News
    headline, publisher = split_publisher(title)
    raw_summary = remove_publisher(summary, publisher)
    threat_actor, actor_confidence = extract_threat_actor_tiered(
        headline, raw_summary, content
    )
    target_organization, target_confidence = extract_target_organization_tiered(
        headline, raw_summary, content
    )

    extraction_confidence = calculate_extraction_confidence(
        attack_type, attack_method, target_sector, location, impact
    )
    field_confidence = {
        "attack_type": _keyword_confidence(attack_type, extract_attack_type(title_text)),
        "attack_method": _keyword_confidence(
            attack_method, extract_attack_method(title_text)
        ),
        "target": target_confidence,
        "target_sector": _keyword_confidence(
            target_sector, extract_target_sector(title_text)
        ),
        "target_group": _keyword_confidence(target_group, extract_target_group(title_text)),
        "location": _keyword_confidence(location, extract_location(title_text)),
        "attack_date": 0.5 if attack_date != "UNKNOWN" else 0.0,
        "threat_actor": actor_confidence,
        "impact": _keyword_confidence(impact, extract_impact(title_text)),
        "indicator": 0.9 if indicators != "UNKNOWN" else 0.0,
    }

    return {
        "article_id": article_id,
        "attack_type": attack_type,
        "attack_method": attack_method,
        "target": target_organization,
        "target_organization": target_organization,
        "target_sector": target_sector,
        "target_group": target_group,
        "location": location,
        "attack_date": attack_date,
        "threat_actor": threat_actor,
        "impact": impact,
        "indicator": indicators,
        "extraction_confidence": extraction_confidence,
        "field_confidence": field_confidence,
        "extraction_method": "RULE_BASED",
    }


# --- Database ---
def initialize_v03_database():
    """Buat tabel dan indeks V0.3 bila belum ada."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS v03_information_extraction (
            article_id INTEGER PRIMARY KEY,
            attack_type TEXT,
            attack_method TEXT,
            target TEXT,
            target_organization TEXT,
            target_sector TEXT,
            target_group TEXT,
            location TEXT,
            attack_date TEXT,
            threat_actor TEXT,
            impact TEXT,
            indicator TEXT,
            extraction_confidence REAL,
            extraction_method TEXT,
            extracted_at TEXT
        )
        """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_v03_attack_type
        ON v03_information_extraction(attack_type)
        """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_v03_location
        ON v03_information_extraction(location)
        """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_v03_target_sector
        ON v03_information_extraction(target_sector)
        """)
    connection.commit()
    ensure_column(connection, "v03_information_extraction", "pipeline_version", "TEXT")
    ensure_column(connection, "v03_information_extraction", "field_confidence", "TEXT")
    connection.close()


def get_total_candidates():
    """Hitung jumlah artikel kandidat V0.2 (RELEVANT atau UNCERTAIN)."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT COUNT(*)
        FROM articles a
        INNER JOIN v02_relevance v
            ON a.article_id = v.article_id
        WHERE v.relevance_label IN ('RELEVANT', 'UNCERTAIN')
        """)
    total = cursor.fetchone()[0]
    connection.close()
    return total


def get_analyzed_articles():
    """Hitung jumlah artikel yang sudah diekstrak oleh V0.3."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM v03_information_extraction")
    total = cursor.fetchone()[0]
    connection.close()
    return total


def get_remaining_candidates():
    """Hitung kandidat V0.2 yang belum diekstrak oleh V0.3."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM v02_relevance v
        JOIN articles a ON a.article_id = v.article_id
        LEFT JOIN v03_information_extraction x ON v.article_id = x.article_id
        WHERE v.relevance_label IN ('RELEVANT', 'UNCERTAIN')
            AND ({_NEEDS_EXTRACTION})
        """)
    total = cursor.fetchone()[0]
    connection.close()
    return total


# Artikel perlu (di)ekstrak bila belum pernah, atau isi penuhnya baru diambil
# setelah ekstraksi terakhir (INSERT OR REPLACE memperbarui barisnya).
_NEEDS_EXTRACTION = (
    "x.article_id IS NULL OR (a.content_status = 'ok' "
    "AND a.content_fetched_at > x.extracted_at)"
)


def get_next_batch():
    """Ambil batch artikel kandidat V0.2 yang belum (atau perlu ulang) diekstrak."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        f"""
        SELECT
            a.article_id,
            a.title,
            a.summary,
            a.content,
            a.language,
            v.relevance_label,
            v.relevance_score
        FROM articles a
        INNER JOIN v02_relevance v
            ON a.article_id = v.article_id
        LEFT JOIN v03_information_extraction x
            ON a.article_id = x.article_id
        WHERE v.relevance_label IN ('RELEVANT', 'UNCERTAIN')
            AND ({_NEEDS_EXTRACTION})
        ORDER BY a.article_id
        LIMIT ?
        """,
        (BATCH_SIZE,),
    )
    rows = cursor.fetchall()
    connection.close()
    return rows


def save_extraction(cursor, result):
    """Simpan hasil ekstraksi satu artikel lewat cursor batch (tanpa commit)."""
    extracted_at = get_timestamp()
    cursor.execute(
        """
        INSERT OR REPLACE INTO v03_information_extraction (
            article_id,
            attack_type,
            attack_method,
            target,
            target_organization,
            target_sector,
            target_group,
            location,
            attack_date,
            threat_actor,
            impact,
            indicator,
            extraction_confidence,
            extraction_method,
            extracted_at,
            pipeline_version,
            field_confidence
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            result["article_id"],
            result["attack_type"],
            result["attack_method"],
            result["target"],
            result["target_organization"],
            result["target_sector"],
            result["target_group"],
            result["location"],
            result["attack_date"],
            result["threat_actor"],
            result["impact"],
            result["indicator"],
            result["extraction_confidence"],
            result["extraction_method"],
            extracted_at,
            pipeline_stamp(),
            json.dumps(result["field_confidence"]),
        ),
    )


def process_batch(rows):
    """Ekstrak dan simpan informasi satu batch artikel dalam satu transaksi."""
    processed = 0
    connection = get_connection()
    cursor = connection.cursor()
    for row in rows:
        article_id = row[0]
        title = row[1] or ""
        summary = row[2] or ""
        content = row[3] or ""
        language = row[4] or "unknown"
        relevance_label = row[5] or "UNKNOWN"
        relevance_score = row[6] or 0.0

        result = extract_information(article_id, title, summary, content)
        save_extraction(cursor, result)
        processed += 1

        # Tampilkan contoh hasil untuk 10 artikel pertama
        if processed <= 10:
            print(f"\n[{processed}] Article ID : {article_id}")
            print(f"    Language       : {language}")
            print(f"    V0.2 Relevance : {relevance_label}")
            print(f"    V0.2 Score     : {relevance_score:.2f}")
            print(f"    Title          : {title[:120]}")
            print(f"    Attack Type    : {result['attack_type']}")
            print(f"    Attack Method  : {result['attack_method']}")
            print(f"    Target         : {result['target']}")
            print(f"    Sector         : {result['target_sector']}")
            print(f"    Location       : {result['location']}")
            print(f"    Impact         : {result['impact']}")
            print(f"    Confidence     : {result['extraction_confidence']:.2f}")

    connection.commit()
    connection.close()
    return processed


def get_v03_summary():
    """Ambil 15 jenis serangan dan 15 sektor target terbanyak."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT attack_type, COUNT(*)
        FROM v03_information_extraction
        GROUP BY attack_type
        ORDER BY COUNT(*) DESC
        LIMIT 15
        """)
    attack_rows = cursor.fetchall()
    cursor.execute("""
        SELECT target_sector, COUNT(*)
        FROM v03_information_extraction
        GROUP BY target_sector
        ORDER BY COUNT(*) DESC
        LIMIT 15
        """)
    sector_rows = cursor.fetchall()
    connection.close()
    return attack_rows, sector_rows


# --- Program utama ---
def run():
    """Jalankan V0.3: ekstraksi informasi untuk semua kandidat V0.2."""
    print("\n==================================================")
    print("   CSAIS V0.3 - INFORMATION EXTRACTION")
    print("==================================================")

    # Cek database
    if not os.path.exists(DATABASE_FILE):
        print("\n❌ Database tidak ditemukan:")
        print(f"   {DATABASE_FILE}")
        return

    started_at = get_timestamp()
    initialize_v03_database()
    connection = get_connection()
    ensure_content_columns(connection)  # kolom content_status dipakai kueri batch
    connection.close()

    # Ringkasan database
    total_candidates = get_total_candidates()
    analyzed_articles = get_analyzed_articles()
    print(f"\nTotal V0.2 candidates : {total_candidates}")
    print(f"Sudah dianalisis     : {analyzed_articles}")
    print(f"Belum dianalisis     : {get_remaining_candidates()}")

    # Proses artikel per batch
    total_processed = 0
    while True:
        rows = get_next_batch()
        if not rows:
            break
        processed = process_batch(rows)
        total_processed += processed
        print(f"\nBatch processed : {processed}")
        print(f"Total processed : {total_processed}")

    # Ringkasan akhir
    attack_rows, sector_rows = get_v03_summary()
    final_total = get_analyzed_articles()

    print("\n==================================================")
    print("   V0.3 ANALYSIS SUMMARY")
    print("==================================================")
    print(f"\nTotal candidates : {total_candidates}")
    print(f"Total extracted  : {final_total}")

    print("\nTOP ATTACK TYPES")
    print("--------------------------------------------------")
    for attack_type, count in attack_rows:
        print(f"{attack_type:<35} {count}")

    print("\nTOP TARGET SECTORS")
    print("--------------------------------------------------")
    for sector, count in sector_rows:
        print(f"{sector:<35} {count}")

    connection = get_connection()
    record_run(connection, "v03_information_extraction", started_at, total_processed)
    connection.close()

    print("\n==================================================")
    print("   ✅ V0.3 INFORMATION EXTRACTION SELESAI")
    print("==================================================")


if __name__ == "__main__":
    run()
