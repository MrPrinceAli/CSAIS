# CSAIS - Cyber Social Attack Intelligence System

Pipeline pengumpulan dan pengolahan berita serangan siber (khususnya
rekayasa sosial) dari Google News. Seluruh hasil disimpan di database
SQLite `database/csais.db`. Program berjalan di terminal, tidak ada
antarmuka web.

## Struktur proyek

```
main.py                 titik masuk: crawler lalu V0.1 - V0.6 berurutan
requirements.txt        dependensi Python
csais/
  config.py             lokasi database (bisa dioverride lewat CSAIS_DB_PATH)
  db.py                 koneksi SQLite dan timestamp bersama
  text.py               normalisasi teks dan Jaccard bersama
  crawler.py            crawler Google News RSS (historical + incremental)
  v01_data_collector.py          V0.1 ringkasan data
  v02_relevance_detection.py     V0.2 deteksi relevansi artikel
  v03_information_extraction.py  V0.3 ekstraksi jenis serangan, target, dll.
  v04_entity_resolution.py       V0.4 penyatuan nama entitas
  v05_incident_clustering.py     V0.5 pengelompokan artikel menjadi incident
  v06_evidence_correlation.py    V0.6 korelasi bukti antar sumber
database/
  csais.db              database SQLite (tidak ikut di git)
```

Setiap modul V0.x bersifat inkremental: hanya artikel yang belum
diproses yang diolah pada run berikutnya.

## Persiapan

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## Menjalankan

```bash
./.venv/bin/python main.py
```

Crawler akan menanyakan apakah ingin menarik data baru (`y`) atau
langsung memproses data yang sudah ada (`n`). Crawl membutuhkan koneksi
internet dan bisa memakan waktu lama.

## Melihat hasil

Gunakan `sqlite3` atau aplikasi seperti DB Browser for SQLite, misalnya:

```bash
sqlite3 -header -column database/csais.db \
  "SELECT * FROM v05_incidents ORDER BY rowid DESC LIMIT 10"
```

Tabel utama: `articles`, `v02_relevance`, `v03_information_extraction`,
`v04_entities`, `v04_entity_mentions`, `v05_incidents`,
`v05_incident_documents`, `v06_evidence`, `v06_source_relations`.
