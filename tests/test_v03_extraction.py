"""Pengujian csais/v03_information_extraction.py: ekstraksi kata kunci dan regex."""

import pytest

from csais import v03_information_extraction as v03


def test_extract_attack_type_joins_categories_in_dictionary_order():
    assert v03.extract_attack_type("a ransomware attack and phishing emails") == (
        "RANSOMWARE, PHISHING"
    )
    assert v03.extract_attack_type("sunny day at the beach") == "UNKNOWN"


def test_extract_attack_method():
    assert v03.extract_attack_method("phishing emails delivered malware") == "PHISHING, MALWARE"
    assert v03.extract_attack_method("nothing here") == "UNKNOWN"


def test_extract_target_sector_and_group():
    assert v03.extract_target_sector("the hospital and a bank") == "HEALTHCARE, FINANCE"
    assert v03.extract_target_sector("nothing") == "UNKNOWN"
    assert v03.extract_target_group("targeting students and employees") == "EMPLOYEES, STUDENTS"


def test_extract_location_and_impact():
    assert v03.extract_location("attack in indonesia and singapore") == "Indonesia, Singapore"
    assert v03.extract_location("nowhere in particular") == "UNKNOWN"
    assert v03.extract_impact("services disrupted and data stolen") == (
        "DATA_THEFT, SERVICE_DISRUPTION"
    )


@pytest.mark.parametrize(
    "headline,expected",
    [
        ("Smiths Group hit by cyber attack", "Smiths Group"),
        ("Ransomware attack hits Rivers Casino Philadelphia", "Rivers Casino Philadelphia"),
        ("Bank of PNG confirms cyber incident", "Bank of PNG"),
        ("Ransomware attack on the University of Manchester", "University of Manchester"),
        ("Marks & Spencer suffered a ransomware attack", "Marks & Spencer"),
    ],
)
def test_extract_target_organization_from_headline(headline, expected):
    assert v03.extract_target_organization(headline, "") == expected


@pytest.mark.parametrize(
    "headline",
    [
        "Hackers hit hospitals",
        "Dutch university disrupted",
        "Indonesia hit by cyber attack",
        "Cyberattack on Germany",
        "",
    ],
)
def test_extract_target_organization_rejects_generic_and_country_names(headline):
    assert v03.extract_target_organization(headline, "") == "UNKNOWN"


def test_extract_target_organization_falls_back_to_summary():
    assert v03.extract_target_organization(
        "Big news today", "Yesterday, Acme Corp was hacked by criminals."
    ) == "Acme Corp"
    assert v03.extract_target_organization(None, None) == "UNKNOWN"


@pytest.mark.parametrize(
    "sentence,expected",
    [
        ("Qilin ransomware claims attack on Rivers Casino Philadelphia", "Qilin"),
        ("Medusa ransomware group claims responsibility for the breach", "Medusa"),
        ("hacktivist group Sector 16 targeting water utilities", "Sector 16"),
        ("Fancy Bear linked to new espionage campaign", "Fancy Bear"),
        ("LockBit ransomware hits hospital", "LockBit"),
        ("The threat actor known as Scattered Spider strikes again", "Scattered Spider"),
    ],
)
def test_extract_threat_actor_positive(sentence, expected):
    assert v03.extract_threat_actor(sentence) == expected


@pytest.mark.parametrize(
    "sentence",
    [
        "AI-powered ransomware group emerges",
        "ransomware groups abuse Microsoft Teams for initial access",
        "no actors mentioned here",
    ],
)
def test_extract_threat_actor_negative(sentence):
    assert v03.extract_threat_actor(sentence) == "UNKNOWN"


def test_extract_threat_actor_caps_at_three_and_deduplicates():
    result = v03.extract_threat_actor(
        "LockBit, Qilin, Akira ransomware, Medusa ransomware and LockBit again"
    )
    actors = result.split(", ")
    assert len(actors) == 3
    assert len(set(actors)) == 3
    assert "LockBit" in actors


@pytest.mark.parametrize(
    "sentence,expected",
    [
        ("breach on 2025-01-15 confirmed", "2025-01-15"),
        ("breach on 15/01/2025 confirmed", "2025-01-15"),
        ("breach on 13-02-2025 confirmed", "2025-02-13"),
        ("breach on 01/15/2025 confirmed", "2025-01-15"),  # d/m tidak valid -> m/d
        ("breach on 2024-99-99 confirmed", "UNKNOWN"),
        ("no date here", "UNKNOWN"),
    ],
)
def test_extract_attack_date(sentence, expected):
    assert v03.extract_attack_date(sentence) == expected


def test_extract_indicators_normalizes_case_and_deduplicates():
    sample = (
        "exploits cve-2024-1234 and CVE-2023-99999; hash D41D8CD98F00B204E9800998ECF8427E "
        "and da39a3ee5e6b4b0d3255bfef95601890afd80709 and cve-2024-1234 again"
    )
    assert v03.extract_indicators(sample) == (
        "CVE-2024-1234, CVE-2023-99999, d41d8cd98f00b204e9800998ecf8427e, "
        "da39a3ee5e6b4b0d3255bfef95601890afd80709"
    )
    assert v03.extract_indicators("nothing here") == "UNKNOWN"


def test_extract_indicators_sha256():
    digest = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert v03.extract_indicators(f"hash {digest}") == digest


def test_calculate_extraction_confidence():
    assert v03.calculate_extraction_confidence(
        "RANSOMWARE", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"
    ) == 0.2
    assert v03.calculate_extraction_confidence("A", "B", "C", "D", "E") == 1.0
    assert v03.calculate_extraction_confidence(*(["UNKNOWN"] * 5)) == 0.0


def test_extract_information_end_to_end():
    info = v03.extract_information(
        7,
        "Qilin ransomware claims attack on Rivers Casino Philadelphia - BleepingComputer",
        "The Qilin ransomware gang has claimed the attack on Rivers Casino Philadelphia "
        "on 2025-01-15, with customer data stolen. BleepingComputer",
        None,
    )
    assert set(info) == {
        "article_id", "attack_type", "attack_method", "target", "target_organization",
        "target_sector", "target_group", "location", "attack_date", "threat_actor",
        "impact", "indicator", "extraction_confidence", "extraction_method",
        "field_confidence",
    }
    assert info["article_id"] == 7
    assert info["attack_type"] == "RANSOMWARE, DATA_THEFT"
    assert info["target"] == info["target_organization"] == "Rivers Casino Philadelphia"
    assert info["threat_actor"] == "Qilin"
    assert info["attack_date"] == "2025-01-15"
    assert info["impact"] == "DATA_THEFT"
    assert info["indicator"] == "UNKNOWN"
    assert info["extraction_method"] == "RULE_BASED"
    assert info["extraction_confidence"] == pytest.approx(0.4)


@pytest.mark.parametrize(
    "sentence",
    [
        # keterangan sebelum kata kerja bukan nama
        "Threat Actor Allegedly Claims 20 Million Records Stolen from Company X",
        # judul seksi di isi artikel tidak boleh menyambung ke baris berikutnya
        "Campaign Overview\nThreat actors behind this campaign used phishing.",
        "the threat actor\nCampaign Overview\nused phishing",
    ],
)
def test_extract_threat_actor_rejects_adverbs_and_section_headings(sentence):
    assert v03.extract_threat_actor(sentence) == "UNKNOWN"


def test_extract_target_organization_ignores_month_names():
    assert v03.extract_target_organization("Dec 28 was hit by a cyberattack", "") == "UNKNOWN"
    assert (
        v03.extract_target_organization("PowerSchool was hit by a cyberattack on Dec 28", "")
        == "PowerSchool"
    )


def test_extract_target_organization_does_not_cross_line_breaks():
    text = "Latest News\nAcme Corp was hacked last week."
    assert v03.extract_target_organization("", "", text) == "Acme Corp"
