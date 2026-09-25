"""Ambil sampel artikel berstrata untuk dilabeli manual.

Sampel deterministik: N artikel per label V0.2 (RELEVANT, UNCERTAIN,
NOT_RELEVANT) untuk satu bahasa. Kolom ``label_*`` dibiarkan kosong untuk
diisi pelabel.

Pemakaian:
  python eval/make_sample.py                       # 100/label, en+id, eval/sample.csv
  python eval/make_sample.py --language id --per-label 50 --output eval/sample_id.csv

Sampel bahasa Inggris (default) memakai filter dan urutan yang sama seperti
saat eval/labels.csv dibuat, sehingga hasilnya tetap sama. Sampel bahasa lain
memakai urutan acak deterministik (hash article_id) agar tidak terpaku pada
satu periode crawl.
"""

import argparse
import csv
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from csais.config import DATABASE_FILE  # noqa: E402

FIELDS = [
    "article_id", "language", "v02_label", "v02_score", "title", "summary", "url",
    "v03_attack_type", "v03_target", "v03_threat_actor",
    "label_relevant", "label_target", "label_actor", "label_notes",
]


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("output", nargs="?", default=None, help="file CSV keluaran")
    parser.add_argument("--language", default=None, help="kode bahasa, misalnya id")
    parser.add_argument("--per-label", type=int, default=100, help="artikel per label V0.2")
    parser.add_argument("--output", dest="output_opt", default=None)
    args = parser.parse_args()
    args.output = args.output_opt or args.output or os.path.join(
        "eval", f"sample_{args.language}.csv" if args.language else "sample.csv"
    )
    return args


def main():
    args = parse_args()
    if args.language:
        languages, where, order = ((args.language,), "", "(a.article_id * 7919) % 10007")
    else:  # filter dan urutan asli sampel bahasa Inggris
        languages, where, order = (("en", "id"), "AND a.article_id % 7 = 3", "a.article_id")
    marks = ",".join("?" for _ in languages)

    conn = sqlite3.connect(f"file:{DATABASE_FILE}?mode=ro", uri=True)
    rows = []
    for label in ("RELEVANT", "UNCERTAIN", "NOT_RELEVANT"):
        cursor = conn.execute(
            f"""
            SELECT a.article_id, a.language, r.relevance_label, r.relevance_score,
                   a.title, a.summary, a.article_url,
                   x.attack_type, x.target, x.threat_actor
            FROM articles a
            JOIN v02_relevance r USING (article_id)
            LEFT JOIN v03_information_extraction x USING (article_id)
            WHERE r.relevance_label = ? AND a.language IN ({marks}) {where}
            ORDER BY {order}
            LIMIT ?
            """,
            (label, *languages, args.per_label),
        )
        rows.extend(cursor.fetchall())
    conn.close()

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(FIELDS)
        for row in rows:
            (
                article_id, language, v02_label, v02_score, title, summary, url,
                attack_type, target, actor,
            ) = row
            writer.writerow([
                article_id, language, v02_label, round(v02_score or 0, 2), title,
                (summary or "")[:400], url, attack_type or "", target or "", actor or "",
                "", "", "", "",
            ])
    print(f"{len(rows)} artikel ditulis ke {args.output}")


if __name__ == "__main__":
    main()
