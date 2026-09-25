"""Fungsi pengolahan teks dasar yang dipakai bersama oleh beberapa modul."""

import re

_WHITESPACE = re.compile(r"\s+")


def normalize_text(text):
    """Huruf kecil, hapus spasi tepi, dan rapatkan spasi berulang.

    ``None`` menjadi string kosong. Nilai bukan string diubah ke string.
    """
    if text is None:
        return ""
    return _WHITESPACE.sub(" ", str(text).lower().strip())


def jaccard_index(tokens_a, tokens_b):
    """Jaccard similarity dua himpunan token. Kosong menghasilkan 0.0."""
    if not tokens_a or not tokens_b:
        return 0.0
    union = tokens_a | tokens_b
    if not union:
        return 0.0
    return len(tokens_a & tokens_b) / len(union)
