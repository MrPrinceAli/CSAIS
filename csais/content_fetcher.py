"""Pengambilan isi artikel penuh dari halaman media aslinya.

Tautan di ``articles.article_url`` adalah tautan redirect Google News. Modul
ini membukanya menjadi URL media asli (pustaka ``googlenewsdecoder``),
mengambil halamannya dengan ``requests`` memakai user agent riset dan jeda
antar permintaan (menghormati robots.txt), lalu mengekstrak teks utamanya
dengan ``trafilatura``.

Hasil disimpan di tabel ``articles``:
  content            teks utama artikel (dipotong MAX_CONTENT_CHARS)
  resolved_url       URL media asli
  content_status     ok | unresolved | blocked | robots | empty | error
  content_sha256     SHA-256 teks (untuk ledger bukti)
  content_fetched_at waktu pengambilan

Hanya artikel kandidat V0.2 (RELEVANT lalu UNCERTAIN, terbaru lebih dulu)
yang diambil, dengan anggaran per run agar cocok untuk pekerja terjadwal.
Artikel yang gagal sementara (``error`` jaringan, atau ``unresolved`` karena
pembuka tautan Google News dibatasi) dicoba lagi setelah RETRY_AFTER_DAYS.
"""

import hashlib
import random
import time
from datetime import datetime, timedelta, timezone
from urllib import robotparser
from urllib.parse import urlparse

import requests
import trafilatura
from googlenewsdecoder import gnewsdecoder

from csais import sources
from csais.db import get_connection, get_timestamp
from csais.schema import ensure_content_columns, record_run

# --- Konfigurasi ---
DEFAULT_BUDGET = 300
REQUEST_TIMEOUT = 20
DELAY_MIN = 1.0
DELAY_MAX = 3.0
SAME_DOMAIN_GAP = 3.0  # detik minimum antara dua permintaan ke domain yang sama
DECODE_INTERVAL = 1  # jeda internal googlenewsdecoder (detik)
MAX_CONTENT_CHARS = 20000
MIN_CONTENT_CHARS = 200
RETRY_AFTER_DAYS = 7
USER_AGENT = "CSAIS-Research-Crawler/0.1 (Cyber Social Attack Intelligence System)"
BLOCKED_MARKERS = ("enable javascript and cookies", "access denied", "just a moment")

_robots_cache = {}
_last_request_at = {}


# --- Utilitas ---
def domain_of(url):
    """Nama host tanpa awalan www., huruf kecil."""
    host = (urlparse(url).netloc or "").lower()
    return host[4:] if host.startswith("www.") else host


def robots_allows(url):
    """Cek robots.txt domain (di-cache); bila tidak bisa dibaca, dianggap boleh."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    parser = _robots_cache.get(base)
    if parser is None:
        parser = robotparser.RobotFileParser()
        try:
            response = requests.get(
                f"{base}/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=10
            )
            parser.parse(response.text.splitlines() if response.ok else [])
        except requests.RequestException:
            parser.parse([])
        _robots_cache[base] = parser
    return parser.can_fetch(USER_AGENT, url)


def polite_delay(url):
    """Jeda acak, plus jeda tambahan bila domain yang sama baru saja diakses."""
    domain = domain_of(url)
    wait = random.uniform(DELAY_MIN, DELAY_MAX)
    last = _last_request_at.get(domain)
    if last is not None:
        wait = max(wait, SAME_DOMAIN_GAP - (time.time() - last))
    if wait > 0:
        time.sleep(wait)
    _last_request_at[domain] = time.time()


def resolve_google_news_url(url):
    """URL media asli dari tautan Google News; None bila gagal."""
    if "news.google.com" not in url:
        return url
    try:
        result = gnewsdecoder(url, interval=DECODE_INTERVAL)
    except Exception:
        return None
    if result.get("success") and result.get("decoded_url"):
        return result["decoded_url"]
    return None


def fetch_article_text(url):
    """(status, teks) untuk satu URL media."""
    if not robots_allows(url):
        return "robots", None
    polite_delay(url)
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en,id;q=0.8"},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException:
        return "error", None
    if response.status_code in (401, 403, 429, 451):
        return "blocked", None
    if response.status_code >= 400:
        return "error", None
    html = response.text
    text = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
    text = text.strip()
    if any(marker in text.lower()[:200] for marker in BLOCKED_MARKERS):
        return "blocked", None
    if len(text) < MIN_CONTENT_CHARS:
        return "empty", None
    return "ok", text[:MAX_CONTENT_CHARS]


# --- Database ---
def get_pending(conn, budget):
    """Artikel kandidat yang belum diambil, RELEVANT dulu, terbaru dulu."""
    retry_before = (datetime.now(timezone.utc) - timedelta(days=RETRY_AFTER_DAYS)).isoformat()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT a.article_id, a.article_url
        FROM articles a
        JOIN v02_relevance r ON r.article_id = a.article_id
        WHERE r.relevance_label IN ('RELEVANT', 'UNCERTAIN')
          AND (
              a.content_fetched_at IS NULL
              OR (a.content_status IN ('error', 'unresolved') AND a.content_fetched_at < ?)
          )
        ORDER BY CASE r.relevance_label WHEN 'RELEVANT' THEN 0 ELSE 1 END,
                 a.published_date DESC
        LIMIT ?
        """,
        (retry_before, budget),
    )
    return cursor.fetchall()


def save_result(conn, article_id, resolved_url, status, text):
    """Simpan hasil pengambilan satu artikel."""
    sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None
    conn.execute(
        """
        UPDATE articles
        SET content = ?, resolved_url = ?, content_status = ?,
            content_sha256 = ?, content_fetched_at = ?
        WHERE article_id = ?
        """,
        (text, resolved_url, status, sha256, get_timestamp(), article_id),
    )


def fetch_one(conn, article_id, article_url):
    """Buka tautan, ambil teks, simpan; kembalikan status."""
    resolved_url = resolve_google_news_url(article_url)
    if resolved_url is None:
        save_result(conn, article_id, None, "unresolved", None)
        return "unresolved"
    status, text = fetch_article_text(resolved_url)
    save_result(conn, article_id, resolved_url, status, text)
    return status


def content_summary(conn):
    """Jumlah artikel per content_status, plus jumlah kandidat yang belum diambil."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COALESCE(content_status, 'belum'), COUNT(*) FROM articles GROUP BY 1"
    )
    counts = dict(cursor.fetchall())
    cursor.execute(
        """
        SELECT COUNT(*) FROM articles a JOIN v02_relevance r USING (article_id)
        WHERE r.relevance_label IN ('RELEVANT', 'UNCERTAIN')
          AND a.content_fetched_at IS NULL
        """
    )
    pending = cursor.fetchone()[0]
    return counts, pending


# --- Program utama ---
def run(budget=DEFAULT_BUDGET):
    """Ambil isi artikel untuk maksimal ``budget`` kandidat yang belum diambil."""
    print("\n==================================================")
    print("   CONTENT FETCH - ISI ARTIKEL PENUH")
    print("==================================================")

    started_at = get_timestamp()
    conn = get_connection()
    ensure_content_columns(conn)

    counts, pending = content_summary(conn)
    print(f"\nKandidat belum diambil : {pending}")
    print(f"Anggaran run ini       : {budget}")

    rows = get_pending(conn, budget)
    statuses = {}
    try:
        for number, (article_id, article_url) in enumerate(rows, start=1):
            status = fetch_one(conn, article_id, article_url)
            statuses[status] = statuses.get(status, 0) + 1
            # Commit per artikel: kunci tulis tidak ditahan selama menunggu
            # jaringan, sehingga proses lain (misalnya pengambilan sampel
            # evaluasi) bisa menulis bergantian dan kegagalan tidak membuang hasil.
            conn.commit()
            if number % 25 == 0 or number == len(rows):
                print(f"   {number}/{len(rows)} diproses: {statuses}")
    except KeyboardInterrupt:
        conn.commit()
        print("\n\n⚠️ Content fetch dihentikan oleh user; hasil sejauh ini tersimpan.")
    finally:
        conn.commit()

    counts, pending = content_summary(conn)
    record_run(conn, "content_fetch", started_at, len(rows), str(statuses))
    # URL asli yang baru diketahui memperbarui registri sumber
    sources.run(conn)
    conn.close()

    print("\n==================================================")
    print("   CONTENT FETCH SUMMARY")
    print("==================================================")
    print(f"Diproses run ini    : {len(rows)}  {statuses}")
    for status in ("ok", "empty", "blocked", "unresolved", "robots", "error"):
        if status in counts:
            print(f"Total {status:11s}: {counts[status]}")
    print(f"Kandidat tersisa    : {pending}")
    print("==================================================")


if __name__ == "__main__":
    run()
