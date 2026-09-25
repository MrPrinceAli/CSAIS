"""Tulis bahan pelabelan (judul, ringkasan, isi artikel, hasil pipeline) ke JSONL.

Pelabel (manusia atau agen) membaca file ini, bukan database, sehingga label
dibuat dari isi artikel yang sama dengan yang dibaca pipeline. Kolom label yang
sudah ada di file sampel ikut disalin agar bisa ditinjau ulang.

Pemakaian: python eval/dump_for_labeling.py eval/sample_id.csv keluaran.jsonl [--chars 2500]
"""

import argparse
import csv
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from csais.config import DATABASE_FILE  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sample")
    parser.add_argument("output")
    parser.add_argument("--chars", type=int, default=2500, help="potongan isi artikel")
    parser.add_argument("--only-relevant", action="store_true",
                        help="hanya baris berlabel label_relevant=y")
    args = parser.parse_args()

    with open(args.sample, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if args.only_relevant:
        rows = [r for r in rows if r.get("label_relevant", "").strip().lower() == "y"]

    conn = sqlite3.connect(f"file:{DATABASE_FILE}?mode=ro", uri=True)
    ids = [int(r["article_id"]) for r in rows]
    marks = ",".join("?" for _ in ids)
    data = {
        row[0]: row[1:]
        for row in conn.execute(
            f"""
            SELECT a.article_id, a.title, a.summary, a.content, a.content_status,
                   a.resolved_url, a.published_date, r.relevance_label,
                   x.attack_type, x.target, x.threat_actor
            FROM articles a
            LEFT JOIN v02_relevance r USING (article_id)
            LEFT JOIN v03_information_extraction x USING (article_id)
            WHERE a.article_id IN ({marks})
            """,
            ids,
        )
    }
    conn.close()

    written = 0
    with open(args.output, "w", encoding="utf-8") as out:
        for row in rows:
            article_id = int(row["article_id"])
            (title, summary, content, status, resolved_url, published, v02,
             attack_type, target, actor) = data.get(article_id, (None,) * 10)
            record = {
                "article_id": article_id,
                "title": title,
                "summary": summary,
                "published_date": published,
                "resolved_url": resolved_url,
                "content_status": status,
                "content": (content or "")[: args.chars],
                "pipeline": {
                    "v02_label": v02, "attack_type": attack_type,
                    "target": target, "threat_actor": actor,
                },
                "labels": {
                    "label_relevant": row.get("label_relevant", ""),
                    "label_target": row.get("label_target", ""),
                    "label_actor": row.get("label_actor", ""),
                    "label_notes": row.get("label_notes", ""),
                },
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
    print(f"{written} artikel ditulis ke {args.output}")


if __name__ == "__main__":
    main()
