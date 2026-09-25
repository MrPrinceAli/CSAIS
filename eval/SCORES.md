# Riwayat skor evaluasi

Dihitung dengan `python eval/score.py [file label]` terhadap label manual. Angka
ini untuk membandingkan versi pipeline, bukan estimasi seluruh korpus, karena
sampelnya berstrata per label V0.2. Tambahkan baris baru setiap kali logika
V0.2 atau V0.3 berubah.

## Sampel Inggris (`eval/labels.csv`, 300 artikel, 100 per label V0.2)

| Tanggal | Versi pipeline | V0.2 ketat P/R/F1 | V0.2 longgar P/R/F1 | Target P/R/F1 | Pelaku P/R/F1 |
|---|---|---|---|---|---|
| 2026-09-25 | 0.7.0+e2d6b51280a9 | 0.77 / 0.51 / 0.61 | 0.64 / 0.83 / 0.72 | 0.88 / 0.12 / 0.21 | 0.75 / 0.23 / 0.35 |
| 2026-09-25 (isi artikel 100/300) | 0.7.0+ gelombang 2a | 0.77 / 0.51 / 0.61 | 0.64 / 0.83 / 0.72 | 0.69 / 0.15 / 0.25 | 0.27 / 0.23 / 0.25 |
| 2026-09-25 (isi artikel 225/300, label ditinjau ulang) | 0.7.0+d00be1ec2c9c | 0.76 / 0.51 / 0.61 | 0.64 / 0.84 / 0.72 | 0.71 / 0.19 / 0.30 | 0.71 / 0.36 / 0.48 |

Catatan baris 1: recall target dan pelaku rendah karena ekstraksi hanya
membaca judul dan satu kalimat ringkasan Google News.

Catatan baris 2: penurunan "presisi" pelaku (0.75 ke 0.27) sebagian besar
artefak label: label dibuat dari judul saja, sedangkan pipeline membaca isi
artikel dan menemukan pelaku yang benar tetapi tidak ada di label (BlackCat/
ALPHV pada Change Healthcare). Dua kesalahan nyata: "Allegedly Claims 20"
dan "Campaign Overview".

Catatan baris 3: label target dan pelaku ditinjau ulang dengan isi artikel
(26 baris berubah, 15 pelaku ditambah, 1 relevansi dibalik), sehingga baris ini
tidak sepenuhnya sebanding dengan dua baris di atasnya. Perubahan kode:
V0.3 menolak keterangan ("allegedly", "North Korean", "Russian-aligned"),
judul seksi isi artikel ("Campaign Overview"), nama bulan, dan nama yang
melintasi baris baru. Isi artikel tersedia untuk 225 dari 300 sampel
(sisanya diblokir situs media atau kosong). Kesalahan pelaku yang tersisa
sebagian besar nama yang belum ada di daftar dan tidak berpola (Silver Fox,
RedDelta, Handala, HeartSender); ini bahan gelombang 3 (NER/LLM).

## Sampel Indonesia (`eval/labels_id.csv`, 150 artikel, 50 per label V0.2)

| Tanggal | Versi pipeline | V0.2 ketat P/R/F1 | V0.2 longgar P/R/F1 | Target P/R/F1 | Pelaku P/R/F1 |
|---|---|---|---|---|---|
| 2026-09-25 sebelum kosakata Indonesia (simulasi dari label V0.2 lama) | 0.7.0+8299c14 | 0.16 / 0.18 / 0.17 | 0.30 / 0.68 / 0.42 | tidak diukur | tidak diukur |
| 2026-09-25 setelah kosakata Indonesia (gelombang 3 butir 8, V0.2/V0.3) | 0.7.0+d00be1ec2c9c | 0.62 / 0.48 / 0.54 | 0.48 / 0.93 / 0.64 | 0.00 / 0.00 / 0.00 | 0.67 / 0.15 / 0.25 |

Catatan: sampel ini dipakai sebagai set pengembangan saat menyusun kosakata
Indonesia (kesalahan dibaca, kata ditambah, diukur ulang), jadi angkanya
optimistis; perlu sampel Indonesia kedua yang tidak dilihat untuk angka yang
jujur. Isi artikel tersedia untuk 131 dari 150. Kelas positif palsu terbesar
sebelum perubahan: artikel imbauan "link video viral, waspada phishing"
(sekitar 35 dari 150). Target 0 karena pola pengenal organisasi korban di
V0.3 (kata kerja pasif "was hit by", "breached") hanya berbahasa Inggris;
pelaku hanya tertangkap bila namanya ada di daftar (Akira, Lazarus). Keduanya
bahan gelombang 3 butir 7 dan lanjutan butir 8. Di seluruh korpus, artikel
Indonesia berlabel RELEVANT naik dari 69 menjadi 1.206 setelah kosakata
ditambah.
