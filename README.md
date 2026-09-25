# CSAIS - Cyber Social Attack Intelligence System

Pipeline pengumpulan dan pengolahan berita serangan siber (khususnya
rekayasa sosial) dari Google News, ditambah halaman lembaga resmi (BSSN,
Komdigi, OJK, Polri) yang terindeks Google News lewat operator `site:`.
Seluruh hasil disimpan di database SQLite `database/csais.db`. Program
berjalan di terminal, tidak ada antarmuka web.

## Struktur proyek

```
main.py                 titik masuk: crawler lalu V0.1 - V0.6 berurutan
requirements.txt        dependensi Python
.env.example            contoh kredensial Turso; salin menjadi .env (tidak ikut di git)
scripts/
  run_daily.sh          crawl harian tanpa prompt (untuk cron di komputer sendiri)
  setup_cloud.sh        simpan rahasia Turso ke GitHub Actions dan unggah rilis bootstrap
csais/
  config.py             lokasi database (bisa dioverride lewat CSAIS_DB_PATH)
  db.py                 koneksi SQLite dan timestamp bersama
  text.py               normalisasi teks, pencocokan kata utuh, Jaccard bersama
  reset.py              penghapusan hasil olahan V0.2 - V0.6 (dipakai --reset)
  language.py           deteksi bahasa artikel (langdetect)
  crawler.py            crawler Google News RSS (historical + incremental)
  content_fetcher.py    buka tautan Google News ke URL media, ambil isi artikel penuh
  sources.py            registri domain sumber (media/resmi) dan penanda sindikasi
  provenance.py         versi pipeline + sidik jari kode
  schema.py             migrasi kolom ringan, ID deterministik, catatan run
  export.py             ekspor incident ke JSON Lines (kontrak keluaran)
  v01_data_collector.py          V0.1 ringkasan data
  v02_relevance_detection.py     V0.2 deteksi relevansi artikel
  v03_information_extraction.py  V0.3 ekstraksi jenis serangan, target, dll.
  v04_entity_resolution.py       V0.4 penyatuan nama entitas
  v05_incident_clustering.py     V0.5 pengelompokan artikel menjadi incident
  v06_evidence_correlation.py    V0.6 korelasi bukti antar sumber
database/
  csais.db              database SQLite (tidak ikut di git)
```

Urutan tahap: crawler, V0.1, V0.2, content fetch, V0.3, V0.4, V0.5, V0.6.
Setiap tahap bersifat inkremental: hanya artikel yang belum diproses yang
diolah pada run berikutnya. Content fetch mengambil isi artikel penuh untuk
kandidat V0.2 dengan anggaran per run (`--fetch-budget`, default 300);
artikel yang isinya baru terambil otomatis diekstrak ulang oleh V0.3 dan
V0.4. V0.5 membandingkan jenis serangan per keluarga (ransomware dan data
breach satu keluarga) dan merangkai incident lanjutan bertarget sama.

## Persiapan

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## Menjalankan

```bash
./.venv/bin/python main.py              # crawler (dengan konfirmasi) lalu V0.1 - V0.6
./.venv/bin/python main.py --no-crawl   # lewati crawler
./.venv/bin/python main.py --reset      # hapus hasil V0.2 - V0.6, proses ulang dari awal
./.venv/bin/python main.py --reset-from 5   # hapus hasil V0.5 - V0.6 saja, lalu proses ulang
./.venv/bin/python main.py --redetect-language  # deteksi ulang bahasa semua artikel (langdetect)
./.venv/bin/python main.py --crawl              # crawl tanpa prompt, untuk penjadwalan (scripts/run_daily.sh)
./.venv/bin/python main.py --export exports/incidents.jsonl --min-docs 2   # ekspor incident ke JSON Lines
```

Setiap run menyalin keluaran layar ke `logs/csais_<waktu>.log` dan mencatat
tahap yang dijalankan di tabel `pipeline_runs` beserta versi pipeline
(`csais/provenance.py`: nomor versi plus sidik jari kode). Setiap baris hasil
V0.2 sampai V0.6 juga menyimpan versi itu di kolom `pipeline_version`.

## Identitas data dan ekspor

- `articles.article_uid`: ID deterministik artikel (24 heksadesimal SHA-256 dari
  URL), sama di database mana pun. `incident_id` diturunkan dari article_uid
  artikel pertamanya, dan `v06_evidence.evidence_uid` dari incident dan artikel.
  ID ini yang dipakai sistem lain (ledger bukti, laporan), bukan nomor urut.
- `--export` menulis JSON Lines: baris pertama metadata, lalu satu incident per
  baris berisi klaim tiap artikel (hasil V0.3), bukti (V0.6), dan relasi antar
  sumber. Skemanya didokumentasikan di `csais/export.py`.

## Evaluasi

`eval/make_sample.py` mengambil artikel berstrata (100 per label V0.2 untuk
bahasa Inggris; `--language id --per-label 50` untuk sampel Indonesia),
`eval/labels.csv` dan `eval/labels_id.csv` berisi label manual (relevan,
target, pelaku), dan `eval/score.py [file label]` menghitung presisi, recall,
dan F1 pipeline terhadap label itu dari database saat ini. Sebelum mengukur,
`eval/fetch_sample_content.py [file label]` mengambil isi artikel sampel yang
belum ada (status `unresolved`/`error` dicoba lagi), lalu
`main.py --no-crawl --no-fetch` mengekstrak ulang. Jalankan `score.py` setiap
kali logika V0.2 atau V0.3 berubah dan catat hasilnya di `eval/SCORES.md`.

## Menjalankan di cloud (gratis)

Pembagian kerja: pekerja pipeline di GitHub Actions, database bersama di
Turso (SQLite hosted), aplikasi web di Vercel yang hanya membaca Turso.

1. Buat database di Turso, lalu ambil URL dan token:
   `turso db create csais`, `turso db show csais --url`,
   `turso db tokens create csais`.
2. Salin `.env.example` menjadi `.env` dan isi kedua nilainya. `main.py`
   membaca `.env` otomatis (variabel yang sudah ada di lingkungan tidak
   ditimpa; file ini di-gitignore, jangan tulis kredensial di kode). Lalu uji
   terbit dari komputer lokal:

   ```bash
   ./.venv/bin/python main.py --publish-only
   ```

3. Kode ada di repo GitHub `MrPrinceAli/CSAIS`. Jalankan
   `scripts/setup_cloud.sh` (butuh `gh` yang sudah login) untuk menyimpan
   kedua rahasia ke Settings > Secrets and variables > Actions dan mengunggah
   database saat ini sebagai rilis `bootstrap` yang dipakai run pertama.
4. Workflow `.github/workflows/daily.yml` berjalan tiap hari pukul 04:00 WIB:
   memulihkan database dari cache, crawl tanpa prompt, mengolah artikel baru,
   mengambil isi artikel (anggaran 300), menerbitkan ke Turso, menyimpan
   database ke cache lagi. Bisa dipicu manual dari tab Actions.

Batasan paket gratis: 2.000 menit Actions per bulan untuk repo privat (satu run
sekitar 30 sampai 45 menit), cache 10 GB, Turso 9 GB dan 25 juta baris tulis
per bulan; semuanya jauh di atas kebutuhan saat ini.

## Aplikasi web (folder `web/`)

Dashboard publik dibangun dengan Next.js dan hanya membaca Turso lewat token
baca-saja; tidak ada yang berjalan di laptop. Produksi: https://csais.vercel.app
(proyek Vercel `csais`, root directory `web`, wilayah fungsi Tokyo agar dekat
database). Setiap push ke `main` yang menyentuh `web/` memicu deploy otomatis.

```bash
cd web
cp .env.local.example .env.local      # isi TURSO_DATABASE_URL dan token baca-saja
npm install
npm run dev                            # http://localhost:3000
```

Token baca-saja dibuat dengan `turso db tokens create csais --read-only`; token
tulis hanya dipakai pekerja Actions. Situs dwibahasa: setiap path berprefiks
`/id` atau `/en` (dipilih dari cookie atau Accept-Language, diatur di
`web/proxy.ts`; kamus teks di `web/lib/i18n.ts`). Halaman: beranda,
`/incidents` (globe sebaran negara, filter, indeks kepercayaan awal, paginasi
bernomor), `/incidents/[id]` (klaim, kronologi sumber, bukti), `/findings`
(peringkat kelompok berisiko dan peta panas jenis serangan), `/verify`
(tautan, hash, atau ID bukti), `/sources` (registri domain dengan logo), dan
`/institutions`. Commit harus memakai email yang terverifikasi di GitHub agar
Vercel mau membangunnya (`git config user.email` di repo ini sudah diatur).

## Pengembangan

```bash
./.venv/bin/pip install -r requirements-dev.txt
./.venv/bin/python -m pytest          # tes otomatis di folder tests/
```

Daftar kata kunci ada di `csais/data/*.json` dan bisa diedit tanpa menyentuh
kode.

Crawler akan menanyakan apakah ingin menarik data baru (`y`) atau
langsung memproses data yang sudah ada (`n`). Bila `y`, periode historical
30 hari yang belum lengkap dilengkapi dulu, lalu incremental crawl menarik
3 hari terakhir. Crawl membutuhkan koneksi internet dan bisa memakan waktu
lama. Checkpoint disimpan per hari, jadi run yang terputus bisa dilanjutkan
tanpa mengulang kata kunci yang sudah selesai.

`--reset` diperlukan setelah logika ekstraksi atau clustering berubah,
karena setiap modul hanya memproses artikel yang belum pernah diolah.
Tabel `articles` dan `crawl_state` tidak ikut dihapus.

## Melihat hasil

Gunakan `sqlite3` atau aplikasi seperti DB Browser for SQLite, misalnya:

```bash
sqlite3 -header -column database/csais.db \
  "SELECT * FROM v05_incidents ORDER BY rowid DESC LIMIT 10"
```

Tabel utama: `articles`, `v02_relevance`, `v03_information_extraction`,
`v04_entities`, `v04_entity_mentions`, `v05_incidents`,
`v05_incident_documents`, `v06_evidence`, `v06_source_relations`.
