# Riwayat skor evaluasi

Dihitung dengan `python eval/score.py` terhadap `eval/labels.csv` (300 artikel
berstrata: 100 per label V0.2, semuanya berbahasa Inggris; 2 baris "?"
diabaikan). Angka ini untuk membandingkan versi pipeline, bukan estimasi
seluruh korpus. Tambahkan baris baru setiap kali logika V0.2 atau V0.3 berubah.

| Tanggal | Versi pipeline | V0.2 ketat P/R/F1 | V0.2 longgar P/R/F1 | Target P/R/F1 | Pelaku P/R/F1 |
|---|---|---|---|---|---|
| 2026-09-25 | 0.7.0+e2d6b51280a9 | 0.77 / 0.51 / 0.61 | 0.64 / 0.83 / 0.72 | 0.88 / 0.12 / 0.21 | 0.75 / 0.23 / 0.35 |

Catatan 2026-09-25: recall target dan pelaku rendah karena ekstraksi hanya
membaca judul dan satu kalimat ringkasan Google News; ini yang dituju
gelombang 2 (isi artikel penuh, model NER). Presisinya sudah tinggi.
