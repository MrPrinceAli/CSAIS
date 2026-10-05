# Berkontribusi ke CSAIS

Terima kasih sudah tertarik membantu.

1. Fork repo, buat branch dari `main` (`fix/...`, `feat/...`, `docs/...`).
2. Siapkan lingkungan:
   ```bash
   python3 -m venv .venv && ./.venv/bin/pip install -r requirements-dev.txt
   ./.venv/bin/python -m pytest -q          # semua test harus lulus
   cd web && npm ci && npm run lint && npx tsc --noEmit
   ```
3. Format kode Python dengan `black`. Tambahkan test untuk setiap perilaku baru di `tests/`.
4. Jangan pernah meng-commit `.env`, token Turso, kunci lembaga, atau `database/csais.db`.
5. Buka pull request dengan deskripsi singkat: apa yang berubah, kenapa, dan cara mengujinya.

Dengan berkontribusi kamu setuju kontribusimu dirilis di bawah [MIT License](LICENSE) dan
mengikuti [Kode Etik](CODE_OF_CONDUCT.md).
