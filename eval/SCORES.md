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
| 2026-09-26 pola Indonesia + pelaku baru di daftar (gelombang 3 butir 8b), V0.3 dihitung in-process | 0.7.0+ butir 8b | tidak berubah | tidak berubah | 0.68 / 0.21 / 0.32 | 0.78 / 0.50 / 0.61 |

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
| 2026-09-26 pola target dan pelaku Indonesia di V0.3 (butir 8b), dihitung in-process | 0.7.0+ butir 8b | tidak berubah | tidak berubah | 0.77 / 0.67 / 0.71 | 0.57 / 0.31 / 0.40 |

Catatan: sampel ini dipakai sebagai set pengembangan saat menyusun kosakata
Indonesia (kesalahan dibaca, kata ditambah, diukur ulang), jadi angkanya
optimistis; perlu sampel Indonesia kedua yang tidak dilihat untuk angka yang
jujur.

Catatan baris 3 (26 September): V0.3 mendapat pola bahasa Indonesia untuk
organisasi korban ("X diretas/dibobol/kena hack", "data nasabah X bocor",
"hacker jebol server X", "peretasan X", "X akui kebocoran data", "X pulih
setelah serangan") dengan penangkal Title Case (kata kerja/keterangan judul
ditolak sebagai token nama; kata aset seperti "situs", "akun", "data nasabah"
dibuang dari awal nama; nama tempat saja ditolak), pola pelaku Indonesia
("kelompok hacker X", 'hacker "X"', "X mengaku membobol"), nama negara
Indonesia di `country_names`, dan pelaku baru di `known_threat_actors` (Silver
Fox, RedDelta, Handala, DragonForce, RomCom, Mysterious Elephant, W3LL,
Desorden). Angka dihitung in-process (`extract_information` dijalankan pada
judul dan isi artikel yang ada di database) tanpa `--reset-from 3`, jadi
kolom V0.2 tidak berubah; angka Inggris ikut dihitung ulang dengan cara yang
sama untuk memastikan tidak ada regresi (target 0,30 -> 0,32, pelaku 0,48 ->
0,61 karena daftar pelaku bertambah). Sisa kesalahan target Indonesia: nama
malware dianggap korban ("Mantax Otax"), penyidik dianggap korban ("Kejari
Jakarta Pusat"), dan korban yang hanya disebut di isi artikel dengan kata
kerja yang belum ada polanya (Alldocube, BKN). Pelaku yang masih terlewat
umumnya nama orang atau layanan (Zyaire Wilkins, Anyproxy) yang memang bukan
sasaran pola grup. Setelah kode ini dijalankan dengan `--reset-from 3` pada
database sebenarnya, ukur ulang dengan `eval/score.py` dan catat di sini. Isi artikel tersedia untuk 131 dari 150. Kelas positif palsu terbesar
sebelum perubahan: artikel imbauan "link video viral, waspada phishing"
(sekitar 35 dari 150). Target 0 karena pola pengenal organisasi korban di
V0.3 (kata kerja pasif "was hit by", "breached") hanya berbahasa Inggris;
pelaku hanya tertangkap bila namanya ada di daftar (Akira, Lazarus). Keduanya
bahan gelombang 3 butir 7 dan lanjutan butir 8. Di seluruh korpus, artikel
Indonesia berlabel RELEVANT naik dari 69 menjadi 1.206 setelah kosakata
ditambah.

## LLM lokal (LM Studio, qwen/qwen3.5-9b) - sampel awal 2026-09-29

`python eval/score_llm.py --limit 30` (30 baris pertama per berkas; sampel kecil,
angka sementara). Kolom "aturan" = v03_target / v03_threat_actor yang tersimpan
di berkas label saat label dibuat.

| Berkas | Ukuran | Aturan P/R/F1 | LLM v1 | LLM v2 |
|---|---|---|---|---|
| labels.csv (en) | Target | 1.00/0.07/0.13 | 0.63/0.86/0.73 | 0.69/0.79/0.73 |
| labels.csv (en) | Pelaku | 1.00/0.20/0.33 | 1.00/0.20/0.33 | 1.00/0.20/0.33 |
| labels.csv (en) | Incident | - | 0.92/0.92/0.92 | 1.00/0.67/0.80 |
| labels_id.csv (id) | Incident | - | 0.25/1.00/0.40 | 1.00/0.75/0.86 |

Sampel Indonesia hanya berisi 4 artikel relevan tanpa label target/pelaku, jadi
skor target/pelakunya belum bermakna. Prompt v2 menambahkan aturan bahwa imbauan
dan peringatan umum ("waspada link video viral ...") bukan incident; v1
menganggapnya incident. Rata-rata sekitar 4 detik per artikel.
