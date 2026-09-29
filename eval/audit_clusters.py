"""Audit clustering V0.5: cari incident yang berisi artikel menyimpang.

Artikel anggota dianggap menyimpang bila hampir tidak berbagi kata dengan
artikel jangkar incident (Jaccard token judul+ringkasan < OUTLIER_JACCARD)
dan nama target incident yang khas tidak muncul di teksnya. Incident seperti
ini biasanya melebar berantai: artikel B tergabung karena mirip artikel A
yang sudah masuk, bukan karena mirip incident aslinya.

Tanpa label manual, angka ini bukan presisi clustering; gunanya membandingkan
versi aturan V0.5 pada data yang sama.

Pemakaian: python eval/audit_clusters.py [--db PATH] [--min-docs 3] [--out FILE.csv]
"""

import argparse
import csv
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from csais.config import DATABASE_FILE  # noqa: E402
from csais.text import jaccard_index  # noqa: E402
from csais import v05_incident_clustering as v05  # noqa: E402

OUTLIER_JACCARD = 0.08


def audit(conn, min_docs=3):
    """Kembalikan (ringkasan, daftar incident dengan artikel menyimpang)."""
    v05.load_token_document_frequency(conn)
    incidents = conn.execute(
        """
        SELECT i.incident_id, i.target, i.document_count, i.anchor_article_id, a.title, a.summary
        FROM v05_incidents i JOIN articles a ON a.article_id = i.anchor_article_id
        WHERE i.document_count >= ?
        """,
        (min_docs,),
    ).fetchall()
    members = {}
    for incident_id, article_id, title, summary in conn.execute(
        """
        SELECT d.incident_id, d.article_id, a.title, a.summary
        FROM v05_incident_documents d JOIN articles a ON a.article_id = d.article_id
        JOIN v05_incidents i ON i.incident_id = d.incident_id
        WHERE i.document_count >= ?
        """,
        (min_docs,),
    ):
        members.setdefault(incident_id, []).append((article_id, title, summary))

    flagged, audited_articles, outlier_articles = [], 0, 0
    for incident_id, target, docs, anchor_id, anchor_title, anchor_summary in incidents:
        anchor_tokens = v05.text_tokens(anchor_title, anchor_summary)
        target_tokens = v05.distinctive_tokens(v05.normalize_value(target))
        outliers = []
        for article_id, title, summary in members.get(incident_id, []):
            if article_id == anchor_id:
                continue
            audited_articles += 1
            tokens = v05.text_tokens(title, summary)
            if target_tokens and target_tokens <= tokens:
                continue
            if jaccard_index(tokens, anchor_tokens) < OUTLIER_JACCARD:
                outliers.append(title)
        outlier_articles += len(outliers)
        if outliers:
            flagged.append({
                "incident_id": incident_id, "documents": docs, "outliers": len(outliers),
                "share": round(len(outliers) / max(1, docs - 1), 3),
                "anchor_title": anchor_title, "outlier_example": outliers[0],
            })
    flagged.sort(key=lambda r: (-r["outliers"], -r["share"]))
    summary = {
        "incidents_audited": len(incidents),
        "incidents_with_outliers": len(flagged),
        "member_articles": audited_articles,
        "outlier_articles": outlier_articles,
    }
    return summary, flagged


def main():
    parser = argparse.ArgumentParser(description="Audit clustering V0.5")
    parser.add_argument("--db", default=DATABASE_FILE)
    parser.add_argument("--min-docs", type=int, default=3)
    parser.add_argument("--out", help="tulis daftar incident menyimpang ke CSV")
    args = parser.parse_args()
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        summary, flagged = audit(conn, args.min_docs)
    finally:
        conn.close()
    share_inc = summary["incidents_with_outliers"] / max(1, summary["incidents_audited"])
    share_art = summary["outlier_articles"] / max(1, summary["member_articles"])
    print(f"Incident diaudit (>= {args.min_docs} artikel): {summary['incidents_audited']}")
    print(f"Incident dengan artikel menyimpang : {summary['incidents_with_outliers']} ({share_inc:.1%})")
    print(f"Artikel anggota (tanpa jangkar)    : {summary['member_articles']}")
    print(f"Artikel menyimpang                 : {summary['outlier_articles']} ({share_art:.1%})")
    print("\nTerburuk:")
    for row in flagged[:8]:
        print(f"  {row['incident_id']} {row['outliers']}/{row['documents'] - 1}  {row['anchor_title'][:60]!r}")
        print(f"      contoh: {row['outlier_example'][:80]!r}")
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(flagged[0]) if flagged else ["incident_id"])
            writer.writeheader()
            writer.writerows(flagged)


if __name__ == "__main__":
    main()
