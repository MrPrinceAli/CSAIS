# ============================================================
# CSAIS - CYBER SOCIAL ATTACK INTELLIGENCE SYSTEM
# V0.2 - INFORMATION RELEVANCE DETECTION
# ============================================================

import os
import re
import sqlite3

from datetime import datetime, timezone


# ============================================================
# KONFIGURASI
# ============================================================

DATABASE_FILE = (
    "database/csais.db"
)

BATCH_SIZE = 500

RELEVANT_THRESHOLD = 0.60
UNCERTAIN_THRESHOLD = 0.40


# ============================================================
# RELEVANCE KEYWORDS
# ============================================================

ATTACK_KEYWORDS = [

    # --------------------------------------------------------
    # GENERAL CYBERSECURITY
    # --------------------------------------------------------

    "cyber attack",
    "cyberattack",
    "cyber incident",
    "cybersecurity incident",
    "cyber threat",
    "cyber intrusion",
    "cyber compromise",
    "cyber breach",

    # --------------------------------------------------------
    # MALWARE
    # --------------------------------------------------------

    "malware",
    "ransomware",
    "trojan",
    "worm",
    "spyware",
    "rootkit",
    "backdoor",
    "botnet",
    "infostealer",
    "information stealer",
    "remote access trojan",
    "keylogger",
    "loader malware",
    "dropper malware",
    "wiper malware",
    "cryptojacking",

    # --------------------------------------------------------
    # CREDENTIAL / IDENTITY
    # --------------------------------------------------------

    "credential theft",
    "credential stealing",
    "account takeover",
    "password attack",
    "password spraying",
    "credential stuffing",
    "brute force attack",
    "identity theft",
    "session hijacking",
    "token theft",
    "authentication bypass",
    "mfa bypass",
    "mfa fatigue",
    "mfa bombing",
    "privilege escalation",

    # --------------------------------------------------------
    # SOCIAL ENGINEERING
    # --------------------------------------------------------

    "phishing",
    "spear phishing",
    "spearphishing",
    "smishing",
    "vishing",
    "quishing",
    "social engineering",
    "impersonation",
    "business email compromise",
    "bec attack",
    "ceo fraud",
    "executive impersonation",
    "invoice fraud",
    "romance scam",
    "job scam",
    "investment scam",
    "online scam",
    "online fraud",
    "cyber fraud",
    "digital fraud",

    # --------------------------------------------------------
    # WEB / APPLICATION
    # --------------------------------------------------------

    "web attack",
    "website attack",
    "web application attack",
    "sql injection",
    "sqli",
    "cross site scripting",
    "xss attack",
    "command injection",
    "code injection",
    "remote code execution",
    "rce",
    "ssrf",
    "file inclusion",
    "path traversal",
    "directory traversal",
    "api attack",
    "api abuse",

    # --------------------------------------------------------
    # VULNERABILITY / EXPLOIT
    # --------------------------------------------------------

    "zero day",
    "zero-day",
    "zero day vulnerability",
    "zero-day vulnerability",
    "zero day exploit",
    "zero-day exploit",
    "exploit",
    "exploitation",
    "vulnerability exploited",
    "actively exploited",
    "security vulnerability",
    "critical vulnerability",
    "remote exploit",
    "cve-",

    # --------------------------------------------------------
    # NETWORK
    # --------------------------------------------------------

    "ddos",
    "distributed denial of service",
    "dos attack",
    "denial of service",
    "network attack",
    "network intrusion",
    "dns attack",
    "dns hijacking",
    "dns poisoning",
    "dns spoofing",
    "bgp hijacking",
    "man in the middle",
    "mitm attack",
    "packet interception",
    "network compromise",

    # --------------------------------------------------------
    # DATA
    # --------------------------------------------------------

    "data breach",
    "data leak",
    "data theft",
    "data exfiltration",
    "information theft",
    "database breach",
    "database leak",
    "stolen data",
    "personal data breach",
    "pii breach",
    "customer data breach",

    # --------------------------------------------------------
    # SUPPLY CHAIN
    # --------------------------------------------------------

    "supply chain attack",
    "supply chain compromise",
    "software supply chain attack",
    "third party compromise",
    "third-party compromise",
    "vendor compromise",
    "vendor attack",
    "dependency confusion",
    "malicious package",
    "malicious dependency",
    "software update attack",

    # --------------------------------------------------------
    # CLOUD
    # --------------------------------------------------------

    "cloud attack",
    "cloud breach",
    "cloud compromise",
    "cloud account takeover",
    "cloud credential theft",
    "cloud security incident",
    "saas attack",
    "cloud exploitation",
    "cloud vulnerability",
    "cloud ransomware",
    "container escape",
    "kubernetes attack",

    # --------------------------------------------------------
    # INSIDER
    # --------------------------------------------------------

    "insider threat",
    "insider attack",
    "malicious insider",
    "employee data theft",
    "employee cyber attack",
    "privileged user abuse",
    "insider data breach",

    # --------------------------------------------------------
    # CRITICAL INFRASTRUCTURE / OT
    # --------------------------------------------------------

    "ics attack",
    "scada attack",
    "ot attack",
    "industrial control system attack",
    "industrial cybersecurity",
    "critical infrastructure attack",
    "critical infrastructure cyber attack",
    "power grid cyber attack",
    "water system cyber attack",
    "energy sector cyber attack",
    "manufacturing cyber attack",
    "oil and gas cyber attack",
    "telecommunication cyber attack",
    "transportation cyber attack",

    # --------------------------------------------------------
    # MOBILE
    # --------------------------------------------------------

    "mobile malware",
    "mobile attack",
    "android malware",
    "android attack",
    "ios malware",
    "iphone malware",
    "mobile ransomware",
    "mobile spyware",
    "mobile security breach",

    # --------------------------------------------------------
    # IOT
    # --------------------------------------------------------

    "iot attack",
    "iot malware",
    "iot botnet",
    "iot security breach",
    "smart device attack",
    "connected device attack",

    # --------------------------------------------------------
    # WEBSITE / DOMAIN
    # --------------------------------------------------------

    "website defacement",
    "web defacement",
    "domain hijacking",
    "domain takeover",
    "website compromise",
    "website hacking",
    "server compromise",
    "server hacking",

    # --------------------------------------------------------
    # CYBER ESPIONAGE
    # --------------------------------------------------------

    "cyber espionage",
    "cyber espionage campaign",
    "cyber spying",
    "state sponsored cyber attack",
    "state-sponsored cyber attack",
    "apt attack",
    "advanced persistent threat",
    "apt campaign",
    "nation state cyber attack",
    "nation-state cyber attack",

    # --------------------------------------------------------
    # INFORMATION OPERATIONS
    # --------------------------------------------------------

    "information operation",
    "influence operation",
    "online influence operation",
    "disinformation campaign",
    "malinformation",
    "information warfare",
    "cyber influence operation",
    "deepfake fraud",
    "ai impersonation",
    "synthetic identity fraud",

    # --------------------------------------------------------
    # CRYPTO / BLOCKCHAIN
    # --------------------------------------------------------

    "crypto attack",
    "cryptocurrency attack",
    "crypto theft",
    "crypto wallet hack",
    "crypto exchange hack",
    "blockchain attack",
    "smart contract attack",
    "crypto scam",

    # --------------------------------------------------------
    # EXTORTION
    # --------------------------------------------------------

    "cyber extortion",
    "digital extortion",
    "ransom attack",
    "ransomware attack",
    "double extortion",
    "triple extortion",
    "data extortion",

    # --------------------------------------------------------
    # MALICIOUS WEBSITE / LINK
    # --------------------------------------------------------

    "malicious website",
    "malicious link",
    "malicious url",
    "fake website",
    "fake login page",
    "malicious domain",
    "malicious domain attack",

    # --------------------------------------------------------
    # DARK WEB / CYBERCRIME
    # --------------------------------------------------------

    "dark web cybercrime",
    "dark web stolen data",
    "stolen credentials",
    "stolen account",
    "cybercrime marketplace",
    "malware marketplace",
    "ransomware group",

    # --------------------------------------------------------
    # AI RELATED CYBER ATTACK
    # --------------------------------------------------------

    "ai cyber attack",
    "ai-powered cyber attack",
    "ai powered cyber attack",
    "artificial intelligence cyber attack",
    "generative ai cyber attack",
    "ai phishing",
    "ai scam",
    "ai fraud",
    "ai malware",
    "ai social engineering",
    "ai vulnerability",
    "ai security attack"
]


# ============================================================
# ATTACK EVENT INDICATORS
# ============================================================

EVENT_INDICATORS = [

    "attacked",
    "attackers",
    "targeted",
    "targeting",
    "breached",
    "compromised",
    "infected",
    "exploited",
    "hacked",
    "hit by",
    "hit with",
    "fell victim",
    "victim of",
    "stolen",
    "exfiltrated",
    "leaked",
    "disrupted",
    "shutdown",
    "intrusion",
    "incident",
    "campaign",
    "threat actor",
    "threat group",
    "victims",
    "affected",
    "unauthorized access",
    "data stolen",
    "data leaked",
    "credentials stolen"
]


# ============================================================
# NON-INCIDENT / GENERAL DISCUSSION INDICATORS
# ============================================================

NON_INCIDENT_INDICATORS = [

    "conference",
    "webinar",
    "workshop",
    "training",
    "course",
    "certification",
    "summit",
    "forum",
    "event",
    "panel discussion",
    "research paper",
    "academic study",
    "study finds",
    "report discusses",
    "guide",
    "guidance",
    "best practices",
    "awareness campaign",
    "awareness program",
    "prevention",
    "how to protect",
    "how to prevent",
    "tips to avoid",
    "security advice",
    "security training",
    "cybersecurity strategy"
]


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text):

    if not text:

        return ""

    text = text.lower()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# KEYWORD MATCHING
# ============================================================

def find_matches(
    text,
    keywords
):

    matches = []

    for keyword in keywords:

        keyword_normalized = (
            keyword.lower()
        )

        if keyword_normalized in text:

            matches.append(
                keyword
            )

    return matches


# ============================================================
# RELEVANCE ANALYSIS
# ============================================================

def analyze_relevance(
    title,
    summary
):

    title_text = normalize_text(
        title
    )

    summary_text = normalize_text(
        summary
    )

    full_text = (
        f"{title_text} "
        f"{summary_text}"
    ).strip()

    if not full_text:

        return {
            "label": "NOT_RELEVANT",
            "score": 0.0,
            "confidence": 0.0,
            "method": "RULE_BASED",
            "attack_matches": [],
            "event_matches": [],
            "non_incident_matches": []
        }

    attack_matches = find_matches(
        full_text,
        ATTACK_KEYWORDS
    )

    event_matches = find_matches(
        full_text,
        EVENT_INDICATORS
    )

    non_incident_matches = find_matches(
        full_text,
        NON_INCIDENT_INDICATORS
    )

    title_attack_matches = find_matches(
        title_text,
        ATTACK_KEYWORDS
    )

    title_event_matches = find_matches(
        title_text,
        EVENT_INDICATORS
    )

    # --------------------------------------------------------
    # BASE SCORE
    # --------------------------------------------------------

    score = 0.0

    # Cyber attack keyword
    if attack_matches:

        score += 0.40

    # Multiple attack concepts
    if len(attack_matches) >= 2:

        score += 0.15

    if len(attack_matches) >= 4:

        score += 0.10

    # Actual incident/event language
    if event_matches:

        score += 0.20

    # Stronger evidence in title
    if title_attack_matches:

        score += 0.10

    if title_event_matches:

        score += 0.10

    # General discussion penalty
    if non_incident_matches:

        score -= 0.15

    # --------------------------------------------------------
    # SCORE NORMALIZATION
    # --------------------------------------------------------

    if score < 0:

        score = 0.0

    if score > 1:

        score = 1.0

    # --------------------------------------------------------
    # CLASSIFICATION
    # --------------------------------------------------------

    if score >= RELEVANT_THRESHOLD:

        label = "RELEVANT"

    elif score >= UNCERTAIN_THRESHOLD:

        label = "UNCERTAIN"

    else:

        label = "NOT_RELEVANT"

    # --------------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------------

    confidence = abs(
        score - 0.50
    ) * 2

    if confidence > 1:

        confidence = 1.0

    # --------------------------------------------------------
    # RETURN RESULT
    # --------------------------------------------------------

    return {
        "label": label,
        "score": round(
            score,
            4
        ),
        "confidence": round(
            confidence,
            4
        ),
        "method": "RULE_BASED",
        "attack_matches": attack_matches,
        "event_matches": event_matches,
        "non_incident_matches": non_incident_matches
    }


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def initialize_v02_database():

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    # --------------------------------------------------------
    # V0.2 ANALYSIS TABLE
    # --------------------------------------------------------

    cursor.execute(
        """
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
        """
    )

    # --------------------------------------------------------
    # INDEX
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_v02_relevance_label
        ON v02_relevance(relevance_label)
        """
    )

    connection.commit()

    connection.close()


# ============================================================
# GET TOTAL ARTICLES
# ============================================================

def get_total_articles():

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM articles
        """
    )

    total = cursor.fetchone()[0]

    connection.close()

    return total


# ============================================================
# GET ANALYZED ARTICLES
# ============================================================

def get_analyzed_articles():

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM v02_relevance
        """
    )

    total = cursor.fetchone()[0]

    connection.close()

    return total


# ============================================================
# GET NEXT BATCH
# ============================================================

def get_next_batch():

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            a.article_id,
            a.title,
            a.summary,
            a.language

        FROM articles a

        LEFT JOIN v02_relevance v
            ON a.article_id = v.article_id

        WHERE v.article_id IS NULL

        ORDER BY a.article_id

        LIMIT ?
        """,
        (
            BATCH_SIZE,
        )
    )

    rows = cursor.fetchall()

    connection.close()

    return rows


# ============================================================
# SAVE ANALYSIS
# ============================================================

def save_analysis(
    article_id,
    result
):

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    analyzed_at = datetime.now(
        timezone.utc
    ).isoformat()

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
            " | ".join(
                result["attack_matches"]
            ),
            " | ".join(
                result["event_matches"]
            ),
            " | ".join(
                result["non_incident_matches"]
            ),
            analyzed_at
        )
    )

    connection.commit()

    connection.close()


# ============================================================
# PROCESS BATCH
# ============================================================

def process_batch(
    rows
):

    processed = 0

    relevant = 0
    uncertain = 0
    not_relevant = 0

    for row in rows:

        article_id = row[0]
        title = row[1] or ""
        summary = row[2] or ""
        language = row[3] or "unknown"

        result = analyze_relevance(
            title,
            summary
        )

        save_analysis(
            article_id,
            result
        )

        processed += 1

        if result["label"] == "RELEVANT":

            relevant += 1

        elif result["label"] == "UNCERTAIN":

            uncertain += 1

        else:

            not_relevant += 1

        # ----------------------------------------------------
        # DISPLAY SAMPLE
        # ----------------------------------------------------

        if processed <= 10:

            print(
                f"\n[{processed}] "
                f"Article ID : {article_id}"
            )

            print(
                f"    Language   : {language}"
            )

            print(
                f"    Title      : "
                f"{title[:120]}"
            )

            print(
                f"    Relevance  : "
                f"{result['label']}"
            )

            print(
                f"    Score      : "
                f"{result['score']:.2f}"
            )

            print(
                f"    Confidence : "
                f"{result['confidence']:.2f}"
            )

    return (
        processed,
        relevant,
        uncertain,
        not_relevant
    )


# ============================================================
# DATABASE SUMMARY
# ============================================================

def get_v02_summary():

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            relevance_label,
            COUNT(*)

        FROM v02_relevance

        GROUP BY relevance_label
        """
    )

    rows = cursor.fetchall()

    connection.close()

    summary = {
        "RELEVANT": 0,
        "UNCERTAIN": 0,
        "NOT_RELEVANT": 0
    }

    for label, count in rows:

        if label in summary:

            summary[label] = count

    return summary


# ============================================================
# MAIN V0.2
# ============================================================

def run():

    print("\n==================================================")
    print("   CSAIS V0.2 - RELEVANCE DETECTION")
    print("==================================================")

    # --------------------------------------------------------
    # CHECK DATABASE
    # --------------------------------------------------------

    if not os.path.exists(
        DATABASE_FILE
    ):

        print(
            "\n❌ Database tidak ditemukan:"
        )

        print(
            f"   {DATABASE_FILE}"
        )

        return

    # --------------------------------------------------------
    # INITIALIZE V0.2
    # --------------------------------------------------------

    initialize_v02_database()

    # --------------------------------------------------------
    # DATABASE SUMMARY
    # --------------------------------------------------------

    total_articles = (
        get_total_articles()
    )

    analyzed_articles = (
        get_analyzed_articles()
    )

    print(
        f"\nTotal articles      : "
        f"{total_articles}"
    )

    print(
        f"Sudah dianalisis    : "
        f"{analyzed_articles}"
    )

    print(
        f"Belum dianalisis    : "
        f"{total_articles - analyzed_articles}"
    )

    # --------------------------------------------------------
    # PROCESS ARTICLES
    # --------------------------------------------------------

    total_processed = 0

    while True:

        rows = get_next_batch()

        if not rows:

            break

        (
            processed,
            relevant,
            uncertain,
            not_relevant
        ) = process_batch(
            rows
        )

        total_processed += processed

        print(
            f"\nBatch processed : "
            f"{processed}"
        )

        print(
            f"Total processed : "
            f"{total_processed}"
        )

    # --------------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------------

    summary = get_v02_summary()

    print("\n==================================================")
    print("   V0.2 ANALYSIS SUMMARY")
    print("==================================================")

    print(
        f"\nTotal articles       : "
        f"{total_articles}"
    )

    print(
        f"Total analyzed       : "
        f"{analyzed_articles + total_processed}"
    )

    print(
        f"\nRELEVANT             : "
        f"{summary['RELEVANT']}"
    )

    print(
        f"UNCERTAIN            : "
        f"{summary['UNCERTAIN']}"
    )

    print(
        f"NOT_RELEVANT         : "
        f"{summary['NOT_RELEVANT']}"
    )

    print(
        "\n=================================================="
    )

    print(
        "   ✅ V0.2 RELEVANCE DETECTION SELESAI"
    )

    print(
        "=================================================="
    )


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":

    run()