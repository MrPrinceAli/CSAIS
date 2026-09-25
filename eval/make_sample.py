"""Ambil sampel artikel berstrata untuk dilabeli manual.

Sampel deterministik (berdasarkan article_id), 100 artikel per label V0.2
(RELEVANT, UNCERTAIN, NOT_RELEVANT), hanya bahasa Inggris dan Indonesia.
Kolom ``label_*`` dibiarkan kosong untuk diisi pelabel.

Pemakaian: python eval/make_sample.py [eval/sample.csv]
"""

import csv
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from csais.config import DATABASE_FILE  # noqa: E402

PER_LABEL = 100
LANGUAGES = ("en", "id")
OUTPUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join("eval", "sample.csv")

FIELDS = [
    "article_id", "language", "v02_label", "v02_score", "title", "summary", "url",
    "v03_attack_type", "v03_target", "v03_threat_actor",
    "label_relevant", "label_target", "label_actor", "label_notes",
]


def main():
    conn = sqlite3.connect(f"file:{DATABASE_FILE}?mode=ro", uri=True)
    rows = []
    for label in ("RELEVANT", "UNCERTAIN", "NOT_RELEVANT"):
        cursor = conn.execute(
            """
            SELECT a.article_id, a.language, r.relevance_label, r.relevance_score,
                   a.title, a.summary, a.article_url,
                   x.attack_type, x.target, x.threat_actor
            FROM articles a
            JOIN v02_relevance r USING (article_id)
            LEFT JOIN v03_information_extraction x USING (article_id)
            WHERE r.relevance_label = ? AND a.language IN (?, ?)
              AND a.article_id % 7 = 3
            ORDER BY a.article_id
            LIMIT ?
            """,
            (label, *LANGUAGES, PER_LABEL),
        )
        rows.extend(cursor.fetchall())
    conn.close()

    os.makedirs(os.path.dirname(OUTPUT) or ".", exist_ok=True)
    with open(OUTPUT, "w", newline="", encoding="utf-8") as fh:
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
    print(f"{len(rows)} artikel ditulis ke {OUTPUT}")


if __name__ == "__main__":
    main()
