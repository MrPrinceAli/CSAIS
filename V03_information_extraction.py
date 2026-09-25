# ============================================================
# CYBER SOCIAL ATTACK INTELLIGENCE SYSTEM
# V0.3 - INFORMATION EXTRACTION
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


# ============================================================
# ATTACK TYPE KEYWORDS
# ============================================================

ATTACK_TYPE_KEYWORDS = {

    # --------------------------------------------------------
    # MALWARE
    # --------------------------------------------------------

    "RANSOMWARE": [
        "ransomware",
        "ransom attack",
        "ransomware attack"
    ],

    "MALWARE": [
        "malware",
        "trojan",
        "worm",
        "spyware",
        "rootkit",
        "backdoor",
        "botnet",
        "infostealer",
        "information stealer",
        "keylogger"
    ],

    # --------------------------------------------------------
    # CREDENTIAL / IDENTITY
    # --------------------------------------------------------

    "ACCOUNT_TAKEOVER": [
        "account takeover",
        "account hijacking",
        "stolen account"
    ],

    "CREDENTIAL_ATTACK": [
        "credential stuffing",
        "password spraying",
        "brute force attack",
        "password attack",
        "credential stealing",
        "credential theft"
    ],

    # --------------------------------------------------------
    # SOCIAL ENGINEERING
    # --------------------------------------------------------

    "PHISHING": [
        "phishing",
        "spear phishing",
        "spearphishing",
        "smishing",
        "vishing",
        "quishing"
    ],

    "SOCIAL_ENGINEERING": [
        "social engineering",
        "impersonation",
        "business email compromise",
        "bec attack",
        "ceo fraud",
        "executive impersonation"
    ],

    "ONLINE_SCAM": [
        "online scam",
        "online fraud",
        "cyber fraud",
        "digital fraud"
    ],

    "JOB_SCAM": [
        "job scam",
        "employment scam",
        "recruitment scam"
    ],

    "INVESTMENT_SCAM": [
        "investment scam",
        "investment fraud"
    ],

    # --------------------------------------------------------
    # WEB / APPLICATION
    # --------------------------------------------------------

    "WEB_ATTACK": [
        "web attack",
        "website attack",
        "web application attack"
    ],

    "SQL_INJECTION": [
        "sql injection",
        "sqli"
    ],

    "XSS": [
        "cross site scripting",
        "xss attack"
    ],

    "REMOTE_CODE_EXECUTION": [
        "remote code execution",
        "rce"
    ],

    "PATH_TRAVERSAL": [
        "path traversal",
        "directory traversal"
    ],

    "FILE_INCLUSION": [
        "file inclusion"
    ],

    # --------------------------------------------------------
    # VULNERABILITY / EXPLOIT
    # --------------------------------------------------------

    "ZERO_DAY": [
        "zero-day",
        "zero day",
        "zero-day vulnerability",
        "zero day vulnerability"
    ],

    "VULNERABILITY_EXPLOITATION": [
        "zero-day exploit",
        "zero day exploit",
        "actively exploited",
        "vulnerability exploited",
        "exploitation"
    ],

    # --------------------------------------------------------
    # NETWORK
    # --------------------------------------------------------

    "DDoS": [
        "ddos",
        "distributed denial of service",
        "denial of service",
        "dos attack"
    ],

    "DNS_ATTACK": [
        "dns hijacking",
        "dns poisoning",
        "dns spoofing",
        "dns attack"
    ],

    "NETWORK_INTRUSION": [
        "network intrusion",
        "network compromise"
    ],

    # --------------------------------------------------------
    # DATA
    # --------------------------------------------------------

    "DATA_BREACH": [
        "data breach",
        "database breach",
        "personal data breach",
        "customer data breach"
    ],

    "DATA_LEAK": [
        "data leak",
        "database leak",
        "stolen data",
        "data leaked"
    ],

    "DATA_THEFT": [
        "data theft",
        "information theft",
        "data stolen"
    ],

    "DATA_EXFILTRATION": [
        "data exfiltration",
        "exfiltrated"
    ],

    # --------------------------------------------------------
    # SUPPLY CHAIN
    # --------------------------------------------------------

    "SUPPLY_CHAIN_ATTACK": [
        "supply chain attack",
        "supply chain compromise",
        "software supply chain attack",
        "third party compromise",
        "third-party compromise"
    ],

    # --------------------------------------------------------
    # CLOUD
    # --------------------------------------------------------

    "CLOUD_ATTACK": [
        "cloud attack",
        "cloud breach",
        "cloud compromise",
        "cloud exploitation"
    ],

    # --------------------------------------------------------
    # INSIDER
    # --------------------------------------------------------

    "INSIDER_THREAT": [
        "insider threat",
        "insider attack",
        "malicious insider"
    ],

    # --------------------------------------------------------
    # CRITICAL INFRASTRUCTURE / OT
    # --------------------------------------------------------

    "CRITICAL_INFRASTRUCTURE_ATTACK": [
        "critical infrastructure attack",
        "critical infrastructure cyber attack",
        "power grid cyber attack",
        "water system cyber attack",
        "energy sector cyber attack"
    ],

    "ICS_SCADA_ATTACK": [
        "ics attack",
        "scada attack",
        "ot attack",
        "industrial control system attack"
    ],

    # --------------------------------------------------------
    # MOBILE / IOT
    # --------------------------------------------------------

    "MOBILE_ATTACK": [
        "mobile attack",
        "android attack",
        "ios malware",
        "mobile malware",
        "mobile ransomware"
    ],

    "IOT_ATTACK": [
        "iot attack",
        "iot malware",
        "iot botnet",
        "iot security breach"
    ],

    # --------------------------------------------------------
    # WEBSITE / DOMAIN
    # --------------------------------------------------------

    "WEBSITE_DEFACEMENT": [
        "website defacement",
        "web defacement"
    ],

    "DOMAIN_HIJACKING": [
        "domain hijacking",
        "domain takeover"
    ],

    "MALICIOUS_WEBSITE": [
        "malicious website",
        "fake website",
        "malicious domain",
        "fake login page"
    ],

    "MALICIOUS_LINK": [
        "malicious link",
        "malicious url"
    ],

    # --------------------------------------------------------
    # CYBER ESPIONAGE
    # --------------------------------------------------------

    "CYBER_ESPIONAGE": [
        "cyber espionage",
        "cyber spying",
        "cyber espionage campaign"
    ],

    "APT": [
        "apt attack",
        "advanced persistent threat",
        "apt campaign"
    ],

    # --------------------------------------------------------
    # INFORMATION OPERATIONS
    # --------------------------------------------------------

    "INFORMATION_OPERATION": [
        "information operation",
        "influence operation",
        "online influence operation",
        "disinformation campaign"
    ],

    "DEEPFAKE_FRAUD": [
        "deepfake fraud",
        "deepfake scam",
        "ai impersonation"
    ],

    # --------------------------------------------------------
    # CRYPTO / BLOCKCHAIN
    # --------------------------------------------------------

    "CRYPTO_ATTACK": [
        "crypto attack",
        "cryptocurrency attack",
        "crypto theft",
        "crypto wallet hack",
        "crypto exchange hack",
        "blockchain attack",
        "smart contract attack"
    ],

    # --------------------------------------------------------
    # EXTORTION
    # --------------------------------------------------------

    "CYBER_EXTORTION": [
        "cyber extortion",
        "digital extortion",
        "double extortion",
        "triple extortion"
    ]
}


# ============================================================
# ATTACK METHOD KEYWORDS
# ============================================================

ATTACK_METHOD_KEYWORDS = {

    "PHISHING": [
        "phishing",
        "spear phishing",
        "smishing",
        "vishing",
        "quishing"
    ],

    "SOCIAL_ENGINEERING": [
        "social engineering",
        "impersonation",
        "business email compromise",
        "bec attack"
    ],

    "MALWARE": [
        "malware",
        "trojan",
        "spyware",
        "backdoor",
        "botnet",
        "infostealer"
    ],

    "EXPLOITATION": [
        "exploit",
        "exploited",
        "exploitation",
        "zero-day",
        "zero day"
    ],

    "BRUTE_FORCE": [
        "brute force",
        "password spraying",
        "credential stuffing"
    ],

    "VULNERABILITY_EXPLOITATION": [
        "vulnerability exploited",
        "actively exploited",
        "security vulnerability"
    ],

    "MALICIOUS_LINK": [
        "malicious link",
        "malicious url"
    ],

    "MALICIOUS_WEBSITE": [
        "malicious website",
        "fake website",
        "fake login page"
    ]
}


# ============================================================
# TARGET SECTOR KEYWORDS
# ============================================================

TARGET_SECTOR_KEYWORDS = {

    "HEALTHCARE": [
        "hospital",
        "healthcare",
        "health care",
        "clinic",
        "medical",
        "health system"
    ],

    "FINANCE": [
        "bank",
        "banking",
        "financial institution",
        "financial services",
        "fintech",
        "insurance"
    ],

    "GOVERNMENT": [
        "government",
        "ministry",
        "municipality",
        "government agency",
        "public sector"
    ],

    "EDUCATION": [
        "university",
        "college",
        "school",
        "education institution",
        "educational institution"
    ],

    "TELECOMMUNICATION": [
        "telecom",
        "telecommunication",
        "mobile operator",
        "internet service provider",
        "isp"
    ],

    "ENERGY": [
        "energy",
        "electricity",
        "power grid",
        "oil and gas",
        "utility"
    ],

    "MANUFACTURING": [
        "manufacturing",
        "factory",
        "industrial",
        "manufacturer"
    ],

    "RETAIL": [
        "retail",
        "e-commerce",
        "ecommerce",
        "online store"
    ],

    "TRANSPORTATION": [
        "airline",
        "airport",
        "railway",
        "rail",
        "transportation",
        "shipping",
        "port"
    ],

    "CRITICAL_INFRASTRUCTURE": [
        "critical infrastructure",
        "water system",
        "power grid",
        "industrial control system",
        "ics",
        "scada"
    ],

    "TECHNOLOGY": [
        "technology company",
        "software company",
        "tech company",
        "cloud provider",
        "software provider"
    ]
}


# ============================================================
# TARGET GROUP KEYWORDS
# ============================================================

TARGET_GROUP_KEYWORDS = {

    "INDIVIDUALS": [
        "individuals",
        "users",
        "customers",
        "citizens",
        "consumers"
    ],

    "EMPLOYEES": [
        "employees",
        "staff",
        "workers"
    ],

    "STUDENTS": [
        "students",
        "student"
    ],

    "CHILDREN": [
        "children",
        "kids",
        "minors"
    ],

    "JOB_SEEKERS": [
        "job seekers",
        "jobseekers",
        "job applicants"
    ],

    "BUSINESSES": [
        "businesses",
        "companies",
        "enterprises"
    ],

    "GOVERNMENT": [
        "government agencies",
        "government institutions",
        "public agencies"
    ]
}


# ============================================================
# IMPACT KEYWORDS
# ============================================================

IMPACT_KEYWORDS = {

    "DATA_THEFT": [
        "data stolen",
        "data theft",
        "information stolen",
        "stolen data",
        "customer data stolen"
    ],

    "DATA_LEAK": [
        "data leak",
        "data leaked",
        "information leaked",
        "database leak"
    ],

    "SERVICE_DISRUPTION": [
        "service disruption",
        "services disrupted",
        "operations disrupted",
        "system disruption",
        "service outage",
        "systems down"
    ],

    "FINANCIAL_LOSS": [
        "financial loss",
        "financial losses",
        "lost money",
        "money stolen",
        "financial damage"
    ],

    "SYSTEM_COMPROMISE": [
        "system compromised",
        "systems compromised",
        "server compromised",
        "network compromised"
    ],

    "ACCOUNT_COMPROMISE": [
        "account compromised",
        "accounts compromised",
        "account takeover"
    ],

    "OPERATIONAL_IMPACT": [
        "operations halted",
        "operations disrupted",
        "business disruption",
        "business operations affected"
    ]
}


# ============================================================
# COUNTRY / LOCATION KEYWORDS
# ============================================================

COUNTRY_NAMES = {

    "Indonesia": [
        "indonesia",
        "indonesian"
    ],

    "Singapore": [
        "singapore",
        "singaporean"
    ],

    "Malaysia": [
        "malaysia",
        "malaysian"
    ],

    "Thailand": [
        "thailand",
        "thai"
    ],

    "Vietnam": [
        "vietnam",
        "vietnamese"
    ],

    "Philippines": [
        "philippines",
        "filipino"
    ],

    "India": [
        "india",
        "indian"
    ],

    "China": [
        "china",
        "chinese"
    ],

    "Japan": [
        "japan",
        "japanese"
    ],

    "South Korea": [
        "south korea",
        "korean"
    ],

    "Australia": [
        "australia",
        "australian"
    ],

    "United States": [
        "united states",
        "u.s.",
        "american"
    ],

    "United Kingdom": [
        "united kingdom",
        "britain",
        "british"
    ],

    "Germany": [
        "germany",
        "german"
    ],

    "France": [
        "france",
        "french"
    ],

    "Russia": [
        "russia",
        "russian"
    ],

    "Ukraine": [
        "ukraine",
        "ukrainian"
    ],

    "Canada": [
        "canada",
        "canadian"
    ],

    "Brazil": [
        "brazil",
        "brazilian"
    ]
}


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(
    text
):

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
# FIND KEYWORD MATCHES
# ============================================================

def find_keyword_matches(
    text,
    keyword_dictionary
):

    matches = []

    for category, keywords in (
        keyword_dictionary.items()
    ):

        for keyword in keywords:

            keyword_normalized = (
                keyword.lower()
            )

            if keyword_normalized in text:

                matches.append(
                    category
                )

                break

    return matches


# ============================================================
# EXTRACT ATTACK TYPE
# ============================================================

def extract_attack_type(
    text
):

    matches = find_keyword_matches(
        text,
        ATTACK_TYPE_KEYWORDS
    )

    if not matches:

        return "UNKNOWN"

    return ", ".join(
        matches
    )


# ============================================================
# EXTRACT ATTACK METHOD
# ============================================================

def extract_attack_method(
    text
):

    matches = find_keyword_matches(
        text,
        ATTACK_METHOD_KEYWORDS
    )

    if not matches:

        return "UNKNOWN"

    return ", ".join(
        matches
    )


# ============================================================
# EXTRACT TARGET SECTOR
# ============================================================

def extract_target_sector(
    text
):

    matches = find_keyword_matches(
        text,
        TARGET_SECTOR_KEYWORDS
    )

    if not matches:

        return "UNKNOWN"

    return ", ".join(
        matches
    )


# ============================================================
# EXTRACT TARGET GROUP
# ============================================================

def extract_target_group(
    text
):

    matches = find_keyword_matches(
        text,
        TARGET_GROUP_KEYWORDS
    )

    if not matches:

        return "UNKNOWN"

    return ", ".join(
        matches
    )


# ============================================================
# EXTRACT IMPACT
# ============================================================

def extract_impact(
    text
):

    matches = find_keyword_matches(
        text,
        IMPACT_KEYWORDS
    )

    if not matches:

        return "UNKNOWN"

    return ", ".join(
        matches
    )


# ============================================================
# EXTRACT LOCATION
# ============================================================

def extract_location(
    text
):

    locations = []

    for country, keywords in (
        COUNTRY_NAMES.items()
    ):

        for keyword in keywords:

            keyword_normalized = (
                keyword.lower()
            )

            if keyword_normalized in text:

                locations.append(
                    country
                )

                break

    if not locations:

        return "UNKNOWN"

    return ", ".join(
        locations
    )


# ============================================================
# EXTRACT THREAT ACTOR
# ============================================================

def extract_threat_actor(
    text
):

    patterns = [

        r"threat actor ([a-z0-9\-_ ]{2,60})",

        r"threat group ([a-z0-9\-_ ]{2,60})",

        r"ransomware group ([a-z0-9\-_ ]{2,60})",

        r"apt group ([a-z0-9\-_ ]{2,60})"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            actor = (
                match.group(1)
                .strip()
            )

            actor = re.split(
                r"[,.!?;:]",
                actor
            )[0]

            return actor[:100]

    return "UNKNOWN"


# ============================================================
# EXTRACT TARGET ORGANIZATION
# ============================================================

def extract_target_organization(
    title,
    text
):

    search_text = (
        f"{title} {text}"
    )

    patterns = [

        r"([A-Z][A-Za-z0-9&.\- ]{2,80})\s+(?:was|were)\s+(?:hit|attacked|breached|hacked|compromised)",

        r"([A-Z][A-Za-z0-9&.\- ]{2,80})\s+(?:suffered|experienced)\s+(?:a\s+)?(?:cyber|ransomware|data)\s+(?:attack|breach|incident)"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            search_text,
            re.IGNORECASE
        )

        if match:

            organization = (
                match.group(1)
                .strip()
            )

            organization = re.sub(
                r"\s+",
                " ",
                organization
            )

            return organization[:150]

    return "UNKNOWN"


# ============================================================
# EXTRACT ATTACK DATE
# ============================================================

def extract_attack_date(
    text
):

    patterns = [

        r"\b(20\d{2}-\d{2}-\d{2})\b",

        r"\b(\d{1,2}/\d{1,2}/20\d{2})\b",

        r"\b(\d{1,2}-\d{1,2}-20\d{2})\b"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text
        )

        if match:

            return match.group(1)

    return "UNKNOWN"


# ============================================================
# EXTRACT INDICATORS
# ============================================================

def extract_indicators(
    text
):

    indicators = []

    patterns = [

        r"\bCVE-\d{4}-\d{4,7}\b",

        r"\b[A-Fa-f0-9]{32}\b",

        r"\b[A-Fa-f0-9]{40}\b",

        r"\b[A-Fa-f0-9]{64}\b"
    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            re.IGNORECASE
        )

        indicators.extend(
            matches
        )

    indicators = list(
        dict.fromkeys(
            indicators
        )
    )

    if not indicators:

        return "UNKNOWN"

    return ", ".join(
        indicators
    )


# ============================================================
# CALCULATE EXTRACTION CONFIDENCE
# ============================================================

def calculate_extraction_confidence(
    attack_type,
    attack_method,
    target_sector,
    location,
    impact
):

    fields = [

        attack_type,
        attack_method,
        target_sector,
        location,
        impact
    ]

    known_fields = 0

    for field in fields:

        if field != "UNKNOWN":

            known_fields += 1

    confidence = (
        known_fields /
        len(fields)
    )

    return round(
        confidence,
        4
    )


# ============================================================
# INFORMATION EXTRACTION
# ============================================================

def extract_information(
    article_id,
    title,
    summary,
    content
):

    title_text = normalize_text(
        title
    )

    summary_text = normalize_text(
        summary
    )

    content_text = normalize_text(
        content
    )

    combined_text = (
        f"{title_text} "
        f"{summary_text} "
        f"{content_text}"
    ).strip()

    attack_type = extract_attack_type(
        combined_text
    )

    attack_method = extract_attack_method(
        combined_text
    )

    target_sector = extract_target_sector(
        combined_text
    )

    location = extract_location(
        combined_text
    )

    threat_actor = extract_threat_actor(
        combined_text
    )

    target_organization = (
        extract_target_organization(
            title,
            combined_text
        )
    )

    target_group = extract_target_group(
        combined_text
    )

    attack_date = extract_attack_date(
        combined_text
    )

    impact = extract_impact(
        combined_text
    )

    indicators = extract_indicators(
        combined_text
    )

    extraction_confidence = (
        calculate_extraction_confidence(
            attack_type,
            attack_method,
            target_sector,
            location,
            impact
        )
    )

    return {

        "article_id": article_id,

        "attack_type": attack_type,

        "attack_method": attack_method,

        "target": (
            target_organization
        ),

        "target_organization": (
            target_organization
        ),

        "target_sector": (
            target_sector
        ),

        "target_group": (
            target_group
        ),

        "location": (
            location
        ),

        "attack_date": (
            attack_date
        ),

        "threat_actor": (
            threat_actor
        ),

        "impact": (
            impact
        ),

        "indicator": (
            indicators
        ),

        "extraction_confidence": (
            extraction_confidence
        ),

        "extraction_method": (
            "RULE_BASED"
        )
    }


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def initialize_v03_database():

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS
        v03_information_extraction (

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
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_v03_attack_type
        ON v03_information_extraction(
            attack_type
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_v03_location
        ON v03_information_extraction(
            location
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_v03_target_sector
        ON v03_information_extraction(
            target_sector
        )
        """
    )

    connection.commit()

    connection.close()


# ============================================================
# GET TOTAL CANDIDATES
# ============================================================

def get_total_candidates():

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM articles a

        INNER JOIN v02_relevance v
            ON a.article_id = v.article_id

        WHERE v.relevance_label IN (
            'RELEVANT',
            'UNCERTAIN'
        )
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
        FROM v03_information_extraction
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
            a.content,
            a.language,
            v.relevance_label,
            v.relevance_score

        FROM articles a

        INNER JOIN v02_relevance v
            ON a.article_id = v.article_id

        LEFT JOIN
            v03_information_extraction x
            ON a.article_id = x.article_id

        WHERE
            v.relevance_label IN (
                'RELEVANT',
                'UNCERTAIN'
            )

            AND x.article_id IS NULL

        ORDER BY
            a.article_id

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
# SAVE EXTRACTION
# ============================================================

def save_extraction(
    result
):

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    extracted_at = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    cursor.execute(
        """
        INSERT OR REPLACE INTO
        v03_information_extraction (

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

        VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?
        )
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

            extracted_at
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

    for row in rows:

        article_id = row[0]

        title = row[1] or ""

        summary = row[2] or ""

        content = row[3] or ""

        language = row[4] or "unknown"

        relevance_label = (
            row[5] or "UNKNOWN"
        )

        relevance_score = (
            row[6] or 0.0
        )

        result = extract_information(

            article_id,

            title,

            summary,

            content
        )

        save_extraction(
            result
        )

        processed += 1

        # ----------------------------------------------------
        # DISPLAY SAMPLE
        # ----------------------------------------------------

        if processed <= 10:

            print(
                f"\n[{processed}] "
                f"Article ID : {article_id}"
            )

            print(
                f"    Language       : "
                f"{language}"
            )

            print(
                f"    V0.2 Relevance : "
                f"{relevance_label}"
            )

            print(
                f"    V0.2 Score     : "
                f"{relevance_score:.2f}"
            )

            print(
                f"    Title          : "
                f"{title[:120]}"
            )

            print(
                f"    Attack Type    : "
                f"{result['attack_type']}"
            )

            print(
                f"    Attack Method  : "
                f"{result['attack_method']}"
            )

            print(
                f"    Target         : "
                f"{result['target']}"
            )

            print(
                f"    Sector         : "
                f"{result['target_sector']}"
            )

            print(
                f"    Location       : "
                f"{result['location']}"
            )

            print(
                f"    Impact         : "
                f"{result['impact']}"
            )

            print(
                f"    Confidence     : "
                f"{result['extraction_confidence']:.2f}"
            )

    return processed


# ============================================================
# V0.3 SUMMARY
# ============================================================

def get_v03_summary():

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            attack_type,
            COUNT(*)

        FROM v03_information_extraction

        GROUP BY attack_type

        ORDER BY COUNT(*) DESC

        LIMIT 15
        """
    )

    attack_rows = cursor.fetchall()

    cursor.execute(
        """
        SELECT
            target_sector,
            COUNT(*)

        FROM v03_information_extraction

        GROUP BY target_sector

        ORDER BY COUNT(*) DESC

        LIMIT 15
        """
    )

    sector_rows = cursor.fetchall()

    connection.close()

    return (
        attack_rows,
        sector_rows
    )


# ============================================================
# MAIN V0.3
# ============================================================

def run():

    print("\n==================================================")
    print("   CSAIS V0.3 - INFORMATION EXTRACTION")
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
    # INITIALIZE V0.3
    # --------------------------------------------------------

    initialize_v03_database()

    # --------------------------------------------------------
    # DATABASE SUMMARY
    # --------------------------------------------------------

    total_candidates = (
        get_total_candidates()
    )

    analyzed_articles = (
        get_analyzed_articles()
    )

    print(
        f"\nTotal V0.2 candidates : "
        f"{total_candidates}"
    )

    print(
        f"Sudah dianalisis     : "
        f"{analyzed_articles}"
    )

    print(
        f"Belum dianalisis     : "
        f"{total_candidates - analyzed_articles}"
    )

    # --------------------------------------------------------
    # PROCESS ARTICLES
    # --------------------------------------------------------

    total_processed = 0

    while True:

        rows = get_next_batch()

        if not rows:

            break

        processed = process_batch(
            rows
        )

        total_processed += (
            processed
        )

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

    (
        attack_rows,
        sector_rows
    ) = get_v03_summary()

    final_total = (
        get_analyzed_articles()
    )

    print("\n==================================================")
    print("   V0.3 ANALYSIS SUMMARY")
    print("==================================================")

    print(
        f"\nTotal candidates : "
        f"{total_candidates}"
    )

    print(
        f"Total extracted  : "
        f"{final_total}"
    )

    print(
        "\nTOP ATTACK TYPES"
    )

    print(
        "--------------------------------------------------"
    )

    for attack_type, count in attack_rows:

        print(
            f"{attack_type:<35} "
            f"{count}"
        )

    print(
        "\nTOP TARGET SECTORS"
    )

    print(
        "--------------------------------------------------"
    )

    for sector, count in sector_rows:

        print(
            f"{sector:<35} "
            f"{count}"
        )

    print(
        "\n=================================================="
    )

    print(
        "   ✅ V0.3 INFORMATION EXTRACTION SELESAI"
    )

    print(
        "=================================================="
    )


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":

    run()