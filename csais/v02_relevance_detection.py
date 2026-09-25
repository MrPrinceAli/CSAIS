"""CSAIS - Cyber Social Attack Intelligence System.

V0.2 - Information Relevance Detection (deteksi relevansi informasi).

Menilai setiap artikel pada tabel ``articles`` yang belum dianalisis, memberi
label RELEVANT / UNCERTAIN / NOT_RELEVANT berdasarkan pencocokan kata kunci
(rule based) pada judul dan ringkasan, lalu menyimpan label, skor, dan tingkat
keyakinannya ke tabel ``v02_relevance``.
"""

import os

from csais.config import DATABASE_FILE
from csais.db import get_connection, get_timestamp
from csais.text import normalize_text


# --- Konfigurasi ---
BATCH_SIZE = 500

RELEVANT_THRESHOLD = 0.60
UNCERTAIN_THRESHOLD = 0.40


# --- Kata kunci relevansi ---
ATTACK_KEYWORDS = [
    # Keamanan siber umum
    "cyber attack", "cyberattack", "cyber incident", "cybersecurity incident",
    "cyber threat", "cyber intrusion", "cyber compromise", "cyber breach",
    # Malware
    "malware", "ransomware", "trojan", "worm", "spyware", "rootkit", "backdoor",
    "botnet", "infostealer", "information stealer", "remote access trojan", "keylogger",
    "loader malware", "dropper malware", "wiper malware", "cryptojacking",
    # Kredensial / identitas
    "credential theft", "credential stealing", "account takeover", "password attack",
    "password spraying", "credential stuffing", "brute force attack", "identity theft",
    "session hijacking", "token theft", "authentication bypass", "mfa bypass",
    "mfa fatigue", "mfa bombing", "privilege escalation",
    # Rekayasa sosial
    "phishing", "spear phishing", "spearphishing", "smishing", "vishing", "quishing",
    "social engineering", "impersonation", "business email compromise", "bec attack",
    "ceo fraud", "executive impersonation", "invoice fraud", "romance scam", "job scam",
    "investment scam", "online scam", "online fraud", "cyber fraud", "digital fraud",
    # Web / aplikasi
    "web attack", "website attack", "web application attack", "sql injection", "sqli",
    "cross site scripting", "xss attack", "command injection", "code injection",
    "remote code execution", "rce", "ssrf", "file inclusion", "path traversal",
    "directory traversal", "api attack", "api abuse",
    # Kerentanan / eksploit
    "zero day", "zero-day", "zero day vulnerability", "zero-day vulnerability",
    "zero day exploit", "zero-day exploit", "exploit", "exploitation",
    "vulnerability exploited", "actively exploited", "security vulnerability",
    "critical vulnerability", "remote exploit", "cve-",
    # Jaringan
    "ddos", "distributed denial of service", "dos attack", "denial of service",
    "network attack", "network intrusion", "dns attack", "dns hijacking",
    "dns poisoning", "dns spoofing", "bgp hijacking", "man in the middle",
    "mitm attack", "packet interception", "network compromise",
    # Data
    "data breach", "data leak", "data theft", "data exfiltration", "information theft",
    "database breach", "database leak", "stolen data", "personal data breach",
    "pii breach", "customer data breach",
    # Rantai pasok
    "supply chain attack", "supply chain compromise", "software supply chain attack",
    "third party compromise", "third-party compromise", "vendor compromise",
    "vendor attack", "dependency confusion", "malicious package",
    "malicious dependency", "software update attack",
    # Cloud
    "cloud attack", "cloud breach", "cloud compromise", "cloud account takeover",
    "cloud credential theft", "cloud security incident", "saas attack",
    "cloud exploitation", "cloud vulnerability", "cloud ransomware", "container escape",
    "kubernetes attack",
    # Orang dalam (insider)
    "insider threat", "insider attack", "malicious insider", "employee data theft",
    "employee cyber attack", "privileged user abuse", "insider data breach",
    # Infrastruktur kritis / OT
    "ics attack", "scada attack", "ot attack", "industrial control system attack",
    "industrial cybersecurity", "critical infrastructure attack",
    "critical infrastructure cyber attack", "power grid cyber attack",
    "water system cyber attack", "energy sector cyber attack",
    "manufacturing cyber attack", "oil and gas cyber attack",
    "telecommunication cyber attack", "transportation cyber attack",
    # Mobile
    "mobile malware", "mobile attack", "android malware", "android attack",
    "ios malware", "iphone malware", "mobile ransomware", "mobile spyware",
    "mobile security breach",
    # IoT
    "iot attack", "iot malware", "iot botnet", "iot security breach",
    "smart device attack", "connected device attack",
    # Website / domain
    "website defacement", "web defacement", "domain hijacking", "domain takeover",
    "website compromise", "website hacking", "server compromise", "server hacking",
    # Spionase siber
    "cyber espionage", "cyber espionage campaign", "cyber spying",
    "state sponsored cyber attack", "state-sponsored cyber attack", "apt attack",
    "advanced persistent threat", "apt campaign", "nation state cyber attack",
    "nation-state cyber attack",
    # Operasi informasi
    "information operation", "influence operation", "online influence operation",
    "disinformation campaign", "malinformation", "information warfare",
    "cyber influence operation", "deepfake fraud", "ai impersonation",
    "synthetic identity fraud",
    # Kripto / blockchain
    "crypto attack", "cryptocurrency attack", "crypto theft", "crypto wallet hack",
    "crypto exchange hack", "blockchain attack", "smart contract attack", "crypto scam",
    # Pemerasan
    "cyber extortion", "digital extortion", "ransom attack", "ransomware attack",
    "double extortion", "triple extortion", "data extortion",
    # Situs / tautan berbahaya
    "malicious website", "malicious link", "malicious url", "fake website",
    "fake login page", "malicious domain", "malicious domain attack",
    # Dark web / kejahatan siber
    "dark web cybercrime", "dark web stolen data", "stolen credentials",
    "stolen account", "cybercrime marketplace", "malware marketplace",
    "ransomware group",
    # Serangan siber terkait AI
    "ai cyber attack", "ai-powered cyber attack", "ai powered cyber attack",
    "artificial intelligence cyber attack", "generative ai cyber attack", "ai phishing",
    "ai scam", "ai fraud", "ai malware", "ai social engineering", "ai vulnerability",
    "ai security attack",
]

# Indikator bahwa serangan benar-benar terjadi (bahasa kejadian/insiden)
EVENT_INDICATORS = [
    "attacked", "attackers", "targeted", "targeting", "breached", "compromised",
    "infected", "exploited", "hacked", "hit by", "hit with", "fell victim", "victim of",
    "stolen", "exfiltrated", "leaked", "disrupted", "shutdown", "intrusion", "incident",
    "campaign", "threat actor", "threat group", "victims", "affected",
    "unauthorized access", "data stolen", "data leaked", "credentials stolen",
]

# Indikator pembahasan umum / bukan insiden (acara, edukasi, panduan)
NON_INCIDENT_INDICATORS = [
    "conference", "webinar", "workshop", "training", "course", "certification",
    "summit", "forum", "event", "panel discussion", "research paper", "academic study",
    "study finds", "report discusses", "guide", "guidance", "best practices",
    "awareness campaign", "awareness program", "prevention", "how to protect",
    "how to prevent", "tips to avoid", "security advice", "security training",
    "cybersecurity strategy",
]


# --- Pencocokan kata kunci dan analisis relevansi ---
def find_matches(text, keywords):
    """Kembalikan kata kunci dari daftar yang muncul di dalam teks."""
    matches = []
    for keyword in keywords:
        keyword_normalized = keyword.lower()
        if keyword_normalized in text:
            matches.append(keyword)
    return matches


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

    # Penalti untuk pembahasan umum
    if non_incident_matches:
        score -= 0.15

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
    if confidence > 1:
        confidence = 1.0

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


def save_analysis(article_id, result):
    """Simpan hasil analisis satu artikel ke tabel v02_relevance."""
    connection = get_connection()
    cursor = connection.cursor()
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
            analyzed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        ),
    )

    connection.commit()
    connection.close()


def process_batch(rows):
    """Analisis dan simpan satu batch artikel; tampilkan 10 contoh pertama."""
    processed = 0
    relevant = 0
    uncertain = 0
    not_relevant = 0

    for row in rows:
        article_id = row[0]
        title = row[1] or ""
        summary = row[2] or ""
        language = row[3] or "unknown"

        result = analyze_relevance(title, summary)
        save_analysis(article_id, result)
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

    print("\n==================================================")
    print("   ✅ V0.2 RELEVANCE DETECTION SELESAI")
    print("==================================================")


if __name__ == "__main__":
    run()
