"""Ukur kualitas pipeline terhadap label manual di eval/labels.csv.

Kolom label:
  label_relevant : y (berita serangan/insiden/penipuan siber yang konkret),
                   n (bukan), ? (ragu, baris diabaikan)
  label_target   : organisasi/entitas yang menjadi korban, kosong bila tidak ada
  label_actor    : nama pelaku/grup, kosong bila tidak ada

Hasil pipeline dibaca langsung dari database saat skrip dijalankan, jadi
skor bisa dihitung ulang setiap kali pipeline berubah. Sampelnya berstrata
(100 per label V0.2), bukan proporsi populasi, jadi angkanya untuk
membandingkan versi, bukan estimasi seluruh korpus.

Pemakaian: python eval/score.py [eval/labels.csv]
"""

import csv
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from csais.config import DATABASE_FILE  # noqa: E402
from csais.text import tokenize  # noqa: E402

LABELS = sys.argv[1] if len(sys.argv) > 1 else os.path.join("eval", "labels.csv")


def prf(tp, fp, fn):
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def names_match(predicted, labeled):
    """Cocok bila sama setelah normalisasi, atau token salah satu ada di yang lain."""
    a, b = tokenize(predicted), tokenize(labeled)
    if not a or not b:
        return False
    return a <= b or b <= a


def load_labels(path):
    with open(path, newline="", encoding="utf-8") as fh:
        rows = [row for row in csv.DictReader(fh)]
    return [row for row in rows if row.get("label_relevant", "").strip().lower() in ("y", "n")]


def load_predictions(article_ids):
    conn = sqlite3.connect(f"file:{DATABASE_FILE}?mode=ro", uri=True)
    marks = ",".join("?" for _ in article_ids)
    rows = conn.execute(
        f"""
        SELECT a.article_id, r.relevance_label, x.target, x.threat_actor
        FROM articles a
        LEFT JOIN v02_relevance r USING (article_id)
        LEFT JOIN v03_information_extraction x USING (article_id)
        WHERE a.article_id IN ({marks})
        """,
        article_ids,
    ).fetchall()
    conn.close()
    return {row[0]: row[1:] for row in rows}


def score_names(rows, predictions, label_key, prediction_index, title):
    tp = fp = fn = 0
    for row in rows:
        if row["label_relevant"].strip().lower() != "y":
            continue
        labeled = row.get(label_key, "").strip()
        predicted = (predictions.get(int(row["article_id"])) or (None, None, None))[
            prediction_index
        ]
        predicted = "" if predicted in (None, "UNKNOWN") else predicted
        if labeled and predicted:
            if names_match(predicted, labeled):
                tp += 1
            else:
                fp += 1
                fn += 1
        elif labeled:
            fn += 1
        elif predicted:
            fp += 1
    precision, recall, f1 = prf(tp, fp, fn)
    print(f"\n{title} (hanya artikel berlabel relevan)")
    print(f"  benar {tp}, salah/asing {fp}, terlewat {fn}")
    print(f"  presisi {precision:.2f}  recall {recall:.2f}  F1 {f1:.2f}")


def main():
    rows = load_labels(LABELS)
    if not rows:
        print(f"Tidak ada baris berlabel y/n di {LABELS}")
        return
    predictions = load_predictions([int(row["article_id"]) for row in rows])

    print(f"Label dipakai : {len(rows)} artikel dari {LABELS}")
    print(f"Database      : {DATABASE_FILE}")

    for mode, positive in (("ketat (RELEVANT saja)", {"RELEVANT"}),
                           ("longgar (RELEVANT + UNCERTAIN)", {"RELEVANT", "UNCERTAIN"})):
        tp = fp = fn = tn = 0
        for row in rows:
            truth = row["label_relevant"].strip().lower() == "y"
            label = (predictions.get(int(row["article_id"])) or (None,))[0]
            predicted = label in positive
            if truth and predicted:
                tp += 1
            elif truth:
                fn += 1
            elif predicted:
                fp += 1
            else:
                tn += 1
        precision, recall, f1 = prf(tp, fp, fn)
        print(f"\nRelevansi V0.2, mode {mode}")
        print(f"  TP {tp}  FP {fp}  FN {fn}  TN {tn}")
        print(f"  presisi {precision:.2f}  recall {recall:.2f}  F1 {f1:.2f}")

    score_names(rows, predictions, "label_target", 1, "Target V0.3")
    score_names(rows, predictions, "label_actor", 2, "Pelaku V0.3")


if __name__ == "__main__":
    main()
