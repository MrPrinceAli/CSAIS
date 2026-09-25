"""Titik masuk CSAIS: menjalankan crawler lalu pipeline V0.1 sampai V0.6.

Cara pakai (dari direktori mana pun):

    python main.py              # crawler (dengan konfirmasi) lalu V0.1 - V0.6
    python main.py --no-crawl   # lewati crawler, langsung V0.1 - V0.6
    python main.py --reset      # hapus hasil V0.2 - V0.6 lalu proses ulang

Lokasi database diatur di ``csais/config.py``.
"""

import argparse

from csais import (
    crawler,
    reset,
    v01_data_collector,
    v02_relevance_detection,
    v03_information_extraction,
    v04_entity_resolution,
    v05_incident_clustering,
    v06_evidence_correlation,
)

PIPELINE_STEPS = [
    ("V0.1 - Data Processing", v01_data_collector.run),
    ("V0.2 - Relevance Detection", v02_relevance_detection.run),
    ("V0.3 - Information Extraction", v03_information_extraction.run),
    ("V0.4 - Entity Resolution", v04_entity_resolution.run),
    ("V0.5 - Incident Clustering", v05_incident_clustering.run),
    ("V0.6 - Evidence Correlation", v06_evidence_correlation.run),
]


def parse_args():
    """Baca opsi baris perintah."""
    parser = argparse.ArgumentParser(description="CSAIS pipeline")
    parser.add_argument(
        "--no-crawl", action="store_true", help="lewati tahap crawler"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="hapus hasil olahan V0.2 - V0.6 sebelum memproses (dengan konfirmasi)",
    )
    parser.add_argument(
        "--yes", action="store_true", help="jangan minta konfirmasi untuk --reset"
    )
    return parser.parse_args()


def main():
    """Jalankan seluruh tahap secara berurutan."""
    args = parse_args()
    steps = list(PIPELINE_STEPS)
    if not args.no_crawl:
        steps.insert(0, ("CSAIS Crawler", crawler.run))

    print("==================================================")
    print("   🛡️ CYBER SOCIAL ATTACK INTELLIGENCE SYSTEM")
    print("==================================================")

    if args.reset:
        reset.reset_derived_tables(confirm=not args.yes)

    total = len(steps)
    for number, (name, step) in enumerate(steps, start=1):
        print(f"\n[{number}/{total}] 🔄 Menjalankan {name}...")
        step()

    print("\n==================================================")
    print("   CSAIS PIPELINE SELESAI")
    print("==================================================")


if __name__ == "__main__":
    main()
