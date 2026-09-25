"""Pengujian csais/v02_relevance_detection.py: analisis relevansi berbasis kata kunci."""

import pytest

from csais import v02_relevance_detection as v02

RESULT_KEYS = {
    "label", "score", "confidence", "method",
    "attack_matches", "event_matches", "non_incident_matches",
}


def test_clear_incident_headline_is_relevant():
    result = v02.analyze_relevance(
        "Ransomware attack hits Rivers Casino Philadelphia, data stolen",
        "The casino said customer data was stolen in the attack.",
    )
    assert result["label"] == "RELEVANT"
    assert result["score"] >= v02.RELEVANT_THRESHOLD
    assert "ransomware attack" in result["attack_matches"]
    assert "ransomware" not in result["attack_matches"]  # tumpang tindih dibuang
    assert result["event_matches"]
    assert result["method"] == "RULE_BASED"
    assert set(result) == RESULT_KEYS


def test_webinar_training_text_is_not_relevant():
    result = v02.analyze_relevance(
        "Free webinar: ransomware awareness training for employees",
        "Join our webinar to learn the basics.",
    )
    assert result["label"] == "NOT_RELEVANT"
    assert {"webinar", "training"} <= set(result["non_incident_matches"])


def test_non_incident_indicators_lower_the_score():
    plain = v02.analyze_relevance("Hospital hit by ransomware, systems disrupted", "")
    penalized = v02.analyze_relevance(
        "Hospital hit by ransomware, systems disrupted", "Watch our webinar."
    )
    assert plain["label"] == "RELEVANT"
    assert penalized["score"] == pytest.approx(plain["score"] - 0.15)


def test_weak_keyword_without_cyber_context_is_not_relevant():
    result = v02.analyze_relevance(
        "Blood worm moon eclipse tonight", "Skywatchers can see the eclipse after sunset."
    )
    assert result["label"] == "NOT_RELEVANT"
    assert result["attack_matches"] == []
    assert result["score"] == 0.0


def test_weak_keyword_with_cyber_context_counts():
    result = v02.analyze_relevance("New Linux backdoor targets governments", "")
    assert result["label"] != "NOT_RELEVANT"
    assert result["attack_matches"] == ["backdoor"]


def test_empty_text_is_not_relevant():
    result = v02.analyze_relevance("", None)
    assert result["label"] == "NOT_RELEVANT"
    assert result["score"] == 0.0
    assert result["confidence"] == 0.0
    assert result["attack_matches"] == []


def test_confidence_is_distance_from_midpoint():
    result = v02.analyze_relevance("Hackers breached the bank in a phishing campaign", "")
    assert result["confidence"] == pytest.approx(abs(result["score"] - 0.5) * 2, abs=1e-4)
    assert 0.0 <= result["confidence"] <= 1.0
    assert 0.0 <= result["score"] <= 1.0


def test_find_matches_drops_overlapping_keywords():
    matches = v02.find_matches("spear phishing campaign hits bank", v02.ATTACK_KEYWORDS)
    assert "spear phishing" in matches
    assert "phishing" not in matches


def test_find_matches_uses_word_boundaries():
    assert v02.find_matches("the door was forced open", ["rce"]) == []
    assert v02.find_matches("an rce flaw", ["rce"]) == ["rce"]


def test_weak_keywords_are_subset_of_attack_keywords():
    # Prasyarat yang didokumentasikan di csais/data/README.md
    assert v02.WEAK_ATTACK_KEYWORDS <= set(v02.ATTACK_KEYWORDS)


# --- Kosakata Indonesia ---
def test_indonesian_incident_headline_is_relevant():
    result = v02.analyze_relevance(
        "Hacker Diduga Jebol Server Telkomsel, Muncul Penjualan Data di Dark Web", ""
    )
    assert result["label"] == "RELEVANT"
    assert "jebol server" in result["attack_matches"]


def test_indonesian_awareness_article_is_not_relevant():
    result = v02.analyze_relevance(
        "Waspada Link Video Viral, Jangan Klik: Modus Phishing dan Malware",
        "Kenali cara menghindari jebakan phishing.",
    )
    assert result["label"] == "NOT_RELEVANT"
    assert len(result["non_incident_matches"]) >= 2


def test_two_non_incident_indicators_double_the_penalty():
    one = v02.analyze_relevance("Hospital hit by ransomware, systems disrupted", "Watch our webinar.")
    two = v02.analyze_relevance(
        "Hospital hit by ransomware, systems disrupted", "Watch our webinar and training."
    )
    assert two["score"] == pytest.approx(one["score"] - 0.15)


def test_indonesian_weak_leak_word_needs_cyber_context():
    plain = v02.analyze_relevance("Pipa air bocor di Jakarta Selatan", "")
    assert plain["attack_matches"] == []
    cyber = v02.analyze_relevance("Data pelanggan diduga bocor, akun pengguna terancam", "")
    assert cyber["attack_matches"]
