"""Pengujian csais/crawler.py tanpa jaringan: utilitas teks/tanggal, URL, periode, checkpoint."""

from datetime import datetime, timezone

import pytest

from csais import crawler
from csais.db import get_connection

UTC = timezone.utc


def test_clean_text_strips_html_and_entities():
    assert crawler.clean_text("<p>Hello &amp; <b>world</b>&nbsp;  now</p>") == "Hello & world now"
    assert crawler.clean_text("") == ""
    assert crawler.clean_text(None) == ""


def test_generate_content_hash_is_sha256_and_sensitive_to_input():
    digest = crawler.generate_content_hash("t", "s", "u")
    assert len(digest) == 64
    int(digest, 16)
    assert digest == crawler.generate_content_hash("t", "s", "u")
    assert digest != crawler.generate_content_hash("t", "s", "u2")


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Mon, 06 Jan 2025 10:00:00 +0700", "2025-01-06T03:00:00+00:00"),
        ("Mon, 06 Jan 2025 10:00:00 GMT", "2025-01-06T10:00:00+00:00"),
        ("Mon, 06 Jan 2025 10:00:00 -0500", "2025-01-06T15:00:00+00:00"),
        ("not a date", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_date_rfc2822_to_iso_utc(value, expected):
    assert crawler.parse_date(value) == expected


def test_build_google_news_url_quotes_keyword():
    url = crawler.build_google_news_url(
        "cyber attack", datetime(2025, 1, 1, tzinfo=UTC), datetime(2025, 1, 31, tzinfo=UTC), "en"
    )
    assert url.startswith("https://news.google.com/rss/search?q=")
    assert "q=%22cyber+attack%22+after%3A2025-01-01+before%3A2025-01-31" in url
    assert url.endswith("&hl=en-US&gl=US&ceid=US:en")


def test_build_google_news_url_site_query_is_unquoted():
    url = crawler.build_google_news_url(
        "site:bssn.go.id", datetime(2025, 1, 1, tzinfo=UTC), datetime(2025, 1, 31, tzinfo=UTC), "id"
    )
    assert "q=site%3Abssn.go.id+after%3A2025-01-01+before%3A2025-01-31" in url
    assert "%22" not in url
    assert url.endswith("&hl=id-ID&gl=ID&ceid=ID:id")


def test_build_google_news_url_bumps_end_date_when_equal_to_start():
    url = crawler.build_google_news_url(
        "x", datetime(2025, 1, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC), "en"
    )
    assert "after%3A2025-01-01+before%3A2025-01-02" in url


def test_build_google_news_url_unknown_language_defaults_to_english():
    url = crawler.build_google_news_url(
        "x", datetime(2025, 1, 1, tzinfo=UTC), datetime(2025, 1, 2, tzinfo=UTC), "xx"
    )
    assert url.endswith("&hl=en-US&gl=US&ceid=US:en")


def test_full_historical_periods_with_fixed_today():
    periods = crawler.full_historical_periods(today=datetime(2025, 3, 15, tzinfo=UTC))
    assert periods == [
        (datetime(2025, 1, 1, tzinfo=UTC), datetime(2025, 1, 31, tzinfo=UTC)),
        (datetime(2025, 1, 31, tzinfo=UTC), datetime(2025, 3, 2, tzinfo=UTC)),
    ]
    assert all((end - start).days == crawler.HISTORICAL_PERIOD_DAYS for start, end in periods)
    assert crawler.full_historical_periods(today=crawler.START_DATE) == []
    # periode yang berakhir tepat hari ini sudah dianggap penuh
    assert len(crawler.full_historical_periods(today=datetime(2025, 1, 31, tzinfo=UTC))) == 1


def test_all_crawl_tasks_includes_official_sources():
    tasks = crawler.all_crawl_tasks()
    assert ("id", "site:bssn.go.id", "BSSN", "OFFICIAL") in tasks

    official = [task for task in tasks if task[3] == "OFFICIAL"]
    assert len(official) == sum(len(queries) for queries in crawler.OFFICIAL_SOURCES.values())
    assert all(task[1].startswith("site:") for task in official)
    assert all(task[0] == crawler.OFFICIAL_SOURCE_LANGUAGE for task in official)

    rss = [task for task in tasks if task[3] == "RSS"]
    assert len(rss) == sum(len(keywords) for keywords in crawler.MULTILINGUAL_KEYWORDS.values())
    assert all(task[2] == "Google News" for task in rss)
    assert len(tasks) == len(rss) + len(official)


def test_crawl_state_checkpoint_roundtrip(fresh_db):
    crawler.initialize_database()
    key = (
        "historical", "en", "cyber attack",
        "2025-01-01T00:00:00+00:00", "2025-01-31T00:00:00+00:00",
    )
    assert crawler.is_period_completed(*key) is False
    crawler.save_crawl_state(*key, "IN_PROGRESS")
    assert crawler.is_period_completed(*key) is False
    crawler.save_crawl_state(*key, "COMPLETED")
    assert crawler.is_period_completed(*key) is True

    conn = get_connection()
    rows = conn.execute("SELECT status, completed_at FROM crawl_state").fetchall()
    conn.close()
    assert len(rows) == 1  # upsert, bukan baris baru
    assert rows[0][0] == "COMPLETED"
    assert rows[0][1]


def test_initialize_database_clears_stale_in_progress(fresh_db, capsys):
    crawler.initialize_database()
    key = (
        "historical", "en", "malware",
        "2025-01-01T00:00:00+00:00", "2025-01-31T00:00:00+00:00",
    )
    crawler.save_crawl_state(*key, "IN_PROGRESS")
    crawler.initialize_database()
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM crawl_state").fetchone()[0]
    conn.close()
    assert count == 0
    assert "IN_PROGRESS" in capsys.readouterr().out


def test_initialize_database_creates_tables_and_uid_column(fresh_db):
    crawler.initialize_database()
    conn = get_connection()
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    columns = {row[1] for row in conn.execute("PRAGMA table_info(articles)")}
    conn.close()
    assert {"articles", "crawl_state", "pipeline_runs"} <= tables
    assert "article_uid" in columns
