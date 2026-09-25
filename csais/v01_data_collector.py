"""V0.1 - Ringkasan data hasil crawl.

Membaca seluruh artikel dari database, lalu menampilkan jumlah total,
distribusi bahasa, dan 20 artikel pertama sebagai contoh.
"""

import sqlite3

from csais.config import DATABASE_FILE
from csais.db import get_connection


def load_articles():
    """Ambil seluruh artikel, diurutkan berdasarkan tanggal terbit."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    articles = conn.execute(
        "SELECT * FROM articles ORDER BY published_date ASC"
    ).fetchall()
    conn.close()
    return articles


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


def run():
    """Tampilkan ringkasan database dan contoh data."""
    print("\n==================================================")
    print("   V0.1 - CYBER SOCIAL ATTACK DATA PROCESSING")
    print("==================================================")

    articles = load_articles()
    print(f"\nData dibaca dari database : {DATABASE_FILE}")
    print(f"Total data tersedia : {len(articles)}")

    total, languages = database_summary()
    print("\nDistribusi bahasa:")
    for language, count in languages:
        print(f"   {language}: {count}")

    print("\n==================================================")
    print("SAMPLE DATA")
    print("==================================================")
    for index, article in enumerate(articles[:20], start=1):
        print(f"\n{index}. {article['title']}")
        print(f"   Language : {article['language']}")
        print(f"   Published: {article['published_date']}")
        print(f"   Source   : {article['source_name']}")
        print(f"   URL      : {article['article_url']}")

    print("\n==================================================")
    print("V0.1 PROCESSING SELESAI")
    print("==================================================")
