"""Ambil isi artikel penuh untuk artikel di sebuah file sampel/label evaluasi.

Dipakai agar skor evaluasi mencerminkan ekstraksi dengan isi artikel. Artikel
yang belum pernah diambil, atau yang statusnya ``unresolved``/``error``
(kegagalan sementara: pembuka tautan Google News dibatasi, jaringan), dicoba
lagi. Setelah ini, jalankan ``python main.py --no-crawl --no-fetch`` agar
V0.3 dan V0.4 mengekstrak ulang artikel tersebut, lalu ``python eval/score.py``.

Pemakaian: python eval/fetch_sample_content.py [eval/labels.csv] [--limit N]
``--limit`` membatasi jumlah artikel per pemanggilan (untuk dijalankan per potongan).
"""

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from csais import content_fetcher  # noqa: E402
from csais.db import get_connection  # noqa: E402
from csais.schema import ensure_content_columns  # noqa: E402

_ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
LABELS = _ARGS[0] if _ARGS else os.path.join("eval", "labels.csv")
LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
RETRY_STATUSES = ("unresolved", "error")


def main():
    with open(LABELS, newline="", encoding="utf-8") as fh:
        article_ids = [int(row["article_id"]) for row in csv.DictReader(fh)]

    conn = get_connection()
    ensure_content_columns(conn)
    marks = ",".join("?" for _ in article_ids)
    retry_marks = ",".join("?" for _ in RETRY_STATUSES)
    rows = conn.execute(
        f"SELECT article_id, article_url FROM articles "
        f"WHERE article_id IN ({marks}) "
        f"AND (content_fetched_at IS NULL OR content_status IN ({retry_marks}))",
        (*article_ids, *RETRY_STATUSES),
    ).fetchall()
    print(f"{len(rows)} dari {len(article_ids)} artikel di {LABELS} perlu diambil isinya.")
    if LIMIT is not None:
        rows = rows[:LIMIT]
        print(f"Dibatasi {len(rows)} artikel pada pemanggilan ini.")

    statuses = {}
    for number, (article_id, url) in enumerate(rows, start=1):
        status = content_fetcher.fetch_one(conn, article_id, url)
        statuses[status] = statuses.get(status, 0) + 1
        if number % 20 == 0 or number == len(rows):
            conn.commit()
            print(f"   {number}/{len(rows)} {statuses}", flush=True)
    conn.commit()
    conn.close()
    print("Selesai:", statuses)


if __name__ == "__main__":
    main()
