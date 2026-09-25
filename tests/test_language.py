"""Pengujian csais/language.py: deteksi bahasa dengan langdetect dan heuristik cadangan."""

import pytest

from csais import language


def test_detect_language_english_sentence():
    code, confidence = language.detect_language(
        "The hackers breached the company's network and stole customer data last week."
    )
    assert code == "en"
    assert 0.5 < confidence <= 1.0


def test_detect_language_indonesian_sentence():
    code, confidence = language.detect_language(
        "Peretas membobol jaringan perusahaan dan mencuri data pelanggan pekan lalu."
    )
    assert code == "id"
    assert 0.5 < confidence <= 1.0


@pytest.mark.parametrize(
    "short_text,expected",
    [
        ("serangan siber", ("id", 0.60)),
        ("cyber attack", ("en", 0.60)),
        ("hello", ("unknown", 0.30)),
        ("", ("unknown", 0.30)),
        (None, ("unknown", 0.30)),
    ],
)
def test_short_text_falls_back_to_word_heuristic(short_text, expected):
    assert len((short_text or "").strip()) < language.MIN_TEXT_LENGTH
    assert language.detect_language(short_text) == expected


def test_detect_language_is_deterministic():
    sentence = "Serangan siber terhadap bank ini menyebabkan kebocoran data nasabah."
    assert language.detect_language(sentence) == language.detect_language(sentence)


def test_article_text_strips_publisher_from_title_and_summary():
    assert language.article_text("Headline - Reuters", "Summary body Reuters") == (
        "Headline Summary body"
    )
