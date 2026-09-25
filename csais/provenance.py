"""Identitas versi pipeline dan sidik jari kode.

Setiap baris hasil V0.2 sampai V0.6 menyimpan ``pipeline_stamp()`` agar selalu
bisa dijelaskan logika versi mana yang menghasilkannya. Sidik jari kode
dihitung dari isi seluruh berkas paket, jadi berubah otomatis setiap kali
kode atau daftar kata kunci diubah, tanpa perlu mengingat menaikkan nomor.
"""

import hashlib
import os

PIPELINE_VERSION = "0.7.0"

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_FINGERPRINT = None


def code_fingerprint():
    """12 heksadesimal pertama SHA-256 dari semua berkas .py dan data paket."""
    global _FINGERPRINT
    if _FINGERPRINT is None:
        digest = hashlib.sha256()
        for root, _, files in sorted(os.walk(_PACKAGE_DIR)):
            if "__pycache__" in root:
                continue
            for name in sorted(files):
                if name.endswith((".py", ".json")):
                    path = os.path.join(root, name)
                    digest.update(os.path.relpath(path, _PACKAGE_DIR).encode("utf-8"))
                    with open(path, "rb") as fh:
                        digest.update(fh.read())
        _FINGERPRINT = digest.hexdigest()[:12]
    return _FINGERPRINT


def pipeline_stamp():
    """Versi pipeline plus sidik jari kode, misalnya '0.7.0+3f9a1c2b7d10'."""
    return f"{PIPELINE_VERSION}+{code_fingerprint()}"
