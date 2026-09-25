"""Titik masuk CSAIS: menjalankan crawler lalu pipeline V0.1 sampai V0.6.

Cara pakai (dari direktori mana pun):

    python main.py

Lokasi database diatur di ``csais/config.py``.
"""

from csais import (
    crawler,
    v01_data_collector,
    v02_relevance_detection,
    v03_information_extraction,
    v04_entity_resolution,
    v05_incident_clustering,
    v06_evidence_correlation,
)

STEPS = [
    ("CSAIS Crawler", crawler.run),
    ("V0.1 - Data Processing", v01_data_collector.run),
    ("V0.2 - Relevance Detection", v02_relevance_detection.run),
    ("V0.3 - Information Extraction", v03_information_extraction.run),
    ("V0.4 - Entity Resolution", v04_entity_resolution.run),
    ("V0.5 - Incident Clustering", v05_incident_clustering.run),
    ("V0.6 - Evidence Correlation", v06_evidence_correlation.run),
]


def main():
    """Jalankan seluruh tahap secara berurutan."""
    print("==================================================")
    print("   🛡️ CYBER SOCIAL ATTACK INTELLIGENCE SYSTEM")
    print("==================================================")

    total = len(STEPS)
    for number, (name, step) in enumerate(STEPS, start=1):
        print(f"\n[{number}/{total}] 🔄 Menjalankan {name}...")
        step()

    print("\n==================================================")
    print("   CSAIS PIPELINE SELESAI")
    print("==================================================")


if __name__ == "__main__":
    main()
