# Pernyataan lembaga (alur D3 dan D4)

`official_statements.csv` berisi pernyataan resmi lembaga atau kementerian
tentang incident CSAIS. Pipeline membacanya setiap run (`csais/official.py`):
pernyataan terbaru per incident menjadi keluaran D3, dan yang berstatus
`dikonfirmasi` atau `dibantah` dengan `reason` terisi menjadi catatan resmi D4
(masuk ledger Merkle). Berkas ini dipakai sampai portal lembaga tersedia.

Isi hanya pernyataan yang sudah dipublikasikan lembaga, dan selalu sertakan
tautannya. Satu baris = satu pernyataan; revisi ditulis sebagai baris baru
dengan `statement_date` lebih baru, baris lama jangan dihapus.

| Kolom | Isi |
|---|---|
| statement_id | ID unik buatan tim, misalnya `OJK-2026-001` |
| incident_id | ID incident CSAIS, misalnya `INCIDENT_4E3B58BC6E7E` |
| institution | BSSN, OJK, Komdigi, Polri, atau nama kementerian |
| status | `dikonfirmasi`, `dibantah`, atau `sebagian` |
| statement_date | tanggal pernyataan, `YYYY-MM-DD` |
| source_url | tautan siaran pers atau unggahan resmi |
| reason | ringkasan alasan atau isi pernyataan (wajib untuk D4) |
| attack_type, target, threat_actor, attack_date, location | isi hanya bila lembaga menyebutnya; dibandingkan dengan kartu mesin |
| prevention_text | imbauan atau langkah pencegahan dari lembaga |
| prevention_keys | opsional, kunci dari `web/lib/prevention.json` dipisah `;` (misalnya `type:phishing:0;group:BANK_CUSTOMERS`) |
| recorded_by | nama pencatat |

Daftar incident yang kemungkinan punya pernyataan resmi (artikel dari situs
lembaga atau judul menyebut lembaga) bisa dibuat dengan:

```bash
./.venv/bin/python main.py --official-candidates statements/kandidat.csv
```

Kolom `card_*` dan `hint_*` di berkas kandidat hanya bantuan; hapus sebelum
menyalin baris ke `official_statements.csv`.
