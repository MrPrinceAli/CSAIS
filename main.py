"""Titik masuk CSAIS: menjalankan crawler lalu pipeline V0.1 sampai V0.6.

Cara pakai (dari direktori mana pun):

    python main.py                    # crawler (dengan konfirmasi) lalu V0.1 - V0.6
    python main.py --no-crawl         # lewati crawler, langsung V0.1 - V0.6
    python main.py --crawl            # crawl tanpa prompt (untuk penjadwalan)
    python main.py --reset            # hapus hasil V0.2 - V0.6 lalu proses ulang
    python main.py --reset-from 5     # hapus hasil V0.5 - V0.6 saja lalu proses ulang
    python main.py --export FILE      # ekspor incident ke JSON Lines lalu keluar
    python main.py --redetect-language

Seluruh keluaran layar juga disalin ke berkas di folder logs/.
Lokasi database diatur di ``csais/config.py``.
"""

import argparse
import os
import sys
from datetime import datetime

from csais import (
    content_fetcher,
    crawler,
    export,
    language,
    publish,
    reset,
    v01_data_collector,
    v02_relevance_detection,
    v03_information_extraction,
    v04_entity_resolution,
    v05_incident_clustering,
    v06_evidence_correlation,
)
from csais.config import PROJECT_ROOT
from csais.provenance import pipeline_stamp

PIPELINE_STEPS = [
    ("V0.1 - Data Processing", v01_data_collector.run),
    ("V0.2 - Relevance Detection", v02_relevance_detection.run),
    ("Content Fetch - Isi Artikel", content_fetcher.run),
    ("V0.3 - Information Extraction", v03_information_extraction.run),
    ("V0.4 - Entity Resolution", v04_entity_resolution.run),
    ("V0.5 - Incident Clustering", v05_incident_clustering.run),
    ("V0.6 - Evidence Correlation", v06_evidence_correlation.run),
]

LOG_DIR = os.path.join(PROJECT_ROOT, "logs")


class _Tee:
    """Tulis ke beberapa stream sekaligus (layar dan berkas log)."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)

    def flush(self):
        for stream in self.streams:
            stream.flush()


def start_logging():
    """Salin stdout dan stderr ke logs/csais_<waktu>.log; kembalikan path-nya."""
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, f"csais_{datetime.now():%Y%m%d_%H%M%S}.log")
    log_file = open(path, "a", encoding="utf-8")  # noqa: SIM115 (ditutup saat keluar)
    sys.stdout = _Tee(sys.__stdout__, log_file)
    sys.stderr = _Tee(sys.__stderr__, log_file)
    return path


def parse_args():
    """Baca opsi baris perintah."""
    parser = argparse.ArgumentParser(description="CSAIS pipeline")
    crawl = parser.add_mutually_exclusive_group()
    crawl.add_argument("--no-crawl", action="store_true", help="lewati tahap crawler")
    crawl.add_argument(
        "--crawl", action="store_true", help="crawl tanpa prompt konfirmasi"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="hapus hasil olahan V0.2 - V0.6 sebelum memproses (dengan konfirmasi)",
    )
    parser.add_argument(
        "--reset-from",
        type=int,
        choices=range(2, 7),
        metavar="N",
        help="hapus hasil olahan mulai tahap V0.N sampai V0.6 saja (2-6)",
    )
    parser.add_argument(
        "--yes", action="store_true", help="jangan minta konfirmasi untuk reset"
    )
    parser.add_argument(
        "--redetect-language",
        action="store_true",
        help="deteksi ulang bahasa seluruh artikel dengan langdetect, lalu keluar",
    )
    parser.add_argument(
        "--fetch-budget",
        type=int,
        default=content_fetcher.DEFAULT_BUDGET,
        metavar="N",
        help=f"maksimal artikel yang diambil isinya per run (default {content_fetcher.DEFAULT_BUDGET})",
    )
    parser.add_argument(
        "--no-fetch", action="store_true", help="lewati pengambilan isi artikel"
    )
    parser.add_argument(
        "--export", metavar="FILE", help="ekspor incident ke berkas JSON Lines, lalu keluar"
    )
    parser.add_argument(
        "--min-docs",
        type=int,
        default=1,
        metavar="N",
        help="hanya ekspor incident dengan minimal N artikel (default 1)",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="setelah pipeline (atau sendiri bersama --no-crawl --no-fetch), "
        "terbitkan hasil ke Turso (TURSO_DATABASE_URL, TURSO_AUTH_TOKEN)",
    )
    parser.add_argument(
        "--publish-only",
        action="store_true",
        help="hanya terbitkan hasil ke Turso, tanpa menjalankan pipeline",
    )
    return parser.parse_args()


def main():
    """Jalankan seluruh tahap secara berurutan."""
    args = parse_args()
    log_path = start_logging()

    print("==================================================")
    print("   🛡️ CYBER SOCIAL ATTACK INTELLIGENCE SYSTEM")
    print(f"   versi pipeline {pipeline_stamp()}")
    print("==================================================")

    if args.redetect_language:
        print("\n🔄 Mendeteksi ulang bahasa seluruh artikel...")
        total = language.redetect_all()
        print(f"\nSelesai: {total} artikel diperbarui.\n\nDistribusi bahasa:")
        for code, count in language.language_distribution():
            print(f"   {code}: {count}")
        return

    if args.export:
        print(f"\n📦 Mengekspor incident (min {args.min_docs} artikel) ke {args.export}")
        total = export.export_incidents(args.export, min_docs=args.min_docs)
        print(f"Selesai: {total} incident ditulis.")
        return

    if args.publish_only:
        publish.run()
        return

    if args.reset or args.reset_from:
        from_stage = args.reset_from or 2
        reset.reset_derived_tables(confirm=not args.yes, from_stage=from_stage)

    steps = []
    for name, step in PIPELINE_STEPS:
        if step is content_fetcher.run:
            if args.no_fetch:
                continue
            step = lambda: content_fetcher.run(budget=args.fetch_budget)  # noqa: E731
        steps.append((name, step))
    if not args.no_crawl:
        steps.insert(0, ("CSAIS Crawler", lambda: crawler.run(ask=not args.crawl)))

    if args.publish:
        steps.append(("Publish - Terbitkan ke Turso", publish.run))

    total = len(steps)
    for number, (name, step) in enumerate(steps, start=1):
        print(f"\n[{number}/{total}] 🔄 Menjalankan {name}...")
        step()

    print("\n==================================================")
    print("   CSAIS PIPELINE SELESAI")
    print(f"   log: {log_path}")
    print("==================================================")


if __name__ == "__main__":
    main()
