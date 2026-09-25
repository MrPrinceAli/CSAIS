"""CSAIS V0.3 - Information Extraction.

Ekstraksi informasi berbasis aturan (kata kunci dan regex) dari artikel yang
dinilai RELEVANT atau UNCERTAIN oleh V0.2: jenis serangan, metode serangan,
sektor dan organisasi target, kelompok target, lokasi, tanggal serangan,
pelaku ancaman, dampak, serta indikator (CVE dan hash). Hasil disimpan ke
tabel ``v03_information_extraction`` beserta skor kepercayaan ekstraksi.
"""

import os
import re
from datetime import datetime

from csais.config import DATABASE_FILE
from csais.db import get_connection, get_timestamp
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


# --- Kata kunci jenis serangan ---
ATTACK_TYPE_KEYWORDS = {
    # MALWARE
    "RANSOMWARE": ["ransomware", "ransom attack", "ransomware attack"],
    "MALWARE": [
        "malware", "trojan", "trojanized", "trojanised", "worm", "spyware", "rootkit",
        "backdoor", "botnet", "infostealer", "information stealer", "keylogger",
    ],
    # CREDENTIAL / IDENTITY
    "ACCOUNT_TAKEOVER": ["account takeover", "account hijacking", "stolen account"],
    "CREDENTIAL_ATTACK": [
        "credential stuffing", "password spraying", "brute force attack",
        "password attack", "credential stealing", "credential theft",
    ],
    # SOCIAL ENGINEERING
    "PHISHING": [
        "phishing", "spear phishing", "spearphishing", "smishing", "vishing",
        "quishing",
    ],
    "SOCIAL_ENGINEERING": [
        "social engineering", "impersonation", "business email compromise",
        "bec attack", "ceo fraud", "executive impersonation",
    ],
    "ONLINE_SCAM": ["online scam", "online fraud", "cyber fraud", "digital fraud"],
    "JOB_SCAM": ["job scam", "employment scam", "recruitment scam"],
    "INVESTMENT_SCAM": ["investment scam", "investment fraud"],
    # WEB / APPLICATION
    "WEB_ATTACK": ["web attack", "website attack", "web application attack"],
    "SQL_INJECTION": ["sql injection", "sqli"],
    "XSS": ["cross site scripting", "xss attack"],
    "REMOTE_CODE_EXECUTION": ["remote code execution", "rce"],
    "PATH_TRAVERSAL": ["path traversal", "directory traversal"],
    "FILE_INCLUSION": ["file inclusion"],
    # VULNERABILITY / EXPLOIT
    "ZERO_DAY": [
        "zero-day", "zero day", "zero-day vulnerability", "zero day vulnerability",
    ],
    "VULNERABILITY_EXPLOITATION": [
        "zero-day exploit", "zero day exploit", "actively exploited",
        "vulnerability exploited", "exploited in the wild", "vulnerability exploitation",
        "exploit chain",
    ],
    # NETWORK
    "DDoS": [
        "ddos", "distributed denial of service", "denial of service", "dos attack",
    ],
    "DNS_ATTACK": ["dns hijacking", "dns poisoning", "dns spoofing", "dns attack"],
    "NETWORK_INTRUSION": ["network intrusion", "network compromise"],
    # DATA
    "DATA_BREACH": [
        "data breach", "database breach", "personal data breach",
        "customer data breach",
    ],
    "DATA_LEAK": ["data leak", "database leak", "stolen data", "data leaked"],
    "DATA_THEFT": ["data theft", "information theft", "data stolen"],
    "DATA_EXFILTRATION": ["data exfiltration", "exfiltrated"],
    # SUPPLY CHAIN
    "SUPPLY_CHAIN_ATTACK": [
        "supply chain attack", "supply chain compromise",
        "software supply chain attack", "third party compromise",
        "third-party compromise",
    ],
    # CLOUD
    "CLOUD_ATTACK": [
        "cloud attack", "cloud breach", "cloud compromise", "cloud exploitation",
    ],
    # INSIDER
    "INSIDER_THREAT": ["insider threat", "insider attack", "malicious insider"],
    # CRITICAL INFRASTRUCTURE / OT
    "CRITICAL_INFRASTRUCTURE_ATTACK": [
        "critical infrastructure attack", "critical infrastructure cyber attack",
        "power grid cyber attack", "water system cyber attack",
        "energy sector cyber attack",
    ],
    "ICS_SCADA_ATTACK": [
        "ics attack", "scada attack", "ot attack", "industrial control system attack",
    ],
    # MOBILE / IOT
    "MOBILE_ATTACK": [
        "mobile attack", "android attack", "ios malware", "mobile malware",
        "mobile ransomware",
    ],
    "IOT_ATTACK": ["iot attack", "iot malware", "iot botnet", "iot security breach"],
    # WEBSITE / DOMAIN
    "WEBSITE_DEFACEMENT": ["website defacement", "web defacement"],
    "DOMAIN_HIJACKING": ["domain hijacking", "domain takeover"],
    "MALICIOUS_WEBSITE": [
        "malicious website", "fake website", "malicious domain", "fake login page",
    ],
    "MALICIOUS_LINK": ["malicious link", "malicious url"],
    # CYBER ESPIONAGE
    "CYBER_ESPIONAGE": ["cyber espionage", "cyber spying", "cyber espionage campaign"],
    "APT": ["apt attack", "advanced persistent threat", "apt campaign"],
    # INFORMATION OPERATIONS
    "INFORMATION_OPERATION": [
        "information operation", "influence operation", "online influence operation",
        "disinformation campaign",
    ],
    "DEEPFAKE_FRAUD": ["deepfake fraud", "deepfake scam", "ai impersonation"],
    # CRYPTO / BLOCKCHAIN
    "CRYPTO_ATTACK": [
        "crypto attack", "cryptocurrency attack", "crypto theft", "crypto wallet hack",
        "crypto exchange hack", "blockchain attack", "smart contract attack",
    ],
    # EXTORTION
    "CYBER_EXTORTION": [
        "cyber extortion", "digital extortion", "double extortion", "triple extortion",
    ],
}


# --- Kata kunci metode serangan ---
ATTACK_METHOD_KEYWORDS = {
    "PHISHING": ["phishing", "spear phishing", "smishing", "vishing", "quishing"],
    "SOCIAL_ENGINEERING": [
        "social engineering", "impersonation", "business email compromise",
        "bec attack",
    ],
    "MALWARE": ["malware", "trojan", "spyware", "backdoor", "botnet", "infostealer"],
    "EXPLOITATION": ["exploit", "exploited", "exploitation", "zero-day", "zero day"],
    "BRUTE_FORCE": ["brute force", "password spraying", "credential stuffing"],
    "VULNERABILITY_EXPLOITATION": [
        "vulnerability exploited", "actively exploited", "security vulnerability",
    ],
    "MALICIOUS_LINK": ["malicious link", "malicious url"],
    "MALICIOUS_WEBSITE": ["malicious website", "fake website", "fake login page"],
}


# --- Kata kunci sektor target ---
TARGET_SECTOR_KEYWORDS = {
    "HEALTHCARE": [
        "hospital", "healthcare", "health care", "clinic", "medical", "health system",
    ],
    "FINANCE": [
        "bank", "banking", "financial institution", "financial services", "fintech",
        "insurance",
    ],
    "GOVERNMENT": [
        "government", "ministry", "municipality", "government agency", "public sector",
    ],
    "EDUCATION": [
        "university", "college", "school", "education institution",
        "educational institution",
    ],
    "TELECOMMUNICATION": [
        "telecom", "telecommunication", "mobile operator", "internet service provider",
        "isp",
    ],
    "ENERGY": ["energy", "electricity", "power grid", "oil and gas", "utility"],
    "MANUFACTURING": ["manufacturing", "factory", "industrial", "manufacturer"],
    "RETAIL": ["retail", "e-commerce", "ecommerce", "online store"],
    "TRANSPORTATION": [
        "airline", "airport", "railway", "rail", "transportation", "shipping", "port",
    ],
    "CRITICAL_INFRASTRUCTURE": [
        "critical infrastructure", "water system", "power grid",
        "industrial control system", "ics", "scada",
    ],
    "TECHNOLOGY": [
        "technology company", "software company", "tech company", "cloud provider",
        "software provider",
    ],
}


# --- Kata kunci kelompok target ---
TARGET_GROUP_KEYWORDS = {
    "INDIVIDUALS": ["individuals", "users", "customers", "citizens", "consumers"],
    "EMPLOYEES": ["employees", "staff", "workers"],
    "STUDENTS": ["students", "student"],
    "CHILDREN": ["children", "kids", "minors"],
    "JOB_SEEKERS": ["job seekers", "jobseekers", "job applicants"],
    "BUSINESSES": ["businesses", "companies", "enterprises"],
    "GOVERNMENT": ["government agencies", "government institutions", "public agencies"],
}


# --- Kata kunci dampak ---
IMPACT_KEYWORDS = {
    "DATA_THEFT": [
        "data stolen", "data theft", "information stolen", "stolen data",
        "customer data stolen",
    ],
    "DATA_LEAK": ["data leak", "data leaked", "information leaked", "database leak"],
    "SERVICE_DISRUPTION": [
        "service disruption", "services disrupted", "operations disrupted",
        "system disruption", "service outage", "systems down",
    ],
    "FINANCIAL_LOSS": [
        "financial loss", "financial losses", "lost money", "money stolen",
        "financial damage",
    ],
    "SYSTEM_COMPROMISE": [
        "system compromised", "systems compromised", "server compromised",
        "network compromised",
    ],
    "ACCOUNT_COMPROMISE": [
        "account compromised", "accounts compromised", "account takeover",
    ],
    "OPERATIONAL_IMPACT": [
        "operations halted", "operations disrupted", "business disruption",
        "business operations affected",
    ],
}


# --- Kata kunci negara / lokasi ---
COUNTRY_NAMES = {
    "Indonesia": ["indonesia", "indonesian"],
    "Singapore": ["singapore", "singaporean"],
    "Malaysia": ["malaysia", "malaysian"],
    "Thailand": ["thailand", "thai"],
    "Vietnam": ["vietnam", "vietnamese"],
    "Philippines": ["philippines", "filipino"],
    "India": ["india", "indian"],
    "China": ["china", "chinese"],
    "Japan": ["japan", "japanese"],
    "South Korea": ["south korea", "korean"],
    "Australia": ["australia", "australian"],
    "United States": ["united states", "u.s.", "american"],
    "United Kingdom": ["united kingdom", "britain", "british"],
    "Germany": ["germany", "german"],
    "France": ["france", "french"],
    "Russia": ["russia", "russian"],
    "Ukraine": ["ukraine", "ukrainian"],
    "Canada": ["canada", "canadian"],
    "Brazil": ["brazil", "brazilian"],
}


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
KNOWN_THREAT_ACTORS = [
    "APT28", "Fancy Bear", "APT29", "Cozy Bear", "Midnight Blizzard", "APT41",
    "Lazarus", "Lazarus Group", "Kimsuky", "Sandworm", "Volt Typhoon", "Salt Typhoon",
    "MuddyWater", "Charming Kitten", "Scattered Spider", "LockBit", "Cl0p", "Clop",
    "BlackCat", "ALPHV", "Black Basta", "RansomHub", "Qilin", "Rhysida", "BianLian",
    "Hunters International", "8Base", "Conti", "REvil", "DarkSide", "INC Ransom",
    "FunkSec", "KillNet", "NoName057(16)", "Anonymous Sudan", "Bjorka", "Brain Cipher",
    "Akira ransomware", "Medusa ransomware", "Play ransomware", "Royal ransomware",
    "Hive ransomware", "Cactus ransomware", "Interlock ransomware",
]

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
    "than", "most", "top", "worst", "massive", "huge",
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


def extract_target_organization(headline, summary):
    """Ekstrak nama organisasi target dari judul lalu ringkasan (tanpa nama media).

    Nama negara tidak dihitung sebagai organisasi; itu urusan extract_location.
    """
    for text in (headline or "", summary or ""):
        if not text:
            continue
        for pattern in _ORGANIZATION_PATTERNS:
            for match in pattern.finditer(text):
                name = _clean_name(match.group(1))
                if name and name.lower() not in _COUNTRY_WORDS:
                    return name[:150]
    return "UNKNOWN"


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


def extract_information(article_id, title, summary, content):
    """Ekstrak seluruh field informasi dari satu artikel."""
    title_text = normalize_text(title)
    summary_text = normalize_text(summary)
    content_text = normalize_text(content)
    combined_text = f"{title_text} {summary_text} {content_text}".strip()

    attack_type = extract_attack_type(combined_text)
    attack_method = extract_attack_method(combined_text)
    target_sector = extract_target_sector(combined_text)
    location = extract_location(combined_text)
    # Teks asli (huruf besar dipertahankan) tanpa nama media Google News
    headline, publisher = split_publisher(title)
    raw_summary = remove_publisher(summary, publisher)
    threat_actor = extract_threat_actor(f"{headline}. {raw_summary}")
    target_organization = extract_target_organization(headline, raw_summary)
    target_group = extract_target_group(combined_text)
    attack_date = extract_attack_date(combined_text)
    impact = extract_impact(combined_text)
    indicators = extract_indicators(combined_text)
    extraction_confidence = calculate_extraction_confidence(
        attack_type, attack_method, target_sector, location, impact
    )

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
    cursor.execute("""
        SELECT COUNT(*)
        FROM v02_relevance v
        LEFT JOIN v03_information_extraction x ON v.article_id = x.article_id
        WHERE v.relevance_label IN ('RELEVANT', 'UNCERTAIN')
            AND x.article_id IS NULL
        """)
    total = cursor.fetchone()[0]
    connection.close()
    return total


def get_next_batch():
    """Ambil batch artikel kandidat V0.2 yang belum diekstrak."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
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
            AND x.article_id IS NULL
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
            extracted_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    initialize_v03_database()

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

    print("\n==================================================")
    print("   ✅ V0.3 INFORMATION EXTRACTION SELESAI")
    print("==================================================")


if __name__ == "__main__":
    run()
