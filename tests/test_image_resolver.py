"""Pengujian csais/image_resolver.py: pemilihan incident dan artikel, tanpa jaringan."""

from datetime import datetime, timedelta, timezone

from csais import image_resolver as ir


def _setup(conn):
    conn.executescript(
        """
        CREATE TABLE articles (
            article_id INTEGER PRIMARY KEY, article_url TEXT, published_date TEXT
        );
        CREATE TABLE v05_incidents (
            incident_id TEXT PRIMARY KEY, document_count INTEGER,
            anchor_published_date TEXT, last_published_date TEXT
        );
        CREATE TABLE v05_incident_documents (incident_id TEXT, article_id INTEGER);
        """
    )
    ir.ensure_columns(conn)
    today = datetime.now(timezone.utc).date()
    recent = (today - timedelta(days=2)).isoformat()
    newer = (today - timedelta(days=1)).isoformat()
    old = (today - timedelta(days=400)).isoformat()
    conn.executemany(
        "INSERT INTO v05_incidents VALUES (?, ?, ?, ?)",
        [
            ("INC_A", 3, recent, recent),
            ("INC_B", 1, newer, newer),
            ("INC_OLD", 5, old, old),
            ("INC_HAS", 2, recent, recent),
        ],
    )
    conn.executemany(
        "INSERT INTO articles (article_id, article_url, published_date) VALUES (?, ?, ?)",
        [
            (1, "https://news.google.com/rss/articles/a1", recent),
            (2, "https://news.google.com/rss/articles/a2", recent),
            (3, "https://news.google.com/rss/articles/a3", recent),
            (4, "https://news.google.com/rss/articles/b1", newer),
            (5, "https://news.google.com/rss/articles/o1", old),
            (6, "https://news.google.com/rss/articles/h1", recent),
        ],
    )
    conn.execute("UPDATE articles SET resolved_url = 'https://media.id/a3' WHERE article_id = 3")
    conn.execute("UPDATE articles SET image_url = 'https://media.id/h.jpg' WHERE article_id = 6")
    conn.executemany(
        "INSERT INTO v05_incident_documents VALUES (?, ?)",
        [("INC_A", 1), ("INC_A", 2), ("INC_A", 3), ("INC_B", 4), ("INC_OLD", 5), ("INC_HAS", 6)],
    )
    conn.commit()


def test_pending_incidents_skips_old_and_already_illustrated(temp_conn):
    _setup(temp_conn)
    assert ir.pending_incidents(temp_conn, 10) == ["INC_B", "INC_A"]
    assert ir.pending_incidents(temp_conn, 1) == ["INC_B"]


def test_articles_to_try_prefers_resolved_urls(temp_conn):
    _setup(temp_conn)
    ids = [row[0] for row in ir.articles_to_try(temp_conn, "INC_A")]
    assert ids[0] == 3
    assert len(ids) == ir.MAX_TRIES


def test_resolve_images_stops_at_first_image_and_records_status(temp_conn):
    _setup(temp_conn)
    fetched = []

    def resolve(url):
        return None if url.endswith("b1") else url.replace("news.google.com/rss/articles", "media.id")

    def fetch(url):
        fetched.append(url)
        return ("ok", "https://media.id/foto.jpg") if url.endswith("a3") else ("none", None)

    found, statuses, total = ir.resolve_images(temp_conn, 10, resolve, fetch, log=lambda *_: None)
    assert (found, total) == (1, 2)
    assert statuses == {"unresolved": 1, "ok": 1}
    assert fetched == ["https://media.id/a3"]  # URL media yang sudah ada tidak di-resolve ulang
    rows = dict(temp_conn.execute("SELECT article_id, image_status FROM articles WHERE image_status IS NOT NULL"))
    assert rows == {3: "ok", 4: "unresolved"}
    assert temp_conn.execute("SELECT image_url FROM articles WHERE article_id = 3").fetchone()[0] == "https://media.id/foto.jpg"
    # INC_A sudah bergambar; INC_B baru dicoba ulang setelah RETRY_AFTER_DAYS
    assert ir.pending_incidents(temp_conn, 10) == []


def test_try_article_saves_resolved_url_without_overwriting(temp_conn):
    _setup(temp_conn)
    status = ir.try_article(
        temp_conn, 1, "https://news.google.com/rss/articles/a1", None,
        resolve=lambda url: "https://media.id/a1", fetch=lambda url: ("blocked", None),
    )
    assert status == "blocked"
    row = temp_conn.execute("SELECT resolved_url, image_url, image_status FROM articles WHERE article_id = 1").fetchone()
    assert row == ("https://media.id/a1", None, "blocked")
