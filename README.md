# CSAIS - Cyber Social Attack Intelligence System

Pipeline pengumpulan dan pengolahan berita serangan siber (khususnya
rekayasa sosial) dari Google News, ditambah halaman lembaga resmi (BSSN,
Komdigi, OJK, Polri) yang terindeks Google News lewat operator `site:`.
Seluruh hasil disimpan di database SQLite `database/csais.db`. Pipeline
berjalan di terminal (dan setiap hari di GitHub Actions); hasilnya
diterbitkan ke Turso dan ditampilkan oleh aplikasi web di folder `web/`
(https://csais.vercel.app).

## Struktur proyek

```
main.py                 titik masuk: crawler lalu V0.1 - V0.7, alur D1, dan ledger berurutan
requirements.txt        dependensi Python
.env.example            contoh kredensial Turso; salin menjadi .env (tidak ikut di git)
scripts/
  run_daily.sh          crawl harian tanpa prompt (untuk cron di komputer sendiri)
  setup_cloud.sh        simpan rahasia Turso ke GitHub Actions dan unggah rilis bootstrap
csais/
  config.py             lokasi database (bisa dioverride lewat CSAIS_DB_PATH)
  db.py                 koneksi SQLite dan timestamp bersama
  text.py               normalisasi teks, pencocokan kata utuh, Jaccard bersama
  reset.py              penghapusan hasil olahan V0.2 - V0.7 (dipakai --reset)
  language.py           deteksi bahasa artikel (langdetect)
  crawler.py            crawler Google News RSS (historical + incremental)
  content_fetcher.py    buka tautan Google News ke URL media, ambil isi artikel penuh
  sources.py            registri domain sumber (media/resmi) dan penanda sindikasi
  provenance.py         versi pipeline + sidik jari kode
  schema.py             migrasi kolom ringan, ID deterministik, catatan run
  export.py             ekspor incident ke JSON Lines (kontrak keluaran)
  publish.py            terbitkan tabel hasil ke Turso (dipakai --publish)
  ledger.py             batch Merkle bukti V0.6 (ledger sisi off-chain)
  v01_data_collector.py          V0.1 ringkasan data
  v02_relevance_detection.py     V0.2 deteksi relevansi artikel
  v03_information_extraction.py  V0.3 ekstraksi jenis serangan, target, dll.
  v04_entity_resolution.py       V0.4 penyatuan nama entitas
  v05_incident_clustering.py     V0.5 pengelompokan artikel menjadi incident
  v06_evidence_correlation.py    V0.6 korelasi bukti antar sumber
  v07_trust_score.py             V0.7 indeks kepercayaan awal per incident
  flows.py                       keluaran alur D1 - D4 per incident (tabel flow_outputs)
  survey.py                      alur D2: kumpulkan jawaban survei publik dari database survei
  official.py                    alur D3/D4: pernyataan lembaga dari statements/official_statements.csv
  flow_compare.py                metrik perbandingan alur D1 - D4 (tabel flow_metrics)
  llm.py, llm_extraction.py      LLM lokal (LM Studio) sebagai pelengkap V0.3
  chain.py                       penjangkaran akar Merkle ke blockchain lokal
chain/                  kontrak CsaisAnchor (Foundry) dan hasil kompilasinya
database/
  csais.db              database SQLite (tidak ikut di git)
```

Urutan tahap: crawler, V0.1, V0.2, content fetch, V0.3, V0.3 LLM, V0.4, V0.5, gambar,
V0.6, V0.7, alur D1, alur D2, alur D3/D4, ledger, metrik perbandingan. Setiap tahap bersifat inkremental: hanya artikel yang belum
diproses yang diolah pada run berikutnya (V0.7 menghitung ulang semua
incident karena masukannya berubah setiap run). Content fetch mengambil isi artikel penuh untuk
kandidat V0.2 dengan anggaran per run (`--fetch-budget`, default 300);
artikel yang isinya baru terambil otomatis diekstrak ulang oleh V0.3 dan
V0.4. V0.5 membandingkan jenis serangan per keluarga (ransomware dan data
breach satu keluarga) dan merangkai incident lanjutan bertarget sama.

## Alur D1 - D4

Setiap incident dinilai oleh empat alur yang menulis kolom sama ke tabel
`flow_outputs` (tambah-saja, tidak ikut `--reset`):

- D1 mesin: pipeline V0.1 - V0.7 atas semua berita (diisi tiap run; baris baru
  hanya bila isinya berubah)
- D2 kartu inti + survei publik (sesuai / tidak sesuai / tidak tahu per kolom)
- D3 kartu inti + pernyataan lembaga atau kementerian
- D4 catatan resmi: D3 yang dikonfirmasi atau dibantah, dengan reason statement

Jawaban survei D2 ditulis halaman web `/survey` ke database Turso terpisah
(`csais-survey`, tabel `survey_responses`); pipeline membacanya dengan token baca
(`SURVEY_DATABASE_URL`, `SURVEY_AUTH_TOKEN`) dan menghitung keputusan per kolom:
minimal 3 jawaban sesuai/tidak sesuai dengan 2/3 sepakat. Untuk sementara satu
orang boleh menjawab berkali-kali; penanda peramban dan hash IP disimpan agar
penyaringan bisa ditambahkan nanti.

Keputusan lembaga (D3) diberikan lewat portal `/portal`: pilih lembaga (BSSN,
OJK, Komdigi, Siber Polri; satu akun per lembaga) lalu masukkan password.
Password membuka kunci tanda tangan lembaga yang tersimpan terenkripsi di
variabel Vercel `PORTAL_KEYS`; tidak ada wallet. Petugas memilih keputusan
(dikonfirmasi, dibantah, sebagian) dan alasannya dengan tombol, dan setiap
keputusan ditandatangani (EIP-712) dengan kunci lembaga. Keputusan disimpan di
tabel `official_reviews` pada database masukan dan dibaca pipeline
(`csais/official.py`); keputusan terbaru berstatus dikonfirmasi atau dibantah
menjadi catatan resmi D4 beserta tanda tangannya, masuk batch Merkle
tersendiri (`batch_kind = official_record`), dan `/verify` memeriksa bahwa
penanda tangan adalah alamat lembaga yang terdaftar
(`web/lib/institution-keys.json`, juga terdaftar di kontrak). Pernyataan resmi
yang sudah dipublikasikan juga bisa disalin tim ke
`statements/official_statements.csv` (opsional).

Mengganti password (membuat kunci baru untuk keempat lembaga):

```bash
cd web && node scripts/portal-keys.mjs < passwords.json > keys.json   # passwords.json: {"BSSN": "...", ...}
# portalKeys -> variabel Vercel PORTAL_KEYS; addresses -> web/lib/institution-keys.json
cd .. && ./.venv/bin/python main.py --chain-institutions              # daftarkan alamat baru ke kontrak
```

Hapus `passwords.json` dan `keys.json` setelah dipakai. Catatan lama tetap sah
karena ditandatangani kunci yang berlaku saat itu, tetapi `/verify` memeriksa
terhadap alamat terbaru, jadi simpan riwayat alamat bila kunci diganti.

Saran preventif memakai `web/lib/prevention.json`, yang dibaca bersama oleh
pipeline dan web. Perbandingan untuk laporan:

```bash
./.venv/bin/python eval/compare_flows.py --as-of 2026-12-31T00:00:00+00:00   # tulis eval/flows/report.md dan metrics.csv
```

Tahap "Status Peringatan" menggabungkan keempat alur menjadi satu status
terkini per incident (tabel `incident_tiers`): catatan resmi D4 (rekomendasi
resmi atau peringatan hoaks) lebih dulu, lalu D2 yang dinyatakan sesuai
(waspada), selain itu peringatan dini dari D1, beserta langkah pencegahan dan
kanal pelaporan. Status ini tampil sebagai lencana di kartu incident, blok
pencegahan di detail incident, dan halaman publik `/alerts`.

Web menampilkan snapshot terakhir tiap alur di halaman detail incident dan
ringkasan metrik semua incident di `/comparison`; laporan Markdown dan CSV tiap
run juga diunggah sebagai artefak Actions (`flow-report-*`, 90 hari).

## Perintah lokal: LLM dan blockchain

LM Studio dan blockchain lokal berjalan di komputer sendiri, sedangkan pipeline
harian berjalan di GitHub Actions. Karena itu keduanya dijalankan sebagai
perintah lokal yang mengirim hasilnya ke database masukan (`csais-survey`,
butuh `SURVEY_WRITE_TOKEN` di `.env`); pipeline harian mengambilnya dari sana.

**LLM lokal (LM Studio).** Muat model di LM Studio, klik Start Server di tab
Developer, lalu isi `LLM_BASE_URL` (default `http://localhost:1234/v1`) dan
`LLM_MODEL` (nama model seperti tampil di LM Studio) di `.env`.

```bash
./.venv/bin/python main.py --llm-check                   # cek koneksi + satu contoh ekstraksi
./.venv/bin/python eval/score_llm.py                     # skor LLM vs aturan pada data berlabel
./.venv/bin/python main.py --llm-extract --llm-limit 200 # ekstrak artikel incident, kirim ke database masukan
```

Hasil LLM disimpan di tabel `v03_llm_extraction`. Secara default hanya
disimpan untuk dibandingkan; untuk mengisi kolom V0.3 yang kosong (UNKNOWN)
dari LLM, set variabel repositori GitHub `LLM_MERGE=fill_unknown`, lalu jalankan
workflow dengan `reset_from=4` agar V0.4 dan V0.5 memakai hasilnya.

**Blockchain lokal (Anvil, Foundry).** Kontrak `chain/src/CsaisAnchor.sol`
(permissioned: hanya relayer CSAIS yang boleh menjangkarkan; BSSN, OJK,
Komdigi, dan Siber Polri terdaftar untuk atestasi berikutnya).

```bash
./scripts/chain_local.sh                       # jalankan Anvil; state di chain/anvil-state.json
./.venv/bin/python main.py --chain-deploy      # sekali saja: pasang kontrak
./.venv/bin/python main.py --chain-institutions   # daftarkan alamat kunci lembaga portal
./.venv/bin/python main.py --anchor            # jangkarkan batch PENDING dari Turso
./.venv/bin/python main.py --anchor-status ROOT
(cd chain && forge test)                       # uji kontrak
```

Pipeline menandai batch yang akarnya ada di `chain_anchors` sebagai ANCHORED.
Jaringan ini hanya ada di komputer lokal; web menampilkan jaringan, blok, dan
transaksinya dengan keterangan prototipe. Nanti kontrak yang sama dipasang di
Besu QBFT dengan validator lembaga.

## Persiapan

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## Menjalankan

```bash
./.venv/bin/python main.py              # crawler (dengan konfirmasi) lalu V0.1 - V0.7 dan ledger
./.venv/bin/python main.py --no-crawl   # lewati crawler
./.venv/bin/python main.py --reset      # hapus hasil V0.2 - V0.7, proses ulang dari awal
./.venv/bin/python main.py --reset-from 5   # hapus hasil V0.5 - V0.7 saja, lalu proses ulang
./.venv/bin/python main.py --redetect-language  # deteksi ulang bahasa semua artikel (langdetect)
./.venv/bin/python main.py --crawl              # crawl tanpa prompt, untuk penjadwalan (scripts/run_daily.sh)
./.venv/bin/python main.py --export exports/incidents.jsonl --min-docs 2   # ekspor incident ke JSON Lines
./.venv/bin/python main.py --proof <evidence_uid>   # bukti Merkle satu evidence (JSON)
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
- `v07_trust`: indeks kepercayaan awal per incident (skor 0..1, tingkat
  tinggi/sedang/rendah, dan lima sinyalnya) beserta versi pipeline. Rumusnya di
  `csais/v07_trust_score.py`; web membaca tabel ini dan hanya menghitung sendiri
  bila tabel belum diterbitkan.
- Ledger bukti (`csais/ledger.py`): setiap run, bukti V0.6 yang belum masuk
  batch dikelompokkan (maksimal 1.024 per batch) ke `evidence_batches` (akar
  Merkle, akar batch sebelumnya, status penjangkaran) dan `evidence_leaves`
  (hash daun dan salinan payload yang di-hash). Konstruksi pohon: daun =
  SHA-256(0x00 || payload JSON kanonis), simpul = SHA-256(0x01 || min || max),
  simpul ganjil naik apa adanya; sama di `web/lib/merkle.ts` dan nanti di
  kontrak (precompile sha256). Tabel ini tambah-saja dan tidak ikut `--reset`;
  yang akan dicatat di rantai hanya akar batch. `--proof` mencetak bukti Merkle
  satu evidence untuk diverifikasi di luar.

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
   database ke cache lagi. Setiap Minggu (UTC) database juga diunggah ulang ke
   rilis `bootstrap` sebagai cadangan. Pemicu manual dari tab Actions menerima
   `reset_from` (2-7, proses ulang mulai tahap itu setelah logikanya berubah)
   dan `refresh_bootstrap` (unggah cadangan sekarang).

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
tulis hanya dipakai pekerja Actions. Untuk mencoba tampilan dengan database
lokal tanpa Turso, isi `TURSO_DATABASE_URL=file:/path/ke/csais.db` (token
boleh kosong). Situs dwibahasa: setiap path berprefiks
`/id` atau `/en` (dipilih dari cookie atau Accept-Language, diatur di
`web/proxy.ts`; kamus teks di `web/lib/i18n.ts`). Halaman: beranda,
`/incidents` (globe sebaran negara, filter, indeks kepercayaan awal, paginasi
bernomor), `/incidents/[id]` (klaim, kronologi sumber, bukti, indeks kepercayaan V0.7),
`/findings` (peringkat kelompok berisiko dan peta panas jenis serangan),
`/verify` (tautan, hash, atau ID bukti; menampilkan batch Merkle, akar, dan
bukti Merkle yang dihitung ulang dari daun batch), `/sources` (registri domain
dengan logo), dan `/institutions`. Tabel baru (`v07_trust`, `evidence_*`)
dicek keberadaannya dulu sehingga halaman tetap jalan sebelum pipeline versi
baru menerbitkannya. Commit harus memakai email yang terverifikasi di GitHub agar
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
Tabel `articles`, `crawl_state`, dan tabel ledger (`evidence_batches`,
`evidence_leaves`) tidak ikut dihapus. Di cloud, pakai input `reset_from`
pada pemicu manual workflow.

## Melihat hasil

Gunakan `sqlite3` atau aplikasi seperti DB Browser for SQLite, misalnya:

```bash
sqlite3 -header -column database/csais.db \
  "SELECT * FROM v05_incidents ORDER BY rowid DESC LIMIT 10"
```

Tabel utama: `articles`, `v02_relevance`, `v03_information_extraction`,
`v04_entities`, `v04_entity_mentions`, `v05_incidents`,
`v05_incident_documents`, `v06_evidence`, `v06_source_relations`.
