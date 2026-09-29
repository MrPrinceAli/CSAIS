"""Laporan perbandingan keluaran alur D1 - D4 (lihat csais/flow_compare.py).

Pemakaian:
  python eval/compare_flows.py [--db PATH] [--as-of ISO] [--out DIR]
Hasil: DIR/report.md dan DIR/metrics.csv (default eval/flows/), dan
laporan Markdown dicetak ke layar. ``--as-of`` membuat angka bisa diulang
persis dengan snapshot yang sama walaupun D1 terus berubah.
"""

import argparse
import csv
import os
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from csais.config import DATABASE_FILE  # noqa: E402
from csais.flow_compare import (  # noqa: E402,F401  (diekspor ulang untuk pengujian)
    cohen_kappa, compare, compute, first_seen, load_latest, parse_time, same_value,
)


def fmt(value):
    if value is None:
        return "–"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def render(metrics, as_of):
    lines = [
        "# Perbandingan alur D1 - D4",
        "",
        f"Snapshot sampai {as_of.isoformat(timespec='seconds')}. Tanda – berarti belum ada data.",
        "",
        "| Ukuran | Alur | Kolom | Nilai | n | Catatan |",
        "|---|---|---|---|---|---|",
    ]
    for m in metrics:
        lines.append(f"| {m['metric']} | {m['flow']} | {m['field']} | {fmt(m['value'])} | {m['n']} | {m['note']} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Bandingkan keluaran alur D1 - D4")
    parser.add_argument("--db", default=DATABASE_FILE)
    parser.add_argument("--as-of", help="waktu snapshot ISO 8601 (default sekarang)")
    parser.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "flows"))
    args = parser.parse_args()

    as_of = parse_time(args.as_of) if args.as_of else datetime.now(timezone.utc)
    if as_of is None:
        parser.error(f"--as-of tidak terbaca: {args.as_of}")
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        metrics = compute(conn, as_of)
    finally:
        conn.close()

    os.makedirs(args.out, exist_ok=True)
    report = render(metrics, as_of)
    with open(os.path.join(args.out, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(report)
    with open(os.path.join(args.out, "metrics.csv"), "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["metric", "flow", "field", "value", "n", "note"])
        writer.writeheader()
        writer.writerows(metrics)
    print(report)


if __name__ == "__main__":
    main()
