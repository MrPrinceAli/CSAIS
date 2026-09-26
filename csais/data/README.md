# Data kata kunci CSAIS

Folder ini berisi daftar kata kunci yang dipakai oleh modul V0.2 (deteksi
relevansi) dan V0.3 (ekstraksi informasi). Kata kunci sengaja dipisahkan dari
kode Python supaya bisa diubah tanpa menyentuh kode program.

| File                       | Dipakai oleh                          |
|----------------------------|---------------------------------------|
| `relevance_keywords.json`  | `csais/v02_relevance_detection.py`    |
| `extraction_keywords.json` | `csais/v03_information_extraction.py` |

Kedua file dibaca sekali saat modul diimpor. Perubahan berlaku pada proses
pipeline berikutnya. Artikel yang sudah dianalisis tidak otomatis dihitung
ulang.

## Aturan umum penulisan

- Format file adalah JSON (UTF-8). JSON tidak mendukung komentar; kunci
  `_comment` di bagian atas file hanya catatan dan diabaikan oleh program.
- Setiap kata kunci ditulis di antara tanda kutip ganda dan dipisahkan koma.
  Tidak boleh ada koma setelah elemen terakhir sebuah daftar.
- Kata kunci dicocokkan sebagai kata utuh, tidak peka huruf besar/kecil, dan
  bentuk turunan sederhana ikut cocok ("attack" juga cocok dengan attacks,
  attacked, attacking; "breach" dengan breaches). Kata kunci yang diakhiri
  tanda baca (misalnya `cve-`) tidak diberi batas kata di sisi itu.
- Kata kunci ditulis dengan huruf kecil (kecuali `known_threat_actors`, yang
  memakai ejaan asli nama kelompok).
- **Urutan penting.** Program memproses daftar sesuai urutannya dan hasil
  pencocokan disimpan ke database dalam urutan yang sama. Mengurutkan ulang
  daftar dapat mengubah isi kolom hasil (misalnya `attack_matches` di tabel
  `v02_relevance` atau `attack_type` di tabel `v03_information_extraction`)
  walaupun kata kuncinya sama. Tambahkan kata kunci baru tanpa mengacak
  urutan yang sudah ada.

## `relevance_keywords.json` (V0.2)

Semua nilai berupa daftar kata kunci.

| Kunci                     | Fungsi                                                                                                                                                                                                    |
|---------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `attack_keywords`         | Kata kunci serangan siber. Ada kata kunci apa pun dari daftar ini menaikkan skor relevansi; makin banyak konsep serangan yang cocok, makin tinggi skornya. Daftar ini dikelompokkan per tema (keamanan siber umum, malware, kredensial, rekayasa sosial, web, kerentanan, jaringan, data, rantai pasok, cloud, orang dalam, infrastruktur kritis, mobile, IoT, website/domain, spionase, operasi informasi, kripto, pemerasan, situs berbahaya, dark web, AI). |
| `event_indicators`        | Kata yang menandakan serangan benar-benar terjadi (attacked, breached, leaked, ...). Menaikkan skor.                                                                                                       |
| `non_incident_indicators` | Kata yang menandakan pembahasan umum, bukan insiden (conference, webinar, guide, ...). Menurunkan skor.                                                                                                     |
| `weak_attack_keywords`    | Kata serangan yang juga lazim di luar konteks siber ("worm", "trojan", "zero day", "exploitation"). Bila hanya kata dari daftar ini yang cocok dan tidak ada kata konteks siber, artikel dianggap bukan serangan siber. Setiap kata di sini harus juga ada di `attack_keywords` agar berpengaruh. Urutan daftar ini tidak berpengaruh (dipakai sebagai himpunan). |
| `cyber_context_keywords`  | Kata konteks siber (cyber, hacker, malware, vulnerability, nama vendor, kata Indonesia seperti "siber", "peretas"). Dipakai bersama `weak_attack_keywords` di atas.                                        |

Catatan tumpang tindih di V0.2: bila dua kata kunci sama-sama cocok dan yang
satu merupakan bagian dari yang lain (misalnya "phishing" dan "spear
phishing"), hanya yang lebih panjang yang dihitung. Kata kunci yang tersisa
dicatat dalam urutan daftar.

## `extraction_keywords.json` (V0.3)

Kecuali `known_threat_actors`, setiap nilai berupa kamus
`"KATEGORI": ["kata kunci", ...]`. Sebuah kategori dianggap cocok bila salah
satu kata kuncinya muncul di teks. Nama kategori (huruf besar, misalnya
`RANSOMWARE`) adalah nilai yang tersimpan di database; jangan diubah tanpa
menyesuaikan pengguna data di hilir.

| Kunci                    | Kolom hasil          | Keterangan                                                                                                   |
|--------------------------|----------------------|--------------------------------------------------------------------------------------------------------------|
| `attack_type_keywords`   | `attack_type`        | Jenis serangan (RANSOMWARE, PHISHING, DATA_BREACH, ...). Semua kategori yang cocok digabung dengan koma, urut sesuai urutan kategori di file. |
| `attack_method_keywords` | `attack_method`      | Metode serangan (PHISHING, MALWARE, EXPLOITATION, ...).                                                     |
| `target_sector_keywords` | `target_sector`      | Sektor organisasi target (HEALTHCARE, FINANCE, GOVERNMENT, ...).                                             |
| `target_group_keywords`  | `target_group`       | Kelompok orang yang menjadi target (INDIVIDUALS, EMPLOYEES, STUDENTS, ...).                                 |
| `impact_keywords`        | `impact`             | Dampak serangan (DATA_THEFT, SERVICE_DISRUPTION, FINANCIAL_LOSS, ...).                                       |
| `country_names`          | `location`           | Nama negara (kunci, dengan ejaan yang tersimpan ke database) dan kata pencariannya. Kata-kata ini juga dipakai agar nama negara tidak salah dikenali sebagai nama organisasi target. |
| `known_threat_actors`    | `threat_actor`       | Daftar (bukan kamus) nama kelompok pelaku ancaman yang dicari langsung di teks asli. Nama umum seperti "Play" atau "Royal" ditulis bersama kata "ransomware" ("Play ransomware"); akhiran " ransomware" dibuang dari hasil. Hanya tiga pelaku pertama yang disimpan, sehingga urutan daftar ini ikut menentukan hasil. |

Bila hasil pencocokan kosong, kolom hasil diisi `UNKNOWN`.

## Kosakata Indonesia

Sejak gelombang 3 (September 2026) kedua file memuat kosakata Indonesia di
akhir tiap daftar: kata serangan dan kejadian ("peretasan", "dibobol",
"kebocoran data", "penipuan online", "kena hack"), kata imbauan sebagai
penanda non-insiden ("waspada", "jangan klik", "kenali", "cara", "link video
viral"), dan sinonim Indonesia untuk jenis serangan, sektor, dampak, serta
kelompok korban. Imbuhan Indonesia tidak dikenali otomatis (pencocokan hanya
mengenal akhiran s/es/ed/ing), jadi tiap bentuk kata ditulis eksplisit.

Di V0.2 penalti non-insiden kini 0,15 per penanda sampai maksimal 0,30, agar
artikel imbauan yang memuat dua penanda atau lebih tidak dinilai RELEVANT
hanya karena menyebut "phishing" dan "malware".

Kategori kelompok korban tambahan di `target_group_keywords` (taksonomi
Indonesia): `BANK_CUSTOMERS` (nasabah), `SMES` (UMKM), `CIVIL_SERVANTS` (ASN,
PNS, PPPK), `ELDERLY` (lansia). Kategori ini ditaruh di akhir agar urutan hasil
kategori lama tidak berubah.

## Kamus cadangan jenis serangan

`attack_type_fallback_keywords` di `extraction_keywords.json` berisi kata umum
("scam", "breach", "leaked", "vulnerability", "hacked", "cyberattack",
"penipuan", "bocor", "serangan siber"). Kamus ini hanya dipakai bila tidak ada
kata dari `attack_type_keywords` yang cocok, supaya artikel "job scam" tetap
JOB_SCAM dan tidak berubah menjadi ONLINE_SCAM. Kategori `CYBER_ATTACK`
("serangan siber umum") adalah pilihan terakhir dan dibuang bila ada kategori
cadangan lain yang cocok. V0.5 memperlakukan `cyber_attack` seperti jenis yang
tidak diketahui saat mencocokkan artikel dengan incident, dan incident yang
hanya berlabel umum mengambil jenis spesifik dari artikel yang bergabung.
Pada September 2026 kamus ini menurunkan artikel RELEVANT berjenis UNKNOWN dari
27,1% menjadi 2,8%. Artikel lama baru ikut berubah setelah proses ulang mulai
V0.3 (`reset_from` 3).

