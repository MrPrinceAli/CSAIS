# ============================================================
# V0.1 - CYBER SOCIAL ATTACK DATA COLLECTOR
# ============================================================

import sqlite3


# ============================================================
# KONFIGURASI DATABASE
# ============================================================

DATABASE_FILE = (
    "database/csais.db"
)


# ============================================================
# LOAD DATA FROM DATABASE
# ============================================================

def load_articles():

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM articles
        ORDER BY published_date ASC
        """
    )

    articles = cursor.fetchall()

    connection.close()

    return articles


# ============================================================
# DATABASE SUMMARY
# ============================================================

def database_summary():

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

    cursor.execute(
        """
        SELECT language, COUNT(*)
        FROM articles
        GROUP BY language
        ORDER BY COUNT(*) DESC
        """
    )

    languages = cursor.fetchall()

    connection.close()

    return total, languages


# ============================================================
# V0.1 PROCESSING
# ============================================================

def run():

    print("\n==================================================")
    print("   V0.1 - CYBER SOCIAL ATTACK DATA PROCESSING")
    print("==================================================")

    # --------------------------------------------------------
    # LOAD DATABASE
    # --------------------------------------------------------

    articles = load_articles()

    print(
        f"\nData dibaca dari database : "
        f"{DATABASE_FILE}"
    )

    print(
        f"Total data tersedia : "
        f"{len(articles)}"
    )

    # --------------------------------------------------------
    # DATABASE SUMMARY
    # --------------------------------------------------------

    total, languages = database_summary()

    print("\nDistribusi bahasa:")

    for language, count in languages:

        print(
            f"   {language}: "
            f"{count}"
        )

    # --------------------------------------------------------
    # SAMPLE DATA
    # --------------------------------------------------------

    print("\n==================================================")
    print("SAMPLE DATA")
    print("==================================================")

    for index, article in enumerate(
        articles[:20],
        start=1
    ):

        print(
            f"\n{index}. "
            f"{article['title']}"
        )

        print(
            f"   Language : "
            f"{article['language']}"
        )

        print(
            f"   Published: "
            f"{article['published_date']}"
        )

        print(
            f"   Source   : "
            f"{article['source_name']}"
        )

        print(
            f"   URL      : "
            f"{article['article_url']}"
        )

    print("\n==================================================")
    print("V0.1 PROCESSING SELESAI")
    print("==================================================")

    return articles