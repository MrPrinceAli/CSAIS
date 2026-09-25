# Pengujian CSAIS
Jalankan dari root proyek: `.venv/bin/python -m pytest -q` (pasang dulu pytest dengan `.venv/bin/pip install -r requirements-dev.txt`).
`conftest.py` mengarahkan `CSAIS_DB_PATH` ke berkas sementara sebelum paket `csais` diimpor, sehingga database asli `database/csais.db` tidak pernah disentuh.
Semua tes berjalan tanpa jaringan; fungsi crawl (`crawl_keyword`, `crawler.run`) tidak dipanggil, hanya fungsi pembantu dan checkpoint-nya.
`test_pipeline_integration.py` membangun database kecil berisi artikel sintetis lalu menjalankan V0.4, V0.5, V0.6, dan ekspor JSONL secara nyata.
