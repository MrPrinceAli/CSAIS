"""Konfigurasi pytest bersama untuk seluruh pengujian CSAIS.

Path database HARUS diarahkan ke berkas sementara SEBELUM paket ``csais``
diimpor, karena ``csais.config`` membaca ``CSAIS_DB_PATH`` saat impor.
Dengan begitu database asli di ``database/csais.db`` tidak pernah disentuh.
"""

import os
import shutil
import sqlite3
import sys
import tempfile

_TEST_DIR = tempfile.mkdtemp(prefix="csais-tests-")
os.environ["CSAIS_DB_PATH"] = os.path.join(_TEST_DIR, "csais_test.db")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest  # noqa: E402

from csais.config import DATABASE_FILE  # noqa: E402

if DATABASE_FILE != os.environ["CSAIS_DB_PATH"]:
    raise RuntimeError(
        "csais.config sudah terlanjur diimpor sebelum CSAIS_DB_PATH diatur; "
        f"DATABASE_FILE = {DATABASE_FILE}"
    )


def remove_database_files():
    """Hapus berkas database sementara beserta berkas WAL/SHM-nya."""
    for suffix in ("", "-wal", "-shm", "-journal"):
        try:
            os.remove(DATABASE_FILE + suffix)
        except FileNotFoundError:
            pass


@pytest.fixture
def fresh_db():
    """Database global (CSAIS_DB_PATH) dalam keadaan kosong untuk satu tes."""
    remove_database_files()
    yield DATABASE_FILE
    remove_database_files()


@pytest.fixture(scope="module")
def fresh_db_module():
    """Database global kosong yang dipakai bersama oleh satu modul tes."""
    remove_database_files()
    yield DATABASE_FILE
    remove_database_files()


@pytest.fixture
def temp_conn(tmp_path):
    """Koneksi SQLite ke berkas sementara terpisah, untuk fungsi yang menerima conn."""
    conn = sqlite3.connect(os.path.join(tmp_path, "unit.db"))
    yield conn
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_directory():
    """Hapus direktori sementara beserta database uji setelah seluruh sesi selesai."""
    yield
    shutil.rmtree(_TEST_DIR, ignore_errors=True)
