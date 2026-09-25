"""Pembacaan file .env oleh csais.config.load_dotenv."""

import os

from csais.config import load_dotenv


def test_load_dotenv_reads_values_without_overriding(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# komentar\n"
        "TURSO_DATABASE_URL=libsql://contoh.turso.io\n"
        "export TURSO_AUTH_TOKEN=\"rahasia\"\n"
        "KOSONG=\n"
        "SUDAH_ADA=baru\n"
        "baris tanpa sama dengan\n",
        encoding="utf-8",
    )
    for key in ("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN", "KOSONG"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SUDAH_ADA", "lama")

    assert load_dotenv(str(env_file)) == 2
    assert os.environ["TURSO_DATABASE_URL"] == "libsql://contoh.turso.io"
    assert os.environ["TURSO_AUTH_TOKEN"] == "rahasia"
    assert "KOSONG" not in os.environ
    assert os.environ["SUDAH_ADA"] == "lama"


def test_load_dotenv_missing_file_is_noop(tmp_path):
    assert load_dotenv(str(tmp_path / "tidak-ada.env")) == 0
