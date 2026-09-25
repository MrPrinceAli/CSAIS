"""Fungsi pengolahan teks dasar yang dipakai bersama oleh beberapa modul."""

import re

_WHITESPACE = re.compile(r"\s+")
_TOKEN = re.compile(r"[^\W_]+")
_PUBLISHER_SUFFIX = re.compile(r"\s+[-–|]\s+[^-–|]{2,60}$")
_KEYWORD_PATTERNS = {}


def split_publisher(title):
    """Pisahkan judul Google News menjadi (judul, nama media).

    Judul dari Google News berbentuk "Judul berita - Nama Media"; ringkasannya
    juga diakhiri nama media yang sama. Nama media dikembalikan agar bisa
    dibuang dari ringkasan.
    """
    title = title or ""
    match = _PUBLISHER_SUFFIX.search(title)
    if match is None:
        return title.strip(), ""
    publisher = match.group(0).strip(" -–|").strip()
    return title[: match.start()].strip(), publisher


def strip_publisher_suffix(title):
    """Buang akhiran ' - Nama Media' pada judul Google News."""
    return split_publisher(title)[0]


def remove_publisher(text, publisher):
    """Buang nama media dari akhir ringkasan Google News."""
    text = (text or "").strip()
    if publisher and text.endswith(publisher):
        text = text[: -len(publisher)].rstrip(" -–|")
    return text


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


def tokenize(text, min_length=3):
    """Himpunan token huruf/angka (huruf kecil) dengan panjang minimal."""
    normalized = normalize_text(text)
    if not normalized:
        return set()
    return {token for token in _TOKEN.findall(normalized) if len(token) >= min_length}


def keyword_pattern(keyword):
    """Regex satu kata kunci sebagai kata utuh, tidak peka huruf besar (di-cache).

    Batas kata memakai huruf/angka Latin, sehingga "rce" tidak cocok dengan
    "forced" tetapi kata kunci tetap bisa cocok di teks non-Latin tanpa spasi.
    Bentuk turunan sederhana ikut cocok ("attack" -> attacks/attacked/attacking,
    "breach" -> breaches). Kata kunci yang diakhiri tanda baca (misalnya
    "cve-") tidak diberi batas di sisi itu.
    """
    pattern = _KEYWORD_PATTERNS.get(keyword)
    if pattern is None:
        escaped = re.escape(keyword.lower())
        prefix = r"(?<![a-z0-9])" if keyword[0].isalnum() else ""
        suffix = r"(?:e?s|e?d|ing)?(?![a-z0-9])" if keyword[-1].isalnum() else ""
        pattern = re.compile(prefix + escaped + suffix, re.IGNORECASE)
        _KEYWORD_PATTERNS[keyword] = pattern
    return pattern


def contains_keyword(text, keyword):
    """True bila kata kunci muncul sebagai kata utuh di dalam teks."""
    return keyword_pattern(keyword).search(text) is not None


def find_keywords(text, keywords):
    """Kata kunci yang muncul sebagai kata utuh, urutan sesuai daftar."""
    return [keyword for keyword in keywords if contains_keyword(text, keyword)]


def drop_overlapping_keywords(matches):
    """Buang kata kunci yang merupakan bagian dari kata kunci lain yang cocok.

    Contoh: ["zero-day", "zero-day exploit", "exploit"] -> ["zero-day exploit"].
    """
    kept = []
    for keyword in matches:
        contained = any(
            other != keyword and contains_keyword(other, keyword) for other in matches
        )
        if not contained:
            kept.append(keyword)
    return kept
