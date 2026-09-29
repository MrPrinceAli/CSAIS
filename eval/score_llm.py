"""Bandingkan ekstraksi LLM lokal dengan ekstraksi aturan V0.3 pada data berlabel.

Menjalankan LLM (LLM_BASE_URL, LLM_MODEL) pada judul+ringkasan setiap baris
berlabel, lalu menghitung presisi/recall/F1 target dan pelaku untuk LLM dan
untuk kolom v03_target / v03_threat_actor di berkas label (hasil aturan saat
label dibuat), serta ketepatan is_incident terhadap label_relevant.

Jawaban LLM di-cache di eval/llm_cache.jsonl (per article_id, model, versi
prompt), jadi menjalankan ulang tidak memanggil model lagi.

Pemakaian:
  python eval/score_llm.py [eval/labels_id.csv ...] [--limit N]
"""

import argparse
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from csais import llm  # noqa: E402
from csais.llm_extraction import PROMPT_VERSION, extract  # noqa: E402
from csais.text import tokenize  # noqa: E402

CACHE = os.path.join(HERE, "llm_cache.jsonl")


def names_match(predicted, labeled):
    """Sama dengan eval/score.py: cocok bila token salah satu termuat di yang lain."""
    a, b = tokenize(predicted or ""), tokenize(labeled or "")
    if not a or not b:
        return False
    return a <= b or b <= a


def prf(tp, fp, fn):
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def _blank(value):
    return not value or value.strip().upper() in ("UNKNOWN", "NONE", "NULL")


def score_names(rows, predict, label_key):
    tp = fp = fn = 0
    for row in rows:
        if row["label_relevant"].strip().lower() != "y":
            continue
        labeled = (row.get(label_key) or "").strip()
        predicted = predict(row)
        predicted = None if _blank(predicted) else predicted
        if predicted and labeled and names_match(predicted, labeled):
            tp += 1
        else:
            if predicted:
                fp += 1
            if labeled:
                fn += 1
    return prf(tp, fp, fn)


def load_cache():
    cache = {}
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as fh:
            for line in fh:
                item = json.loads(line)
                cache[(item["article_id"], item["model"], item["prompt_version"])] = item["result"]
    return cache


def main():
    parser = argparse.ArgumentParser(description="Skor ekstraksi LLM vs aturan")
    parser.add_argument("files", nargs="*", default=[os.path.join(HERE, "labels.csv"), os.path.join(HERE, "labels_id.csv")])
    parser.add_argument("--limit", type=int, default=0, help="batasi jumlah baris per berkas (0 = semua)")
    args = parser.parse_args()

    client = llm.LLMClient()
    model = client.config["model"]
    cache = load_cache()
    with open(CACHE, "a", encoding="utf-8") as out:
        for path in args.files:
            with open(path, newline="", encoding="utf-8") as fh:
                rows = [r for r in csv.DictReader(fh) if r.get("label_relevant", "").strip().lower() in ("y", "n")]
            if args.limit:
                rows = rows[: args.limit]
            results = {}
            for index, row in enumerate(rows, start=1):
                key = (row["article_id"], model, PROMPT_VERSION)
                if key not in cache:
                    try:
                        cache[key], _ = extract(client, row["title"], row["summary"])
                    except llm.LLMError as error:
                        print(f"   ⚠️ {row['article_id']}: {error}")
                        continue
                    out.write(json.dumps({"article_id": key[0], "model": model, "prompt_version": PROMPT_VERSION, "result": cache[key]}) + "\n")
                    out.flush()
                results[row["article_id"]] = cache[key]
                if index % 25 == 0:
                    print(f"   {os.path.basename(path)}: {index}/{len(rows)}")
            scored = [r for r in rows if r["article_id"] in results]
            print(f"\n== {os.path.basename(path)}: {len(scored)} baris, model {model}, prompt {PROMPT_VERSION}")
            for label_key, rule_key, llm_key, title in (
                ("label_target", "v03_target", "target", "Target"),
                ("label_actor", "v03_threat_actor", "threat_actor", "Pelaku"),
            ):
                rule = score_names(scored, lambda r, k=rule_key: r.get(k), label_key)
                model_score = score_names(scored, lambda r, k=llm_key: results[r["article_id"]].get(k), label_key)
                print(f"  {title:7s} aturan P/R/F1 {rule[0]:.2f}/{rule[1]:.2f}/{rule[2]:.2f}   LLM {model_score[0]:.2f}/{model_score[1]:.2f}/{model_score[2]:.2f}")
            tp = sum(1 for r in scored if results[r["article_id"]]["is_incident"] and r["label_relevant"].strip().lower() == "y")
            fp = sum(1 for r in scored if results[r["article_id"]]["is_incident"] and r["label_relevant"].strip().lower() == "n")
            fn = sum(1 for r in scored if not results[r["article_id"]]["is_incident"] and r["label_relevant"].strip().lower() == "y")
            p, rc, f1 = prf(tp, fp, fn)
            print(f"  Incident (is_incident vs label_relevant) P/R/F1 {p:.2f}/{rc:.2f}/{f1:.2f}")


if __name__ == "__main__":
    main()
