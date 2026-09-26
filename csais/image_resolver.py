"""Gambar incident: satu gambar utama (og:image) untuk setiap incident terbaru.

Hampir semua artikel masih berupa tautan Google News tanpa URL media asli,
sehingga web tidak punya gambar untuk daftar incident. Tahap ini memilih
incident terbaru yang belum punya gambar (liputan terluas dulu, sama dengan
urutan daftar incident di web), lalu mencoba artikelnya satu per satu: buka
tautan Google News menjadi URL media, baca bagian awal halaman, dan ambil
og:image. Berhenti pada artikel pertama yang
gambarnya berhasil ditarik. URL media yang ditemukan ikut disimpan, sehingga
registri sumber dan domain bukti juga bertambah.

Setiap artikel yang dicoba diberi articles.image_status (ok, none, unresolved,
robots, blocked, error) agar tidak dicoba ulang setiap hari; status error dan
unresolved dicoba lagi setelah RETRY_AFTER_DAYS.
"""

from datetime import datetime, timedelta, timezone

import requests

from csais import sources
from csais.content_fetcher import (
    REQUEST_TIMEOUT,
    USER_AGENT,
    extract_image_url,
    polite_delay,
    resolve_google_news_url,
    robots_allows,
)
from csais.db import get_connection, get_timestamp
from csais.schema import ensure_column, ensure_content_columns, record_run

DEFAULT_BUDGET = 120  # incident per run; menjaga menit GitHub Actions
MAX_TRIES = 2  # artikel yang dicoba per incident per run
LOOKBACK_DAYS = 60
HEAD_BYTES = 400_000  # og:image selalu ada di <head>; tidak perlu seluruh halaman
RETRY_AFTER_DAYS = 7
RETRY_STATUSES = ("error", "unresolved")


def ensure_columns(conn):
    """Kolom gambar pada tabel articles."""
    ensure_content_columns(conn)  # termasuk image_url dan resolved_url
    ensure_column(conn, "articles", "image_status", "TEXT")
    ensure_column(conn, "articles", "image_checked_at", "TEXT")


def _retry_cutoff():
    return (datetime.now(timezone.utc) - timedelta(days=RETRY_AFTER_DAYS)).isoformat()


def pending_incidents(conn, budget):
    """Incident terbaru tanpa gambar yang masih punya artikel untuk dicoba."""
    cutoff = _retry_cutoff()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT i.incident_id
        FROM v05_incidents i
        WHERE i.anchor_published_date >= date('now', ?)
          AND NOT EXISTS (
              SELECT 1 FROM v05_incident_documents d
              JOIN articles a ON a.article_id = d.article_id
              WHERE d.incident_id = i.incident_id AND a.image_url IS NOT NULL
          )
          AND EXISTS (
              SELECT 1 FROM v05_incident_documents d
              JOIN articles a ON a.article_id = d.article_id
              WHERE d.incident_id = i.incident_id
                AND (a.image_status IS NULL
                     OR (a.image_status IN (?, ?) AND a.image_checked_at < ?))
          )
        ORDER BY i.document_count DESC, i.last_published_date DESC
        LIMIT ?
        """,
        (f"-{LOOKBACK_DAYS} days", *RETRY_STATUSES, cutoff, budget),
    )
    return [row[0] for row in cursor.fetchall()]


def articles_to_try(conn, incident_id, limit=MAX_TRIES):
    """Artikel incident yang belum dicoba; yang sudah punya URL media asli didahulukan."""
    cutoff = _retry_cutoff()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT a.article_id, a.article_url, a.resolved_url
        FROM v05_incident_documents d
        JOIN articles a ON a.article_id = d.article_id
        WHERE d.incident_id = ?
          AND (a.image_status IS NULL
               OR (a.image_status IN (?, ?) AND a.image_checked_at < ?))
        ORDER BY (a.resolved_url IS NULL), a.published_date DESC
        LIMIT ?
        """,
        (incident_id, *RETRY_STATUSES, cutoff, limit),
    )
    return cursor.fetchall()


def fetch_image(url):
    """(status, url gambar) dari bagian awal halaman media."""
    if not robots_allows(url):
        return "robots", None
    polite_delay(url)
    try:
        with requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
            timeout=REQUEST_TIMEOUT,
            stream=True,
        ) as response:
            if response.status_code in (401, 403, 429, 451):
                return "blocked", None
            if response.status_code >= 400:
                return "error", None
            head = b""
            for chunk in response.iter_content(32_768):
                head += chunk
                if len(head) >= HEAD_BYTES or b"</head>" in head:
                    break
            html = head.decode(response.encoding or "utf-8", errors="replace")
            image = extract_image_url(html, response.url or url)
    except requests.RequestException:
        return "error", None
    return ("ok", image) if image else ("none", None)


def try_article(conn, article_id, article_url, resolved_url, resolve=resolve_google_news_url, fetch=fetch_image):
    """Coba satu artikel, simpan hasilnya; kembalikan status."""
    url = resolved_url
    if not url or "news.google." in url:
        url = resolve(article_url)
    image = None
    if not url or "news.google." in url:
        status = "unresolved"
        url = None
    else:
        status, image = fetch(url)
    conn.execute(
        """
        UPDATE articles
        SET image_status = ?, image_checked_at = ?,
            image_url = COALESCE(?, image_url),
            resolved_url = COALESCE(resolved_url, ?)
        WHERE article_id = ?
        """,
        (status, get_timestamp(), image, url, article_id),
    )
    conn.commit()
    return status


def resolve_images(conn, budget=DEFAULT_BUDGET, resolve=resolve_google_news_url, fetch=fetch_image, log=print):
    """Cari gambar untuk maksimal ``budget`` incident; kembalikan (incident dengan gambar, status per artikel)."""
    ensure_columns(conn)
    found = 0
    statuses = {}
    incidents = pending_incidents(conn, budget)
    for number, incident_id in enumerate(incidents, start=1):
        for article_id, article_url, resolved_url in articles_to_try(conn, incident_id):
            status = try_article(conn, article_id, article_url, resolved_url, resolve, fetch)
            statuses[status] = statuses.get(status, 0) + 1
            if status == "ok":
                found += 1
                break
        if number % 20 == 0 or number == len(incidents):
            log(f"   {number}/{len(incidents)} incident: {found} bergambar, {statuses}")
    return found, statuses, len(incidents)


def run(budget=DEFAULT_BUDGET):
    """Titik masuk pipeline: gambar untuk incident terbaru."""
    print("\n==================================================")
    print("   IMAGE - GAMBAR INCIDENT")
    print("==================================================")
    started_at = get_timestamp()
    conn = get_connection()
    try:
        found, statuses, total = resolve_images(conn, budget)
        record_run(conn, "image_resolver", started_at, total, str(statuses))
        if statuses:
            sources.run(conn)  # URL media baru memperbarui registri sumber
    finally:
        conn.close()
    print(f"\nIncident dicoba   : {total}")
    print(f"Mendapat gambar   : {found}")
    print(f"Status per artikel: {statuses}")
    print("==================================================")
