"""Penghapusan hasil olahan V0.2 - V0.6 agar pipeline memproses ulang dari awal.

Tabel hasil crawl (``articles`` dan ``crawl_state``) tidak disentuh.
"""

from csais.db import get_connection

DERIVED_TABLES = [
    "v02_relevance",
    "v03_information_extraction",
    "v04_entities",
    "v04_entity_mentions",
    "v04_processed_articles",
    "v05_incidents",
    "v05_incident_documents",
    "v05_processed_articles",
    "v06_evidence",
    "v06_source_relations",
    "v06_processed_incidents",
]


def derived_table_counts(conn):
    """Jumlah baris tiap tabel hasil olahan yang ada di database."""
    cursor = conn.cursor()
    counts = {}
    for table in DERIVED_TABLES:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        )
        if cursor.fetchone() is None:
            continue
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        counts[table] = cursor.fetchone()[0]
    return counts


def reset_derived_tables(confirm=True):
    """Hapus tabel V0.2 - V0.6. Bila ``confirm``, minta persetujuan lewat prompt."""
    conn = get_connection()
    counts = derived_table_counts(conn)
    if not counts:
        print("\nTidak ada tabel hasil olahan yang perlu dihapus.")
        conn.close()
        return False

    print("\nTabel hasil olahan yang akan dihapus (articles dan crawl_state aman):")
    for table, count in counts.items():
        print(f"   {table:32s} {count} baris")
    if confirm:
        answer = input("Hapus semua tabel di atas dan proses ulang? (y/n): ")
        if answer.strip().lower() != "y":
            print("Dibatalkan.")
            conn.close()
            return False

    cursor = conn.cursor()
    for table in counts:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    print("Tabel hasil olahan dihapus. Pipeline akan memproses ulang dari V0.2.")
    return True
