"""CSAIS - Cyber Social Attack Intelligence System: modul data crawler.

Mengumpulkan artikel berita keamanan siber dari Google News RSS berdasarkan
daftar kata kunci multibahasa, menyimpannya ke database SQLite, dan mencatat
checkpoint di tabel crawl_state agar crawl yang terputus dapat dilanjutkan.
Ada dua mode: historical crawl (per periode 30 hari sejak START_DATE) dan
incremental crawl (3 hari terakhir, setelah konfirmasi interaktif pengguna).
"""

import hashlib
import html
import os
import random
import re
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import feedparser
import requests

from csais.config import DATABASE_DIR, DATABASE_FILE
from csais.db import get_connection, get_timestamp


# --- Konfigurasi ---
START_DATE = datetime(2025, 1, 1, tzinfo=timezone.utc)

REQUEST_DELAY_MIN = 0.5
REQUEST_DELAY_MAX = 5.0
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2

USER_AGENT = "CSAIS-Research-Crawler/0.1 (Cyber Social Attack Intelligence System)"


# --- Kata kunci keamanan siber (bahasa Inggris) ---
CYBER_KEYWORDS = [
    # GENERAL CYBERSECURITY
    "cyber attack", "cyberattack", "cyber incident", "cybersecurity incident",
    "cyber threat", "cyber threat actor", "cybercrime", "cyber criminal",
    "cyber operation", "cyber campaign", "cyber intrusion", "cyber compromise",
    "cyber breach",
    # MALWARE
    "malware", "ransomware", "trojan", "worm", "spyware", "rootkit", "backdoor",
    "botnet", "infostealer", "information stealer", "remote access trojan", "keylogger",
    "loader malware", "dropper malware", "wiper malware", "cryptojacking",
    # CREDENTIAL / IDENTITY
    "credential theft", "credential stealing", "account takeover", "password attack",
    "password spraying", "credential stuffing", "brute force attack", "identity theft",
    "session hijacking", "token theft", "authentication bypass", "MFA bypass",
    "MFA fatigue", "MFA bombing", "privilege escalation",
    # SOCIAL ENGINEERING
    "phishing", "spear phishing", "spearphishing", "smishing", "vishing", "quishing",
    "social engineering", "impersonation", "business email compromise", "BEC attack",
    "CEO fraud", "executive impersonation", "invoice fraud", "romance scam", "job scam",
    "investment scam", "online scam", "online fraud", "cyber fraud", "digital fraud",
    # WEB / APPLICATION
    "web attack", "website attack", "web application attack", "SQL injection", "SQLi",
    "cross site scripting", "XSS attack", "command injection", "code injection",
    "remote code execution", "RCE", "SSRF", "file inclusion", "path traversal",
    "directory traversal", "API attack", "API abuse",
    # VULNERABILITY / EXPLOIT
    "zero day", "zero-day", "zero day vulnerability", "zero-day vulnerability",
    "zero day exploit", "zero-day exploit", "exploit", "exploitation",
    "vulnerability exploited", "actively exploited", "security vulnerability",
    "critical vulnerability", "remote exploit", "CVE",
    # NETWORK
    "DDoS", "distributed denial of service", "DoS attack", "denial of service",
    "network attack", "network intrusion", "DNS attack", "DNS hijacking",
    "DNS poisoning", "DNS spoofing", "BGP hijacking", "man in the middle",
    "MITM attack", "packet interception", "network compromise",
    # DATA
    "data breach", "data leak", "data theft", "data exfiltration", "information theft",
    "database breach", "database leak", "stolen data", "personal data breach",
    "PII breach", "customer data breach",
    # SUPPLY CHAIN
    "supply chain attack", "supply chain compromise", "software supply chain attack",
    "third party compromise", "third-party compromise", "vendor compromise",
    "vendor attack", "dependency confusion", "malicious package",
    "malicious dependency", "software update attack",
    # CLOUD
    "cloud attack", "cloud breach", "cloud compromise", "cloud account takeover",
    "cloud credential theft", "cloud security incident", "SaaS attack",
    "cloud exploitation", "cloud vulnerability", "cloud ransomware", "container escape",
    "Kubernetes attack",
    # INSIDER
    "insider threat", "insider attack", "malicious insider", "employee data theft",
    "employee cyber attack", "privileged user abuse", "insider data breach",
    # CRITICAL INFRASTRUCTURE / OT
    "ICS attack", "SCADA attack", "OT attack", "industrial control system attack",
    "industrial cybersecurity", "critical infrastructure attack",
    "critical infrastructure cyber attack", "power grid cyber attack",
    "water system cyber attack", "energy sector cyber attack",
    "manufacturing cyber attack", "oil and gas cyber attack",
    "telecommunication cyber attack", "transportation cyber attack",
    # MOBILE
    "mobile malware", "mobile attack", "Android malware", "Android attack",
    "iOS malware", "iPhone malware", "mobile ransomware", "mobile spyware",
    "mobile security breach",
    # IOT
    "IoT attack", "IoT malware", "IoT botnet", "IoT security breach",
    "smart device attack", "connected device attack",
    # WEBSITE / DOMAIN
    "website defacement", "web defacement", "domain hijacking", "domain takeover",
    "website compromise", "website hacking", "server compromise", "server hacking",
    # CYBER ESPIONAGE
    "cyber espionage", "cyber espionage campaign", "cyber spying",
    "state sponsored cyber attack", "state-sponsored cyber attack", "APT attack",
    "advanced persistent threat", "APT campaign", "nation state cyber attack",
    "nation-state cyber attack",
    # INFORMATION OPERATIONS
    "information operation", "influence operation", "online influence operation",
    "disinformation campaign", "malinformation", "information warfare",
    "cyber influence operation", "deepfake fraud", "AI impersonation",
    "synthetic identity fraud",
    # CRYPTO / BLOCKCHAIN
    "crypto attack", "cryptocurrency attack", "crypto theft", "crypto wallet hack",
    "crypto exchange hack", "blockchain attack", "smart contract attack", "crypto scam",
    # EXTORTION
    "cyber extortion", "digital extortion", "ransom attack", "ransomware attack",
    "double extortion", "triple extortion", "data extortion",
    # MALICIOUS WEBSITE / LINK
    "malicious website", "malicious link", "malicious URL", "fake website",
    "fake login page", "malicious domain", "malicious domain attack",
    # DARK WEB / CYBERCRIME
    "dark web cybercrime", "dark web stolen data", "stolen credentials",
    "stolen account", "cybercrime marketplace", "malware marketplace",
    "ransomware group",
    # AI RELATED CYBER ATTACK
    "AI cyber attack", "AI-powered cyber attack", "AI powered cyber attack",
    "artificial intelligence cyber attack", "generative AI cyber attack", "AI phishing",
    "AI scam", "AI fraud", "AI malware", "AI social engineering", "AI vulnerability",
    "AI security attack",
]


# --- Kata kunci multibahasa ---
MULTILINGUAL_KEYWORDS = {
    "en": CYBER_KEYWORDS,
    "id": [
        "serangan siber", "serangan dunia maya", "insiden siber", "kejahatan siber",
        "malware", "ransomware", "phishing", "penipuan online", "rekayasa sosial",
        "kebocoran data", "pencurian data", "peretasan", "serangan DDoS",
        "serangan jaringan", "serangan ransomware", "spionase siber",
        "serangan infrastruktur kritis",
    ],
    "es": [
        "ataque cibernético", "ciberataque", "incidente de ciberseguridad",
        "ciberdelincuencia", "malware", "ransomware", "phishing", "fraude en línea",
        "robo de datos",
    ],
    "fr": [
        "cyberattaque", "attaque informatique", "incident de cybersécurité",
        "cybercriminalité", "malware", "ransomware", "hameçonnage", "fuite de données",
    ],
    "de": [
        "Cyberangriff", "Cyberattacke", "Cybersicherheitsvorfall", "Cyberkriminalität",
        "Malware", "Ransomware", "Phishing", "Datenleck",
    ],
    "pt": [
        "ataque cibernético", "ciberataque", "incidente de segurança cibernética",
        "cibercrime", "malware", "ransomware", "phishing", "fraude online",
        "vazamento de dados",
    ],
    "ru": [
        "кибератака", "кибернападение", "кибербезопасность", "киберпреступность",
        "вредоносное ПО", "программа-вымогатель", "фишинг", "утечка данных",
        "кража данных",
    ],
    "ja": [
        "サイバー攻撃", "サイバーセキュリティ", "サイバー犯罪", "マルウェア", "ランサムウェア", "フィッシング", "情報漏えい",
        "データ侵害",
    ],
    "ko": [
        "사이버 공격", "사이버 보안", "사이버 범죄", "악성 코드", "랜섬웨어", "피싱", "데이터 유출",
    ],
    "zh": [
        "网络攻击", "网络安全", "网络犯罪", "恶意软件", "勒索软件", "网络钓鱼", "数据泄露", "数据窃取",
    ],
    "ar": [
        "هجوم إلكتروني", "هجمات إلكترونية", "الأمن السيبراني", "الجريمة الإلكترونية",
        "برمجيات خبيثة", "برمجيات الفدية", "التصيد الاحتيالي", "تسريب البيانات",
    ],
    "hi": [
        "साइबर हमला", "साइबर सुरक्षा", "साइबर अपराध", "मैलवेयर", "रैनसमवेयर", "फिशिंग",
        "डेटा उल्लंघन",
    ],
    "vi": [
        "tấn công mạng", "an ninh mạng", "tội phạm mạng", "phần mềm độc hại",
        "ransomware", "lừa đảo trực tuyến", "rò rỉ dữ liệu",
    ],
    "th": [
        "การโจมตีทางไซเบอร์", "ความปลอดภัยทางไซเบอร์", "อาชญากรรมไซเบอร์", "มัลแวร์",
        "แรนซัมแวร์", "ฟิชชิง", "ข้อมูลรั่วไหล",
    ],
}


# --- Database ---
def initialize_database():
    """Buat direktori, tabel, dan indeks database bila belum ada."""
    os.makedirs(DATABASE_DIR, exist_ok=True)
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            article_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT,
            source_type TEXT,
            source_url TEXT,
            title TEXT,
            summary TEXT,
            content TEXT,
            article_url TEXT UNIQUE,
            published_date TEXT,
            collected_date TEXT,
            language TEXT,
            language_confidence REAL,
            query_keyword TEXT,
            query_language TEXT,
            content_hash TEXT,
            first_seen TEXT,
            last_seen TEXT
        )
        """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crawl_state (
            state_id INTEGER PRIMARY KEY AUTOINCREMENT,
            crawl_type TEXT,
            language TEXT,
            keyword TEXT,
            period_start TEXT,
            period_end TEXT,
            status TEXT,
            started_at TEXT,
            completed_at TEXT,
            updated_at TEXT,
            UNIQUE (crawl_type, language, keyword, period_start, period_end)
        )
        """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_articles_published_date "
        "ON articles(published_date)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_articles_language ON articles(language)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_articles_content_hash "
        "ON articles(content_hash)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_crawl_state_status ON crawl_state(status)"
    )
    connection.commit()
    connection.close()


def get_incremental_start_date():
    """Tanggal mulai incremental berdasarkan artikel terbaru di database."""
    if not os.path.exists(DATABASE_FILE):
        return START_DATE

    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT MAX(published_date) FROM articles")
        result = cursor.fetchone()
    except Exception:
        result = None
    connection.close()

    if result and result[0]:
        try:
            latest_date = datetime.fromisoformat(result[0])
            if latest_date.tzinfo is None:
                latest_date = latest_date.replace(tzinfo=timezone.utc)
            print(
                "\n[*] Data terakhir di database ditemukan pada: "
                f"{latest_date.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
            return latest_date - timedelta(hours=1)
        except Exception:
            pass

    return START_DATE


# --- Utilitas teks, hash, tanggal, dan bahasa ---
def clean_text(text):
    """Hapus entitas HTML, tag, dan spasi berlebih dari teks."""
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def generate_content_hash(title, summary, article_url):
    """SHA-256 dari gabungan judul, ringkasan, dan URL artikel."""
    raw_content = f"{title}|{summary}|{article_url}"
    return hashlib.sha256(raw_content.encode("utf-8")).hexdigest()


def parse_date(date_value):
    """Ubah tanggal RFC 2822 dari RSS menjadi ISO 8601 UTC; None bila gagal."""
    if not date_value:
        return None
    try:
        parsed = parsedate_to_datetime(date_value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def detect_language(text):
    """Deteksi bahasa sederhana (id/en) berdasarkan kata umum."""
    text_lower = text.lower()
    indonesian_words = [
        "dan", "yang", "dari", "dengan", "untuk", "serangan", "siber", "keamanan",
    ]
    english_words = [
        "the", "and", "of", "with", "cyber", "security", "attack",
    ]

    indonesia_score = sum(
        1 for word in indonesian_words if f" {word} " in f" {text_lower} "
    )
    english_score = sum(1 for word in english_words if f" {word} " in f" {text_lower} ")

    if indonesia_score > english_score:
        return "id", 0.60
    if english_score > indonesia_score:
        return "en", 0.60
    return "unknown", 0.30


# --- Google News RSS ---
def build_google_news_url(keyword, start_date, end_date, language):
    """Susun URL pencarian Google News RSS untuk satu kata kunci dan periode."""
    # Pastikan end_date minimal H+1 jika tanggalnya sama agar Google tidak error 503
    if start_date.strftime("%Y-%m-%d") >= end_date.strftime("%Y-%m-%d"):
        end_date = end_date + timedelta(days=1)

    query = (
        f'"{keyword}" '
        f'after:{start_date.strftime("%Y-%m-%d")} '
        f'before:{end_date.strftime("%Y-%m-%d")}'
    )
    encoded_query = quote_plus(query)

    language_settings = {
        "en": ("en-US", "US", "US:en"),
        "id": ("id-ID", "ID", "ID:id"),
        "es": ("es-ES", "ES", "ES:es"),
        "fr": ("fr-FR", "FR", "FR:fr"),
        "de": ("de-DE", "DE", "DE:de"),
        "pt": ("pt-BR", "BR", "BR:pt"),
        "ru": ("ru-RU", "RU", "RU:ru"),
        "ja": ("ja-JP", "JP", "JP:ja"),
        "ko": ("ko-KR", "KR", "KR:ko"),
        "zh": ("zh-CN", "CN", "CN:zh"),
        "ar": ("ar", "AE", "AE:ar"),
        "hi": ("hi-IN", "IN", "IN:hi"),
        "vi": ("vi-VN", "VN", "VN:vi"),
        "th": ("th-TH", "TH", "TH:th"),
    }
    hl, gl, ceid = language_settings.get(language, ("en-US", "US", "US:en"))

    url = (
        "https://news.google.com/rss/search?"
        f"q={encoded_query}&hl={hl}&gl={gl}&ceid={ceid}"
    )
    return url


# --- Checkpoint crawl_state ---
def is_period_completed(crawl_type, language, keyword, period_start, period_end):
    """Cek apakah kombinasi crawl/bahasa/kata kunci/periode sudah COMPLETED."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT status
        FROM crawl_state
        WHERE crawl_type = ?
        AND language = ?
        AND keyword = ?
        AND period_start = ?
        AND period_end = ?
        """,
        (crawl_type, language, keyword, period_start, period_end),
    )
    result = cursor.fetchone()
    connection.close()

    if result:
        return result[0] == "COMPLETED"
    return False


def save_crawl_state(crawl_type, language, keyword, period_start, period_end, status):
    """Simpan atau perbarui checkpoint crawl_state untuk satu kombinasi periode."""
    now = get_timestamp()
    completed_at = None
    if status == "COMPLETED":
        completed_at = now

    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO crawl_state (
            crawl_type, language, keyword, period_start, period_end,
            status, started_at, completed_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (crawl_type, language, keyword, period_start, period_end)
        DO UPDATE SET
            status = excluded.status,
            completed_at = excluded.completed_at,
            updated_at = excluded.updated_at
        """,
        (
            crawl_type,
            language,
            keyword,
            period_start,
            period_end,
            status,
            now,
            completed_at,
            now,
        ),
    )
    connection.commit()
    connection.close()


# --- Penyimpanan artikel ---
def save_article(entry, keyword, query_language, current_start=None, current_end=None):
    """Simpan satu entri RSS ke tabel articles; True bila artikel baru."""
    title = clean_text(entry.get("title", ""))
    summary = clean_text(entry.get("summary", ""))
    article_url = entry.get("link", "")
    if not article_url:
        return False

    published_date = parse_date(entry.get("published", ""))
    collected_date = get_timestamp()
    detected_language, language_confidence = detect_language(f"{title} {summary}")
    content_hash = generate_content_hash(title, summary, article_url)

    connection = get_connection()
    cursor = connection.cursor()

    # Cek apakah URL artikel sudah ada
    cursor.execute(
        "SELECT article_id FROM articles WHERE article_url = ?", (article_url,)
    )
    existing = cursor.fetchone()

    # Artikel sudah ada: perbarui last_seen dan kata kunci pencarian
    if existing:
        cursor.execute(
            """
            UPDATE articles
            SET last_seen = ?,
                query_keyword = ?,
                query_language = ?
            WHERE article_id = ?
            """,
            (collected_date, keyword, query_language, existing[0]),
        )
        connection.commit()
        connection.close()
        return False

    # Artikel baru
    source_start = current_start if current_start else START_DATE
    source_end = current_end if current_end else datetime.now(timezone.utc)

    cursor.execute(
        """
        INSERT INTO articles (
            source_name, source_type, source_url,
            title, summary, content,
            article_url,
            published_date, collected_date,
            language, language_confidence,
            query_keyword, query_language,
            content_hash,
            first_seen, last_seen
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Google News",
            "RSS",
            build_google_news_url(keyword, source_start, source_end, query_language),
            title,
            summary,
            summary,
            article_url,
            published_date,
            collected_date,
            detected_language,
            language_confidence,
            keyword,
            query_language,
            content_hash,
            collected_date,
            collected_date,
        ),
    )
    connection.commit()
    connection.close()
    return True


# --- Crawl ---
def request_delay():
    """Jeda acak antar permintaan HTTP."""
    delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
    time.sleep(delay)


def crawl_keyword(keyword, language, start_date, end_date):
    """Ambil RSS Google News untuk satu kata kunci dan simpan semua entrinya."""
    url = build_google_news_url(keyword, start_date, end_date, language)

    print(f"\n   🔎 [{language}] {keyword}")
    print(
        f"      Period : {start_date.strftime('%Y-%m-%d %H:%M')} → "
        f"{end_date.strftime('%Y-%m-%d %H:%M')}"
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            request_delay()
            response = requests.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()

            feed = feedparser.parse(response.content)
            if feed.bozo and not feed.entries:
                raise RuntimeError("RSS parsing failed")

            saved_count = 0
            for entry in feed.entries:
                if save_article(entry, keyword, language, start_date, end_date):
                    saved_count += 1

            print(f"      Entries : {len(feed.entries)}")
            print(f"      New data: {saved_count}")
            return True

        except Exception as error:
            print(f"      ⚠️ Attempt {attempt}/{MAX_RETRIES}")
            print(f"      Error: {error}")
            if attempt < MAX_RETRIES:
                retry_delay = RETRY_BASE_DELAY**attempt
                print(f"      Retry dalam {retry_delay} detik...")
                time.sleep(retry_delay)

    print(f"      ❌ Crawl gagal setelah {MAX_RETRIES} percobaan.")
    return False


def historical_crawl():
    """Crawl semua kata kunci per periode 30 hari sejak START_DATE."""
    print("\n==================================================")
    print("   HISTORICAL CRAWL")
    print("==================================================")

    current_start = START_DATE
    today = datetime.now(timezone.utc)
    period_number = 0

    while current_start < today:
        period_number += 1
        current_end = min(current_start + timedelta(days=30), today)

        print("\n==================================================")
        print(f"PERIOD {period_number}")
        print(f"{current_start.date()} → {current_end.date()}")
        print("==================================================")

        for language, keywords in MULTILINGUAL_KEYWORDS.items():
            for keyword in keywords:
                period_start = current_start.isoformat()
                period_end = current_end.isoformat()

                # Checkpoint: lewati yang sudah selesai
                if is_period_completed(
                    "historical", language, keyword, period_start, period_end
                ):
                    print(f"\n   ⏭️ SKIP [{language}] {keyword}")
                    continue

                save_crawl_state(
                    "historical",
                    language,
                    keyword,
                    period_start,
                    period_end,
                    "IN_PROGRESS",
                )
                success = crawl_keyword(keyword, language, current_start, current_end)

                if success:
                    save_crawl_state(
                        "historical",
                        language,
                        keyword,
                        period_start,
                        period_end,
                        "COMPLETED",
                    )
                else:
                    print("\n❌ Historical crawl dihentikan.")
                    print("Checkpoint tersimpan.")
                    return

        current_start = current_end

    print("\n✅ HISTORICAL CRAWL SELESAI")


def incremental_crawl():
    """Crawl 3 hari terakhir untuk semua kata kunci setelah konfirmasi pengguna."""
    print("\n==================================================")
    print("   INCREMENTAL CRAWL")
    print("==================================================")

    today = datetime.now(timezone.utc)

    # Pertanyaan interaktif kepada pengguna
    choice = (
        input(
            "Apakah Anda ingin update atau melakukan pembaharuan data (crawl)? (y/n): "
        )
        .strip()
        .lower()
    )
    if choice != "y":
        print("\n[*] Crawl dilewati. Langsung meluncur ke modul berikutnya (V02)...")
        return False  # Mengembalikan False agar langsung lanjut ke modul berikutnya

    # Jika dipilih Y, tarik data dari 3 hari ke belakang sampai hari ini
    start_date = today - timedelta(days=3)
    end_date = today
    print(
        f"[*] Rentang incremental aktif: {start_date.strftime('%Y-%m-%d')} → "
        f"{end_date.strftime('%Y-%m-%d')}"
    )

    for language, keywords in MULTILINGUAL_KEYWORDS.items():
        for keyword in keywords:
            period_start = start_date.isoformat()
            period_end = end_date.isoformat()

            if is_period_completed(
                "incremental", language, keyword, period_start, period_end
            ):
                continue

            save_crawl_state(
                "incremental",
                language,
                keyword,
                period_start,
                period_end,
                "IN_PROGRESS",
            )
            success = crawl_keyword(keyword, language, start_date, end_date)

            if success:
                save_crawl_state(
                    "incremental",
                    language,
                    keyword,
                    period_start,
                    period_end,
                    "COMPLETED",
                )
            else:
                print("\n❌ Incremental crawl dihentikan.")
                return True

    print("\n✅ INCREMENTAL CRAWL SELESAI")
    return True


def historical_crawl_completed():
    """Anggap historical crawl selesai bila jumlah task COMPLETED sudah cukup."""
    connection = get_connection()
    cursor = connection.cursor()
    total_keywords = sum(len(keywords) for keywords in MULTILINGUAL_KEYWORDS.values())
    cursor.execute("""
        SELECT COUNT(*)
        FROM crawl_state
        WHERE crawl_type = 'historical'
        AND status = 'COMPLETED'
        """)
    completed = cursor.fetchone()[0]
    connection.close()
    return completed > 0 and completed >= total_keywords * 21


def database_summary():
    """Jumlah artikel dan jumlah task crawl yang sudah COMPLETED."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM articles")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM crawl_state WHERE status = 'COMPLETED'")
    completed_tasks = cursor.fetchone()[0]
    connection.close()
    return total, completed_tasks


# --- Program utama ---
def run():
    """Jalankan crawler: inisialisasi database, historical, lalu incremental."""
    print("\n==================================================")
    print("   CSAIS DATA CRAWLER")
    print("==================================================")

    initialize_database()

    total_articles, completed_tasks = database_summary()
    print(f"\nData dalam database : {total_articles}")
    print(f"Crawl task selesai  : {completed_tasks}")

    if not historical_crawl_completed():
        historical_crawl()
    else:
        print("\n✅ Historical crawl sudah selesai.")

    if historical_crawl_completed():
        incremental_crawl()
    else:
        print("\n⏸️ Incremental crawl belum dijalankan.")

    total_articles, completed_tasks = database_summary()
    print("\n==================================================")
    print("   CRAWLER SUMMARY")
    print("==================================================")
    print(f"Total articles : {total_articles}")
    print(f"Completed tasks: {completed_tasks}")
    print("==================================================")


if __name__ == "__main__":
    run()
