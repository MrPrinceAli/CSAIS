"""Ambil isi artikel penuh untuk artikel di eval/labels.csv yang belum diambil.

Dipakai agar skor evaluasi mencerminkan ekstraksi dengan isi artikel. Setelah
ini, jalankan ``python main.py --no-crawl --no-fetch`` agar V0.3 dan V0.4
mengekstrak ulang artikel tersebut, lalu ``python eval/score.py``.

Pemakaian: python eval/fetch_sample_content.py [eval/labels.csv]
"""

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from csais import content_fetcher  # noqa: E402
from csais.db import get_connection  # noqa: E402
from csais.schema import ensure_content_columns  # noqa: E402

LABELS = sys.argv[1] if len(sys.argv) > 1 else os.path.join("eval", "labels.csv")


def main():
    with open(LABELS, newline="", encoding="utf-8") as fh:
        article_ids = [int(row["article_id"]) for row in csv.DictReader(fh)]

    conn = get_connection()
    ensure_content_columns(conn)
    marks = ",".join("?" for _ in article_ids)
    rows = conn.execute(
        f"SELECT article_id, article_url FROM articles "
        f"WHERE article_id IN ({marks}) AND content_fetched_at IS NULL",
        article_ids,
    ).fetchall()
    print(f"{len(rows)} dari {len(article_ids)} artikel sampel belum diambil isinya.")

    statuses = {}
    for number, (article_id, url) in enumerate(rows, start=1):
        status = content_fetcher.fetch_one(conn, article_id, url)
        statuses[status] = statuses.get(status, 0) + 1
        if number % 20 == 0 or number == len(rows):
            conn.commit()
            print(f"   {number}/{len(rows)} {statuses}")
    conn.commit()
    conn.close()
    print("Selesai:", statuses)


if __name__ == "__main__":
    main()
