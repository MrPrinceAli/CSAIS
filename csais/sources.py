"""Registri sumber dan penanda sindikasi.

- Tabel ``sources``: satu baris per domain media atau lembaga: tipe
  (MEDIA/OFFICIAL), negara dari TLD, nama penerbit terumum, jumlah artikel,
  pertama dan terakhir terlihat. Dibangun ulang dari tabel articles memakai
  URL media asli (``resolved_url`` hasil content_fetcher) bila ada. Ini bahan
  "riwayat sumber" untuk trust score.
- ``articles.syndicated_of``: artikel yang judulnya (tanpa nama media) sama
  dengan artikel lebih awal dalam SYNDICATION_WINDOW_DAYS ditandai sebagai
  salinan sindikasi dan menunjuk ke artikel aslinya.
"""

from datetime import datetime
from urllib.parse import urlparse

from csais.db import get_timestamp
from csais.schema import ensure_column
from csais.text import normalize_text, split_publisher

SYNDICATION_WINDOW_DAYS = 14
UNRESOLVED_DOMAIN = "news.google.com"

# Negara dari top-level domain; selain ini "unknown"
TLD_COUNTRY = {
    "id": "ID", "my": "MY", "sg": "SG", "au": "AU", "nz": "NZ", "uk": "GB", "ie": "IE",
    "in": "IN", "pk": "PK", "bd": "BD", "lk": "LK", "jp": "JP", "kr": "KR", "cn": "CN",
    "hk": "HK", "tw": "TW", "th": "TH", "vn": "VN", "ph": "PH", "de": "DE", "fr": "FR",
    "es": "ES", "it": "IT", "nl": "NL", "be": "BE", "ch": "CH", "at": "AT", "pl": "PL",
    "cz": "CZ", "se": "SE", "no": "NO", "dk": "DK", "fi": "FI", "pt": "PT", "br": "BR",
    "mx": "MX", "ar": "AR", "cl": "CL", "co": "CO", "ca": "CA", "us": "US", "ru": "RU",
    "ua": "UA", "tr": "TR", "il": "IL", "ae": "AE", "sa": "SA", "eg": "EG", "za": "ZA",
    "ng": "NG", "ke": "KE",
}


def domain_of(url):
    """Nama host tanpa awalan www., huruf kecil; kosong bila URL kosong."""
    host = (urlparse(url or "").netloc or "").lower()
    return host[4:] if host.startswith("www.") else host


# TLD negara yang lazim dipakai sebagai domain generik (tempo.co, industrialcyber.co,
# x.tv, y.me): hanya dianggap negara bila didahului sufiks registri resmi
# negara itu (eltiempo.com.co, abc.gov.co).
GENERIC_CCTLDS = {"co", "tv", "me", "cc", "fm", "ly", "io", "ai", "gg", "to", "ws"}
REGISTRY_SECOND_LEVEL = {"com", "net", "org", "gov", "edu", "ac", "co", "mil", "or", "go", "web"}


def country_of(domain):
    """Kode negara dari TLD domain, 'unknown' bila tidak dikenali atau TLD-nya generik."""
    parts = domain.lower().rsplit(".", 2)
    if len(parts) < 2:
        return "unknown"
    tld = parts[-1]
    if tld in GENERIC_CCTLDS and not (len(parts) == 3 and parts[-2] in REGISTRY_SECOND_LEVEL):
        return "unknown"
    return TLD_COUNTRY.get(tld, "unknown")


def create_tables(conn):
    """Buat tabel sources dan kolom syndicated_of bila belum ada."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sources (
            domain TEXT PRIMARY KEY,
            source_type TEXT,
            country TEXT,
            publisher_name TEXT,
            article_count INTEGER,
            first_seen TEXT,
            last_seen TEXT,
            updated_at TEXT
        )
        """)
    conn.commit()
    ensure_column(conn, "articles", "syndicated_of", "INTEGER")
    ensure_column(conn, "articles", "resolved_url", "TEXT")


def rebuild_sources(conn):
    """Bangun ulang tabel sources dari articles; kembalikan jumlah domain."""
    create_tables(conn)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COALESCE(resolved_url, article_url), source_type, title, published_date
        FROM articles
        """
    )
    registry = {}
    for url, source_type, title, published in cursor:
        domain = domain_of(url)
        if not domain or domain == UNRESOLVED_DOMAIN:
            continue
        entry = registry.setdefault(
            domain,
            {"official": False, "publishers": {}, "count": 0, "first": None, "last": None},
        )
        entry["count"] += 1
        if source_type == "OFFICIAL":
            entry["official"] = True
        publisher = split_publisher(title)[1]
        if publisher:
            entry["publishers"][publisher] = entry["publishers"].get(publisher, 0) + 1
        if published:
            if entry["first"] is None or published < entry["first"]:
                entry["first"] = published
            if entry["last"] is None or published > entry["last"]:
                entry["last"] = published

    now = get_timestamp()
    rows = []
    for domain, entry in registry.items():
        publishers = entry["publishers"]
        publisher_name = max(publishers, key=publishers.get) if publishers else None
        rows.append(
            (
                domain,
                "OFFICIAL" if entry["official"] else "MEDIA",
                country_of(domain),
                publisher_name,
                entry["count"],
                entry["first"],
                entry["last"],
                now,
            )
        )
    cursor.execute("DELETE FROM sources")
    cursor.executemany(
        """
        INSERT INTO sources (
            domain, source_type, country, publisher_name, article_count,
            first_seen, last_seen, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def _parse(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def mark_syndicated(conn):
    """Tandai salinan sindikasi (judul sama dalam jendela); kembalikan jumlahnya."""
    create_tables(conn)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT article_id, title, published_date FROM articles ORDER BY published_date"
    )
    groups = {}
    for article_id, title, published in cursor:
        headline = normalize_text(split_publisher(title)[0])
        if len(headline) < 20:
            continue
        groups.setdefault(headline, []).append((article_id, _parse(published)))

    window = SYNDICATION_WINDOW_DAYS * 86400
    marks = []
    for items in groups.values():
        if len(items) < 2:
            continue
        original_id, original_date = items[0]
        for article_id, published in items[1:]:
            if (
                original_date is None
                or published is None
                or (published - original_date).total_seconds() <= window
            ):
                marks.append((original_id, article_id))
            else:
                # Judul yang sama tetapi terpaut lama: anggap artikel asli baru
                original_id, original_date = article_id, published

    cursor.execute("UPDATE articles SET syndicated_of = NULL WHERE syndicated_of IS NOT NULL")
    cursor.executemany("UPDATE articles SET syndicated_of = ? WHERE article_id = ?", marks)
    conn.commit()
    return len(marks)


def summary(conn):
    """(jumlah domain, jumlah domain resmi, jumlah artikel sindikasi)."""
    create_tables(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(source_type = 'OFFICIAL') FROM sources")
    domains, official = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) FROM articles WHERE syndicated_of IS NOT NULL")
    syndicated = cursor.fetchone()[0]
    return domains or 0, official or 0, syndicated


def run(conn):
    """Bangun ulang registri sumber dan penanda sindikasi, lalu cetak ringkasan."""
    domains = rebuild_sources(conn)
    syndicated = mark_syndicated(conn)
    _, official, _ = summary(conn)
    print(
        f"\n[*] Registri sumber: {domains} domain ({official} resmi); "
        f"{syndicated} artikel ditandai sindikasi."
    )
