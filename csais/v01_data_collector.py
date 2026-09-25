"""V0.1 - Ringkasan data hasil crawl.

Menampilkan jumlah artikel, distribusi bahasa, dan beberapa artikel terawal
sebagai contoh, tanpa memuat seluruh tabel ke memori.
"""

from csais.config import DATABASE_FILE
from csais.db import get_connection

SAMPLE_SIZE = 20


def database_summary():
    """Jumlah artikel dan distribusi bahasa."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM articles")
    total = cursor.fetchone()[0]
    cursor.execute("""
        SELECT language, COUNT(*)
        FROM articles
        GROUP BY language
        ORDER BY COUNT(*) DESC
        """)
    languages = cursor.fetchall()
    conn.close()
    return total, languages


def sample_articles(limit=SAMPLE_SIZE):
    """Beberapa artikel terawal berdasarkan tanggal terbit."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT title, language, published_date, source_name, article_url
        FROM articles
        ORDER BY published_date ASC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def run():
    """Tampilkan ringkasan database dan contoh data."""
    print("\n==================================================")
    print("   V0.1 - CYBER SOCIAL ATTACK DATA PROCESSING")
    print("==================================================")

    total, languages = database_summary()
    print(f"\nData dibaca dari database : {DATABASE_FILE}")
    print(f"Total data tersedia : {total}")

    print("\nDistribusi bahasa:")
    for language, count in languages:
        print(f"   {language}: {count}")

    print("\n==================================================")
    print("SAMPLE DATA")
    print("==================================================")
    samples = sample_articles()
    for index, (title, language, published, source, url) in enumerate(samples, 1):
        print(f"\n{index}. {title}")
        print(f"   Language : {language}")
        print(f"   Published: {published}")
        print(f"   Source   : {source}")
        print(f"   URL      : {url}")

    print("\n==================================================")
    print("V0.1 PROCESSING SELESAI")
    print("==================================================")
