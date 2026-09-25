"""Pengujian csais/text.py: normalisasi, tokenisasi, pencocokan kata kunci, nama media."""

import pytest

from csais import text


def test_normalize_text_lowercases_and_collapses_whitespace():
    assert text.normalize_text("  Hello   WORLD \n foo ") == "hello world foo"
    assert text.normalize_text(None) == ""
    assert text.normalize_text(123) == "123"


def test_tokenize_min_length_and_alphanumeric_only():
    tokens = text.tokenize("Cyber-attack on Bank_of PNG 2025 ab")
    assert tokens == {"cyber", "attack", "bank", "png", "2025"}
    assert text.tokenize("a bb cc", min_length=2) == {"bb", "cc"}
    assert text.tokenize("") == set()
    assert text.tokenize(None) == set()


def test_jaccard_index():
    assert text.jaccard_index({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)
    assert text.jaccard_index({"a"}, {"a"}) == 1.0
    assert text.jaccard_index(set(), {"a"}) == 0.0
    assert text.jaccard_index({"a"}, set()) == 0.0


@pytest.mark.parametrize(
    "haystack,expected",
    [
        ("he forced the door", False),
        ("open source project", False),
        ("critical rce bug fixed", True),
        ("RCE in router firmware", True),
    ],
)
def test_keyword_rce_respects_word_boundaries(haystack, expected):
    assert text.contains_keyword(haystack, "rce") is expected


def test_keyword_ending_with_punctuation_has_no_trailing_boundary():
    assert text.contains_keyword("fixes cve-2024-1234 today", "cve-")
    assert not text.contains_keyword("the cve list", "cve-")


@pytest.mark.parametrize("word", ["attack", "attacks", "attacked", "attacking"])
def test_keyword_matches_simple_inflections(word):
    assert text.contains_keyword(f"the {word} happened", "attack")


def test_keyword_inflection_limits():
    assert text.contains_keyword("breaches reported", "breach")
    # "attacker" bukan bentuk turunan sederhana yang didukung pola
    assert not text.contains_keyword("the attacker fled", "attack")


def test_keyword_matches_in_non_latin_text():
    assert text.contains_keyword("昨日サイバー攻撃が発生した", "サイバー攻撃")
    assert text.contains_keyword("Произошла кибератака на банк", "кибератака")


def test_keyword_pattern_is_cached_and_case_insensitive():
    assert text.keyword_pattern("Ransomware") is text.keyword_pattern("Ransomware")
    assert text.contains_keyword("RANSOMWARE hits clinic", "ransomware")


def test_find_keywords_preserves_list_order():
    found = text.find_keywords(
        "spear phishing and ransomware", ["ransomware", "phishing", "spear phishing", "ddos"]
    )
    assert found == ["ransomware", "phishing", "spear phishing"]


def test_drop_overlapping_keywords():
    assert text.drop_overlapping_keywords(["zero-day", "zero-day exploit", "exploit"]) == [
        "zero-day exploit"
    ]
    assert text.drop_overlapping_keywords(["ransomware", "phishing"]) == [
        "ransomware",
        "phishing",
    ]
    assert text.drop_overlapping_keywords([]) == []


@pytest.mark.parametrize(
    "title,headline,publisher",
    [
        (
            "Smiths Group hit by cyber attack - Reuters",
            "Smiths Group hit by cyber attack",
            "Reuters",
        ),
        ("Headline here – The Register", "Headline here", "The Register"),
        ("Headline here | BBC News", "Headline here", "BBC News"),
        ("Zero-day flaw exploited - BleepingComputer", "Zero-day flaw exploited", "BleepingComputer"),
        ("Just a headline", "Just a headline", ""),
        ("", "", ""),
        (None, "", ""),
    ],
)
def test_split_publisher(title, headline, publisher):
    assert text.split_publisher(title) == (headline, publisher)


def test_strip_publisher_suffix():
    assert text.strip_publisher_suffix("Headline - Publisher") == "Headline"
    assert text.strip_publisher_suffix("No publisher") == "No publisher"


def test_remove_publisher():
    assert text.remove_publisher("Summary text here - Reuters", "Reuters") == "Summary text here"
    assert text.remove_publisher("Summary text here Reuters", "Reuters") == "Summary text here"
    assert text.remove_publisher("Summary text here", "Reuters") == "Summary text here"
    assert text.remove_publisher("Summary text", "") == "Summary text"
    assert text.remove_publisher(None, "Reuters") == ""
