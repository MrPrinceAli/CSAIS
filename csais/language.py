"""Deteksi bahasa artikel.

Memakai ``langdetect`` (port pustaka deteksi bahasa Google) dengan seed tetap
agar hasilnya deterministik. Heuristik kata umum menjadi cadangan bila teks
terlalu pendek atau pustaka gagal.
"""

from langdetect import DetectorFactory, LangDetectException, detect_langs

from csais.db import get_connection
from csais.text import remove_publisher, split_publisher

DetectorFactory.seed = 0

MIN_TEXT_LENGTH = 20
UPDATE_BATCH_SIZE = 5000

_INDONESIAN_WORDS = {
    "dan", "yang", "dari", "dengan", "untuk", "serangan", "siber", "keamanan",
    "peretas", "ini", "itu", "akan", "telah",
}
_ENGLISH_WORDS = {
    "the", "and", "of", "with", "cyber", "security", "attack", "hackers", "this",
    "that", "from",
}


def _heuristic(text):
    """Deteksi id/en sederhana berdasarkan kata umum; 'unknown' bila seimbang."""
    words = set(text.lower().split())
    indonesian_score = len(words & _INDONESIAN_WORDS)
    english_score = len(words & _ENGLISH_WORDS)
    if indonesian_score > english_score:
        return "id", 0.60
    if english_score > indonesian_score:
        return "en", 0.60
    return "unknown", 0.30


def detect_language(text):
    """(kode bahasa ISO 639-1, keyakinan 0-1) untuk teks; 'unknown' bila gagal."""
    text = (text or "").strip()
    if len(text) < MIN_TEXT_LENGTH:
        return _heuristic(text)
    try:
        candidates = detect_langs(text)
    except LangDetectException:
        return _heuristic(text)
    if not candidates:
        return _heuristic(text)
    best = candidates[0]
    return best.lang, round(best.prob, 4)


def article_text(title, summary):
    """Teks artikel tanpa nama media, agar nama media tidak membiaskan deteksi."""
    headline, publisher = split_publisher(title)
    return f"{headline} {remove_publisher(summary, publisher)}".strip()


def redetect_all():
    """Deteksi ulang bahasa seluruh artikel di database; kembalikan jumlah baris."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT article_id, title, summary FROM articles ORDER BY article_id")
    rows = cursor.fetchall()

    updates = []
    for index, (article_id, title, summary) in enumerate(rows, start=1):
        language, confidence = detect_language(article_text(title, summary))
        updates.append((language, confidence, article_id))
        if index % 20000 == 0:
            print(f"   {index} / {len(rows)} artikel dideteksi...")

    for start in range(0, len(updates), UPDATE_BATCH_SIZE):
        cursor.executemany(
            "UPDATE articles SET language = ?, language_confidence = ? "
            "WHERE article_id = ?",
            updates[start : start + UPDATE_BATCH_SIZE],
        )
        conn.commit()
    conn.close()
    return len(updates)


def language_distribution():
    """Daftar (bahasa, jumlah) terurut dari terbanyak."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT language, COUNT(*) FROM articles GROUP BY language ORDER BY 2 DESC"
    ).fetchall()
    conn.close()
    return rows
