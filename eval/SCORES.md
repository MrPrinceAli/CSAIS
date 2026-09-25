# Riwayat skor evaluasi

Dihitung dengan `python eval/score.py` terhadap `eval/labels.csv` (300 artikel
berstrata: 100 per label V0.2, semuanya berbahasa Inggris; 2 baris "?"
diabaikan). Angka ini untuk membandingkan versi pipeline, bukan estimasi
seluruh korpus. Tambahkan baris baru setiap kali logika V0.2 atau V0.3 berubah.

| Tanggal | Versi pipeline | V0.2 ketat P/R/F1 | V0.2 longgar P/R/F1 | Target P/R/F1 | Pelaku P/R/F1 |
|---|---|---|---|---|---|
| 2026-09-25 | 0.7.0+e2d6b51280a9 | 0.77 / 0.51 / 0.61 | 0.64 / 0.83 / 0.72 | 0.88 / 0.12 / 0.21 | 0.75 / 0.23 / 0.35 |

| 2026-09-25 (isi artikel penuh untuk 220 dari 300 sampel) | 0.7.0+... gelombang 2a | 0.77 / 0.51 / 0.61 | 0.64 / 0.83 / 0.72 | 0.69 / 0.15 / 0.25 | 0.27 / 0.23 / 0.25 |

Catatan 2026-09-25: recall target dan pelaku rendah karena ekstraksi hanya
membaca judul dan satu kalimat ringkasan Google News; ini yang dituju
gelombang 2 (isi artikel penuh, model NER). Presisinya sudah tinggi.

Catatan setelah isi artikel penuh: penurunan "presisi" pelaku (0.75 ke 0.27)
sebagian besar bukan kesalahan pipeline. Label dibuat hanya dari judul dan
ringkasan, sedangkan pipeline kini membaca isi artikel: untuk Change
Healthcare dan UnitedHealth pipeline menemukan BlackCat/ALPHV yang memang
benar tetapi tidak ada di label. Dua kesalahan nyata: "Allegedly Claims 20"
(judul "Threat Actor Allegedly Claims ...") dan "Campaign Overview" dari isi
artikel. Tindak lanjut: label target dan pelaku perlu ditinjau ulang dengan
isi artikel tersedia, dan pola pelaku perlu menolak kata-kata seperti
"allegedly", "claims", "overview".
