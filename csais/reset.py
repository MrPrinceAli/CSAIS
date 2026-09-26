"""Penghapusan hasil olahan agar pipeline memproses ulang dari tahap tertentu.

Tabel hasil crawl (``articles`` dan ``crawl_state``) tidak disentuh. Karena
setiap tahap dibangun dari tahap sebelumnya, menghapus tahap N berarti
menghapus tahap N sampai V0.7. Tabel ledger (``evidence_batches`` dan
``evidence_leaves``) juga tidak pernah dihapus: batch Merkle bersifat
tambah-saja dan akar yang sudah dijangkarkan tidak boleh hilang.
"""

from csais.db import get_connection

STAGE_TABLES = {
    2: ["v02_relevance"],
    3: ["v03_information_extraction"],
    4: ["v04_entities", "v04_entity_mentions", "v04_processed_articles"],
    5: ["v05_incidents", "v05_incident_documents", "v05_processed_articles"],
    6: ["v06_evidence", "v06_source_relations", "v06_processed_incidents"],
    7: ["v07_trust"],
}
LAST_STAGE = max(STAGE_TABLES)


def tables_from_stage(stage):
    """Daftar tabel hasil olahan dari tahap ``stage`` sampai tahap terakhir."""
    if stage not in STAGE_TABLES:
        raise ValueError(f"Tahap tidak dikenal: {stage} (pilih 2 sampai {LAST_STAGE})")
    return [table for s in sorted(STAGE_TABLES) if s >= stage for table in STAGE_TABLES[s]]


def table_counts(conn, tables):
    """Jumlah baris tiap tabel yang ada di database."""
    cursor = conn.cursor()
    counts = {}
    for table in tables:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        )
        if cursor.fetchone() is None:
            continue
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        counts[table] = cursor.fetchone()[0]
    return counts


def reset_derived_tables(confirm=True, from_stage=2):
    """Hapus tabel hasil tahap ``from_stage`` sampai tahap terakhir, dengan konfirmasi."""
    conn = get_connection()
    counts = table_counts(conn, tables_from_stage(from_stage))
    if not counts:
        print("\nTidak ada tabel hasil olahan yang perlu dihapus.")
        conn.close()
        return False

    print(
        f"\nTabel hasil V0.{from_stage} - V0.{LAST_STAGE} yang akan dihapus "
        "(articles, crawl_state, dan ledger aman):"
    )
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
    print(f"Tabel dihapus. Pipeline akan memproses ulang mulai V0.{from_stage}.")
    return True
