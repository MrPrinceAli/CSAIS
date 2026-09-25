"""V0.4 - Entity Resolution.

CSAIS - Cyber Social Attack Intelligence System.

Fungsi:
    1. Mengambil hasil V0.3
    2. Mengekstrak entity mention
    3. Melakukan entity resolution
    4. Menghubungkan mention dengan canonical entity
    5. Menyimpan entity dan entity mention
    6. Menandai article sebagai sudah diproses

IMPORTANT:
    Artikel yang tidak memiliki entity tetap dianggap sebagai artikel yang
    sudah diproses. Hal ini mencegah infinite loop pada proses batch.
"""

import hashlib
import re

from csais.db import get_connection, get_timestamp
from csais.provenance import pipeline_stamp
from csais.schema import ensure_column, record_run
from csais.text import jaccard_index


# --- Konfigurasi ---
BATCH_SIZE = 500
FUZZY_THRESHOLD = 0.85
MAX_ENTITY_NAME_LENGTH = 300


# --- Alias entity yang sudah dikenal ---
#
# Dictionary ini merupakan baseline: beberapa nama berbeda dapat mengarah ke
# entity yang sama. Alias dicocokkan dengan seluruh mention, bukan sebagian.

ORGANIZATION_ALIASES = {
    "Bank Mandiri": [
        "bank mandiri", "pt bank mandiri", "mandiri", "mandiri bank",
        "bank mandiri persero",
    ],
    "Microsoft": [
        "microsoft", "microsoft corporation", "microsoft corp", "microsoft corp.",
    ],
    "Google": ["google", "google llc", "google inc", "google corporation"],
    "Apple": ["apple", "apple inc", "apple inc.", "apple corporation"],
    "Amazon": ["amazon", "amazon.com", "amazon web services", "aws"],
    "Rostelecom": ["rostelecom", "rostelcom", "pjsc rostelecom"],
    "AT&T": ["at&t", "att", "at and t"],
    "Verizon": ["verizon", "verizon communications", "verizon wireless"],
    "T-Mobile": ["t-mobile", "t mobile", "t-mobile us"],
    "Meta": [
        "meta", "meta platforms", "meta platforms inc", "facebook", "facebook inc",
    ],
    "TikTok": ["tiktok", "tiktok inc"],
    "ByteDance": ["bytedance", "byte dance"],
    "Telegram": ["telegram", "telegram messenger"],
    "WhatsApp": ["whatsapp", "whatsapp messenger"],
    "Cloudflare": ["cloudflare", "cloudflare inc"],
    "Cisco": ["cisco", "cisco systems", "cisco systems inc"],
    "IBM": ["ibm", "international business machines"],
    "Oracle": ["oracle", "oracle corporation"],
    "Intel": ["intel", "intel corporation"],
    "NVIDIA": ["nvidia", "nvidia corporation"],
    "OpenAI": ["openai", "openai inc"],
    "CrowdStrike": ["crowdstrike", "crowdstrike holdings"],
    "Palo Alto Networks": ["palo alto networks", "palo alto"],
    "Fortinet": ["fortinet", "fortinet inc"],
    "Kaspersky": ["kaspersky", "kaspersky lab", "kaspersky laboratory"],
    "ESET": ["eset", "eset spol"],
    "Recorded Future": ["recorded future"],
    "Mandiant": ["mandiant", "mandiant inc"],
    "FireEye": ["fireeye", "fireeye inc"],
    "Cisco Talos": ["cisco talos", "talos"],
}

THREAT_ACTOR_ALIASES = {
    "APT28": [
        "apt28", "fancy bear", "sofacy", "sednit", "strontium", "forest blizzard",
    ],
    "APT29": ["apt29", "cozy bear", "the dukes", "midnight blizzard", "nobelium"],
    "APT41": ["apt41", "winnti", "double dragon"],
    "Lazarus Group": ["lazarus group", "lazarus", "hidden cobra"],
    "Kimsuky": ["kimsuky", "velvet chollima"],
    "Sandworm": ["sandworm", "sandworm team", "seashell blizzard"],
    "Volt Typhoon": ["volt typhoon"],
    "Salt Typhoon": ["salt typhoon"],
    "MuddyWater": ["muddywater", "muddy water"],
    "Charming Kitten": ["charming kitten", "apt35", "mint sandstorm"],
    "LockBit": ["lockbit", "lockbit group", "lockbit 3.0", "lockbit ransomware"],
    "Cl0p": ["cl0p", "clop", "cl0p ransomware", "clop ransomware"],
    "BlackCat": [
        "blackcat", "blackcat ransomware", "alphv", "alphv/blackcat", "alphransomware",
    ],
    "Black Basta": ["black basta", "blackbasta"],
    "RansomHub": ["ransomhub"],
    "Akira": ["akira", "akira ransomware"],
    "Qilin": ["qilin", "qilin ransomware", "agenda ransomware"],
    "Medusa": ["medusa", "medusa ransomware"],
    "Play": ["play ransomware", "playcrypt"],
    "Rhysida": ["rhysida", "rhysida ransomware"],
    "BianLian": ["bianlian"],
    "Hunters International": ["hunters international"],
    "8Base": ["8base"],
    "Conti": ["conti", "conti ransomware"],
    "REvil": ["revil", "sodinokibi"],
    "DarkSide": ["darkside"],
    "INC Ransom": ["inc ransom", "inc ransomware"],
    "FunkSec": ["funksec"],
    "Scattered Spider": ["scattered spider", "octo tempest", "0ktapus", "unc3944"],
    "Anonymous": ["anonymous", "anonymous collective"],
    "Anonymous Sudan": ["anonymous sudan"],
    "KillNet": ["killnet", "kill net"],
    "NoName057(16)": ["noname057(16)", "noname05716", "noname057"],
    "Bjorka": ["bjorka"],
    "Brain Cipher": ["brain cipher"],
}


# --- Alias lokasi ---
LOCATION_ALIASES = {
    "United States": [
        "united states", "united states of america", "usa", "u.s.", "u.s.a.", "america",
    ],
    "United Kingdom": ["united kingdom", "uk", "u.k.", "great britain", "england"],
    "Russia": ["russia", "russian federation"],
    "Ukraine": ["ukraine"],
    "China": ["china", "people's republic of china", "prc"],
    "Indonesia": ["indonesia", "republic of indonesia"],
    "Singapore": ["singapore"],
    "Malaysia": ["malaysia"],
    "Australia": ["australia"],
    "India": ["india"],
    "Japan": ["japan"],
    "South Korea": ["south korea", "republic of korea"],
    "North Korea": ["north korea", "dprk"],
    "Vietnam": ["vietnam", "viet nam"],
    "Thailand": ["thailand"],
    "Philippines": ["philippines"],
    "Brazil": ["brazil"],
    "Canada": ["canada"],
    "Germany": ["germany"],
    "France": ["france"],
    "Italy": ["italy"],
    "Spain": ["spain"],
    "Netherlands": ["netherlands", "the netherlands", "holland"],
    "Israel": ["israel"],
    "Iran": ["iran", "islamic republic of iran"],
    "Turkey": ["turkey", "türkiye"],
    "Taiwan": ["taiwan"],
    "Hong Kong": ["hong kong"],
}


# --- Normalisasi dan similarity ---
def normalize_entity_name(name):
    """Huruf kecil, buang tanda kutip, ganti tanda baca pemisah dengan spasi."""
    if name is None:
        return ""
    name = str(name).lower().strip()
    name = re.sub(r"[\"'`]", "", name)
    name = re.sub(r"[(),;:]+", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def generate_entity_id(entity_type, canonical_name):
    """ID entity: 20 karakter pertama SHA1 dari tipe dan nama ternormalisasi."""
    raw = f"{entity_type}|{normalize_entity_name(canonical_name)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def tokenize(text):
    """Himpunan token dari nama entity yang sudah dinormalisasi."""
    text = normalize_entity_name(text)
    if not text:
        return set()
    return set(token for token in text.split() if token)


def jaccard_similarity(text_a, text_b):
    """Jaccard similarity berbasis token."""
    return jaccard_index(tokenize(text_a), tokenize(text_b))


def character_similarity(text_a, text_b):
    """Similarity berbasis karakter: 1 - (jarak Levenshtein / panjang maks)."""
    a = normalize_entity_name(text_a)
    b = normalize_entity_name(text_b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    distance = levenshtein_distance(a, b)
    max_length = max(len(a), len(b))
    if max_length == 0:
        return 0.0
    return 1.0 - (distance / max_length)


def levenshtein_distance(text_a, text_b):
    """Jarak edit Levenshtein antara dua string."""
    if text_a == text_b:
        return 0
    if len(text_a) == 0:
        return len(text_b)
    if len(text_b) == 0:
        return len(text_a)
    previous_row = list(range(len(text_b) + 1))
    for i, char_a in enumerate(text_a, start=1):
        current_row = [i]
        for j, char_b in enumerate(text_b, start=1):
            insertion = current_row[j - 1] + 1
            deletion = previous_row[j] + 1
            substitution = previous_row[j - 1] + (0 if char_a == char_b else 1)
            current_row.append(min(insertion, deletion, substitution))
        previous_row = current_row
    return previous_row[-1]


def calculate_similarity(mention, canonical_name):
    """Skor fuzzy: rata-rata Jaccard dan character similarity."""
    normalized_mention = normalize_entity_name(mention)
    normalized_canonical = normalize_entity_name(canonical_name)
    if not normalized_mention or not normalized_canonical:
        return 0.0
    if normalized_mention == normalized_canonical:
        return 1.0
    jaccard = jaccard_similarity(normalized_mention, normalized_canonical)
    character = character_similarity(normalized_mention, normalized_canonical)
    return (jaccard * 0.50) + (character * 0.50)


# --- Alias ---
def build_alias_index():
    """Peta alias ternormalisasi -> (tipe entity, nama canonical)."""
    alias_index = {}
    alias_groups = [
        ("ORGANIZATION", ORGANIZATION_ALIASES),
        ("THREAT_ACTOR", THREAT_ACTOR_ALIASES),
        ("LOCATION", LOCATION_ALIASES),
    ]
    for entity_type, alias_map in alias_groups:
        for canonical_name, aliases in alias_map.items():
            for alias in aliases:
                alias_index[normalize_entity_name(alias)] = (entity_type, canonical_name)
    return alias_index


def resolve_known_alias(entity_type, mention, alias_index):
    """Nama canonical dari alias yang dikenal, jika tipenya cocok."""
    normalized = normalize_entity_name(mention)
    result = alias_index.get(normalized)
    if result is None:
        return None
    result_type, canonical_name = result
    if result_type != entity_type:
        return None
    return canonical_name


# --- Database ---
def create_tables(conn):
    """Buat tabel dan index V0.4 jika belum ada."""
    cursor = conn.cursor()
    cursor.execute("""
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
        """)
    cursor.execute("""
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
            UNIQUE (article_id, entity_id, entity_type, original_name)
        )
        """)
    # Jangan memakai v04_entity_mentions sebagai indikator artikel sudah
    # diproses, karena artikel bisa saja tidak memiliki entity. Karena itu
    # dibutuhkan tabel khusus.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS v04_processed_articles (
            article_id INTEGER PRIMARY KEY,
            processed_at TEXT NOT NULL
        )
        """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_v04_mentions_article "
        "ON v04_entity_mentions(article_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_v04_mentions_entity "
        "ON v04_entity_mentions(entity_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_v04_processed_article "
        "ON v04_processed_articles(article_id)"
    )
    conn.commit()
    ensure_column(conn, "v04_entity_mentions", "pipeline_version", "TEXT")


def recover_previous_processed_articles(conn):
    """Migrasi: artikel yang sudah punya mention dari V04 lama dianggap processed."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO v04_processed_articles (article_id, processed_at)
        SELECT DISTINCT article_id, ?
        FROM v04_entity_mentions
        """,
        (get_timestamp(),),
    )
    recovered = cursor.rowcount
    conn.commit()
    return recovered


def get_next_batch(conn):
    """Ambil batch hasil V0.3 yang belum diproses."""
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
        LEFT JOIN v04_processed_articles p ON v03.article_id = p.article_id
        WHERE p.article_id IS NULL OR v03.extracted_at > p.processed_at
        ORDER BY v03.article_id
        LIMIT ?
        """,
        (BATCH_SIZE,),
    )
    return cursor.fetchall()


# Cache entity di memori, per tipe: {"by_name": {normalized: entity}, "items": [...]}
# Menghindari pembacaan seluruh tabel entity untuk setiap mention.
_ENTITY_CACHE = {}


def _cache_entity(entity_type, entity_id, canonical_name, normalized_name):
    bucket = _ENTITY_CACHE.setdefault(entity_type, {"by_name": {}, "items": []})
    if normalized_name in bucket["by_name"]:
        return
    entity = {
        "entity_id": entity_id,
        "canonical_name": canonical_name,
        "normalized_name": normalized_name,
    }
    bucket["by_name"][normalized_name] = entity
    bucket["items"].append(entity)


def load_entity_cache(conn):
    """Muat seluruh entity dari database ke cache memori."""
    _ENTITY_CACHE.clear()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT entity_id, entity_type, canonical_name, normalized_name FROM v04_entities"
    )
    for entity_id, entity_type, canonical_name, normalized_name in cursor.fetchall():
        _cache_entity(entity_type, entity_id, canonical_name, normalized_name)


def find_existing_entity(entity_type, mention):
    """Cari entity yang sudah ada di cache: exact match dulu, lalu fuzzy match."""
    normalized_mention = normalize_entity_name(mention)
    if not normalized_mention:
        return None
    bucket = _ENTITY_CACHE.get(entity_type)
    if not bucket:
        return None

    # Tahap 1 - exact match
    exact = bucket["by_name"].get(normalized_mention)
    if exact:
        return {
            "entity_id": exact["entity_id"],
            "canonical_name": exact["canonical_name"],
            "score": 1.0,
            "method": "EXACT_MATCH",
        }

    # Tahap 2 - fuzzy match. Skor >= FUZZY_THRESHOLD (0.85) mengharuskan
    # character similarity >= 0.70, yang mustahil bila selisih panjang nama
    # lebih dari 30% panjang terpanjang; kandidat seperti itu dilewati.
    best_match = None
    best_score = 0.0
    mention_length = len(normalized_mention)
    for entity in bucket["items"]:
        candidate = entity["normalized_name"]
        longest = max(mention_length, len(candidate))
        if abs(mention_length - len(candidate)) > 0.3 * longest:
            continue
        score = calculate_similarity(normalized_mention, candidate)
        if score > best_score:
            best_score = score
            best_match = {
                "entity_id": entity["entity_id"],
                "canonical_name": entity["canonical_name"],
                "score": score,
                "method": "FUZZY_MATCH",
            }
    if best_match is not None and best_score >= FUZZY_THRESHOLD:
        return best_match
    return None


def create_entity(conn, entity_type, canonical_name, resolution_method):
    """Simpan entity baru (INSERT OR IGNORE), masukkan ke cache, kembalikan id."""
    entity_id = generate_entity_id(entity_type, canonical_name)
    normalized_name = normalize_entity_name(canonical_name)
    now = get_timestamp()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO v04_entities (
            entity_id, entity_type, canonical_name, normalized_name,
            mention_count, resolution_method, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entity_id,
            entity_type,
            canonical_name,
            normalized_name,
            0,
            resolution_method,
            now,
            now,
        ),
    )
    _cache_entity(entity_type, entity_id, canonical_name, normalized_name)
    return entity_id


def save_entity_mention(
    conn,
    article_id,
    entity_type,
    original_name,
    canonical_name,
    entity_id,
    resolution_score,
    resolution_confidence,
    resolution_method,
):
    """Simpan mention; mention_count hanya naik jika INSERT benar-benar terjadi."""
    cursor = conn.cursor()
    now = get_timestamp()
    cursor.execute(
        """
        INSERT OR IGNORE INTO v04_entity_mentions (
            article_id, entity_id, entity_type, original_name, canonical_name,
            resolution_score, resolution_confidence, resolution_method,
            resolved_at, pipeline_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            now,
            pipeline_stamp(),
        ),
    )
    inserted = cursor.rowcount
    # INSERT OR IGNORE mencegah mention yang sama masuk berkali-kali;
    # mention_count hanya bertambah jika mention benar-benar baru.
    if inserted == 1:
        cursor.execute(
            """
            UPDATE v04_entities
            SET mention_count = COALESCE(mention_count, 0) + 1, updated_at = ?
            WHERE entity_id = ?
            """,
            (now, entity_id),
        )
    return inserted


def mark_article_processed(conn, article_id):
    """Tandai artikel sebagai sudah diproses."""
    cursor = conn.cursor()
    # OR REPLACE: artikel yang diekstrak ulang V0.3 (isi penuh baru) diproses lagi
    cursor.execute(
        """
        INSERT OR REPLACE INTO v04_processed_articles (article_id, processed_at)
        VALUES (?, ?)
        """,
        (article_id, get_timestamp()),
    )


# --- Ekstraksi dan resolusi mention ---
def extract_field_mentions(value):
    """Pecah nilai field menjadi daftar mention; nilai 'unknown' diabaikan."""
    if value is None:
        return []
    value = str(value).strip()
    if not value:
        return []
    unknown_values = {"", "unknown", "none", "null", "n/a", "na", "-"}
    if normalize_entity_name(value) in unknown_values:
        return []
    parts = re.split(r"\s*[;,|]\s*", value)
    results = []
    for part in parts:
        part = part.strip()
        if not part or normalize_entity_name(part) in unknown_values:
            continue
        if len(part) > MAX_ENTITY_NAME_LENGTH:
            continue
        results.append(part)
    return results


def resolve_mention(conn, entity_type, mention, alias_index):
    """Petakan satu mention ke entity: alias dikenal, entity ada, atau baru."""
    mention = mention.strip()
    if not mention:
        return None

    # Tahap 1 - alias yang sudah dikenal
    known_canonical = resolve_known_alias(entity_type, mention, alias_index)
    if known_canonical:
        existing = find_existing_entity(entity_type, known_canonical)
        if existing:
            entity_id = existing["entity_id"]
            canonical_name = existing["canonical_name"]
        else:
            entity_id = create_entity(conn, entity_type, known_canonical, "KNOWN_ALIAS")
            canonical_name = known_canonical
        return {
            "entity_id": entity_id,
            "canonical_name": canonical_name,
            "score": 1.0,
            "confidence": 1.0,
            "method": "KNOWN_ALIAS",
        }

    # Tahap 2 - entity yang sudah ada
    existing = find_existing_entity(entity_type, mention)
    if existing:
        score = existing["score"]
        confidence = min(max(score, 0.0), 1.0)
        return {
            "entity_id": existing["entity_id"],
            "canonical_name": existing["canonical_name"],
            "score": score,
            "confidence": confidence,
            "method": existing["method"],
        }

    # Tahap 3 - entity baru
    entity_id = create_entity(conn, entity_type, mention, "NEW_ENTITY")
    return {
        "entity_id": entity_id,
        "canonical_name": mention,
        "score": 1.0,
        "confidence": 1.0,
        "method": "NEW_ENTITY",
    }


def process_article(conn, row, alias_index):
    """Resolusi semua mention satu artikel; selalu ditandai processed."""
    article_id, attack_type, target, target_organization, threat_actor, location = row
    mentions_found = 0

    organization_values = extract_field_mentions(target_organization)
    organization_values.extend(extract_field_mentions(target))
    field_values = [
        ("ORGANIZATION", organization_values),
        ("THREAT_ACTOR", extract_field_mentions(threat_actor)),
        ("LOCATION", extract_field_mentions(location)),
    ]

    for entity_type, values in field_values:
        # Hapus duplikat dengan mempertahankan urutan
        for mention in list(dict.fromkeys(values)):
            entity_result = resolve_mention(conn, entity_type, mention, alias_index)
            if entity_result is None:
                continue
            inserted = save_entity_mention(
                conn,
                article_id,
                entity_type,
                mention,
                entity_result["canonical_name"],
                entity_result["entity_id"],
                entity_result["score"],
                entity_result["confidence"],
                entity_result["method"],
            )
            if inserted:
                mentions_found += 1
                print("\nEntity Mention")
                print(f"    Article ID : {article_id}")
                print(f"    Type       : {entity_type}")
                print(f"    Mention    : {mention}")
                print(f"    Canonical  : {entity_result['canonical_name']}")
                print(f"    Entity ID  : {entity_result['entity_id']}")
                print(f"    Score      : {entity_result['score']:.2f}")
                print(f"    Method     : {entity_result['method']}")

    # Artikel ditandai processed WALAU mentions_found == 0.
    # Ini yang mencegah infinite loop.
    mark_article_processed(conn, article_id)
    return mentions_found


def process_batch(conn, rows, alias_index):
    """Proses satu batch dalam satu transaksi; artikel yang gagal di-rollback."""
    batch_articles = 0
    batch_mentions = 0
    if not conn.in_transaction:
        conn.execute("BEGIN")
    for row in rows:
        article_id = row[0]
        conn.execute("SAVEPOINT article")
        try:
            mentions_found = process_article(conn, row, alias_index)
            conn.execute("RELEASE SAVEPOINT article")
            batch_articles += 1
            batch_mentions += mentions_found
        except Exception as error:
            # Tulisan parsial artikel ini dibatalkan; cache disegarkan karena
            # entity yang baru dibuat ikut dibatalkan.
            conn.execute("ROLLBACK TO SAVEPOINT article")
            conn.execute("RELEASE SAVEPOINT article")
            load_entity_cache(conn)
            print("\n⚠️ ERROR")
            print(f"    Article ID : {article_id}")
            print(f"    Error      : {error}")
            continue
    conn.commit()
    return batch_articles, batch_mentions


def database_summary(conn):
    """Ringkasan: total V03, sudah diproses, sisa, entity, dan mention."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM v03_information_extraction")
    total_v03 = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM v04_processed_articles")
    total_processed = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM v04_entities")
    total_entities = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM v04_entity_mentions")
    total_mentions = cursor.fetchone()[0]
    cursor.execute("""
        SELECT COUNT(*)
        FROM v03_information_extraction v03
        LEFT JOIN v04_processed_articles p ON v03.article_id = p.article_id
        WHERE p.article_id IS NULL OR v03.extracted_at > p.processed_at
        """)
    remaining = cursor.fetchone()[0]
    return total_v03, total_processed, remaining, total_entities, total_mentions


# --- Program utama ---
def run():
    """Jalankan V0.4 secara batch sampai semua hasil V0.3 terproses."""
    print("\n==================================================")
    print("   V0.4 ENTITY RESOLUTION")
    print("==================================================")

    started_at = get_timestamp()
    conn = get_connection()
    create_tables(conn)

    # Artikel yang sudah mempunyai mention dari V04 lama otomatis dianggap
    # sudah diproses.
    recovered = recover_previous_processed_articles(conn)
    if recovered > 0:
        print(f"\n♻️ Recovery: {recovered} artikel lama ditandai sebagai PROCESSED.")

    alias_index = build_alias_index()
    load_entity_cache(conn)

    total_v03, total_processed, remaining, total_entities, total_mentions = (
        database_summary(conn)
    )
    print("\n==================================================")
    print("   V0.4 DATABASE STATUS")
    print("==================================================")
    print(f"V03 candidates      : {total_v03}")
    print(f"Already processed   : {total_processed}")
    print(f"Remaining           : {remaining}")
    print(f"Entities            : {total_entities}")
    print(f"Entity mentions     : {total_mentions}")
    print("==================================================")

    total_articles_processed = 0
    total_mentions_created = 0
    try:
        while True:
            rows = get_next_batch(conn)
            if not rows:
                break
            batch_articles, batch_mentions = process_batch(conn, rows, alias_index)
            total_articles_processed += batch_articles
            total_mentions_created += batch_mentions
            if batch_articles == 0:
                print("\n⚠️ Seluruh artikel dalam batch gagal diproses; berhenti.")
                break

            (
                current_v03,
                current_processed,
                current_remaining,
                current_entities,
                current_mentions,
            ) = database_summary(conn)
            print("\n--------------------------------------------------")
            print(f"Batch articles  : {batch_articles}")
            print(f"Batch mentions  : {batch_mentions}")
            print(f"Total articles  : {current_processed}")
            print(f"Total mentions  : {current_mentions}")
            print(f"Remaining       : {current_remaining}")
            print("--------------------------------------------------")
    except KeyboardInterrupt:
        conn.commit()
        print("\n\n⚠️ V0.4 dihentikan oleh user.")
        print("Data batch yang sudah selesai telah disimpan.")
    finally:
        conn.close()

    conn = get_connection()
    final_v03, final_processed, final_remaining, final_entities, final_mentions = (
        database_summary(conn)
    )
    record_run(conn, "v04_entity_resolution", started_at, total_articles_processed)
    conn.close()

    print("\n==================================================")
    print("   V0.4 ANALYSIS SUMMARY")
    print("==================================================")
    print(f"V03 candidates      : {final_v03}")
    print(f"Processed articles  : {final_processed}")
    print(f"Remaining articles  : {final_remaining}")
    print(f"Total entities      : {final_entities}")
    print(f"Total mentions      : {final_mentions}")
    print(f"Articles processed this run           : {total_articles_processed}")
    print(f"New mentions this run                 : {total_mentions_created}")
    print("==================================================")
    if final_remaining == 0:
        print("   ✅ V0.4 ENTITY RESOLUTION SELESAI")
    else:
        print("   ⏸️ V0.4 BELUM SELESAI")
        print("   Jalankan kembali untuk melanjutkan.")
    print("==================================================")


if __name__ == "__main__":
    run()
