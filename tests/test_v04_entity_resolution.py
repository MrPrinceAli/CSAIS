"""Pengujian csais/v04_entity_resolution.py: normalisasi, similarity, alias, cache entity."""

import pytest

from csais import v04_entity_resolution as v04


@pytest.fixture
def empty_cache(monkeypatch):
    """Cache entity di memori yang bersih, terisolasi dari tes lain."""
    cache = {}
    monkeypatch.setattr(v04, "_ENTITY_CACHE", cache)
    return cache


def test_normalize_entity_name():
    assert v04.normalize_entity_name('  "Bank Mandiri" (Persero), Tbk;  ') == (
        "bank mandiri persero tbk"
    )
    assert v04.normalize_entity_name(None) == ""
    assert v04.normalize_entity_name("  APT28  ") == "apt28"


def test_generate_entity_id_is_deterministic_and_normalized():
    entity_id = v04.generate_entity_id("ORGANIZATION", "Microsoft")
    assert entity_id == v04.generate_entity_id("ORGANIZATION", "  MICROSOFT ")
    assert len(entity_id) == 20
    int(entity_id, 16)  # heksadesimal
    assert entity_id != v04.generate_entity_id("THREAT_ACTOR", "Microsoft")


def test_levenshtein_distance():
    assert v04.levenshtein_distance("kitten", "sitting") == 3
    assert v04.levenshtein_distance("", "abc") == 3
    assert v04.levenshtein_distance("abc", "") == 3
    assert v04.levenshtein_distance("same", "same") == 0
    assert v04.levenshtein_distance("flaw", "lawn") == v04.levenshtein_distance("lawn", "flaw")


def test_calculate_similarity():
    assert v04.calculate_similarity("Microsoft", "microsoft") == 1.0
    assert v04.calculate_similarity("", "Microsoft") == 0.0
    close = v04.calculate_similarity("Rivers Casino Philadelphia", "Rivers Casino Philadelphia Inc")
    far = v04.calculate_similarity("Microsoft", "Google")
    assert 0.0 <= far < close < 1.0
    expected = (
        v04.jaccard_similarity("Rivers Casino Philadelphia", "Rivers Casino Philadelphia Inc")
        + v04.character_similarity("Rivers Casino Philadelphia", "Rivers Casino Philadelphia Inc")
    ) / 2
    assert close == pytest.approx(expected)


def test_build_alias_index_types():
    index = v04.build_alias_index()
    assert index["fancy bear"] == ("THREAT_ACTOR", "APT28")
    assert index["microsoft corp"] == ("ORGANIZATION", "Microsoft")
    assert index["u.s."] == ("LOCATION", "United States")
    assert all(key == v04.normalize_entity_name(key) for key in index)


def test_resolve_known_alias_requires_matching_type():
    index = v04.build_alias_index()
    assert v04.resolve_known_alias("THREAT_ACTOR", "Fancy Bear", index) == "APT28"
    assert v04.resolve_known_alias("ORGANIZATION", "Fancy Bear", index) is None
    assert v04.resolve_known_alias("ORGANIZATION", "Microsoft Corp.", index) == "Microsoft"
    assert v04.resolve_known_alias("ORGANIZATION", "Zzz Corp", index) is None


def test_extract_field_mentions_splits_and_ignores_unknown():
    assert v04.extract_field_mentions("Smiths Group, Qilin; Akira | Medusa") == [
        "Smiths Group", "Qilin", "Akira", "Medusa",
    ]
    assert v04.extract_field_mentions("UNKNOWN") == []
    assert v04.extract_field_mentions(None) == []
    assert v04.extract_field_mentions("   ") == []
    assert v04.extract_field_mentions("x" * (v04.MAX_ENTITY_NAME_LENGTH + 1)) == []


def test_create_entity_inserts_once_and_fills_cache(temp_conn, empty_cache):
    v04.create_tables(temp_conn)
    first = v04.create_entity(temp_conn, "ORGANIZATION", "Smiths Group", "NEW_ENTITY")
    second = v04.create_entity(temp_conn, "ORGANIZATION", "smiths group", "NEW_ENTITY")
    assert first == second == v04.generate_entity_id("ORGANIZATION", "Smiths Group")
    rows = temp_conn.execute(
        "SELECT entity_id, entity_type, canonical_name, normalized_name FROM v04_entities"
    ).fetchall()
    assert rows == [(first, "ORGANIZATION", "Smiths Group", "smiths group")]
    assert empty_cache["ORGANIZATION"]["by_name"]["smiths group"]["entity_id"] == first


def test_find_existing_entity_exact_match(temp_conn, empty_cache):
    v04.create_tables(temp_conn)
    entity_id = v04.create_entity(
        temp_conn, "ORGANIZATION", "Rivers Casino Philadelphia", "NEW_ENTITY"
    )
    match = v04.find_existing_entity("ORGANIZATION", "  rivers casino PHILADELPHIA ")
    assert match == {
        "entity_id": entity_id,
        "canonical_name": "Rivers Casino Philadelphia",
        "score": 1.0,
        "method": "EXACT_MATCH",
    }
    # tipe berbeda atau mention kosong tidak pernah cocok
    assert v04.find_existing_entity("THREAT_ACTOR", "Rivers Casino Philadelphia") is None
    assert v04.find_existing_entity("ORGANIZATION", "") is None


def test_find_existing_entity_fuzzy_match_threshold(temp_conn, empty_cache):
    v04.create_tables(temp_conn)
    long_name = "Ministry of Communication and Digital Affairs Indonesia"
    entity_id = v04.create_entity(temp_conn, "ORGANIZATION", long_name, "NEW_ENTITY")
    v04.create_entity(temp_conn, "ORGANIZATION", "Smiths Group", "NEW_ENTITY")

    match = v04.find_existing_entity(
        "ORGANIZATION", "Ministry of Communication and Digital Affairs Indonesa"
    )
    assert match is not None
    assert match["entity_id"] == entity_id
    assert match["method"] == "FUZZY_MATCH"
    assert match["score"] >= v04.FUZZY_THRESHOLD
    # skor "Smiths Group PLC" vs "Smiths Group" hanya ~0.71, di bawah ambang 0.85
    assert v04.find_existing_entity("ORGANIZATION", "Smiths Group PLC") is None


def test_load_entity_cache_reads_database(temp_conn, empty_cache):
    v04.create_tables(temp_conn)
    v04.create_entity(temp_conn, "THREAT_ACTOR", "Qilin", "KNOWN_ALIAS")
    empty_cache.clear()
    assert v04.find_existing_entity("THREAT_ACTOR", "Qilin") is None
    v04.load_entity_cache(temp_conn)
    assert v04.find_existing_entity("THREAT_ACTOR", "qilin")["method"] == "EXACT_MATCH"


def test_resolve_mention_alias_new_and_existing(temp_conn, empty_cache):
    v04.create_tables(temp_conn)
    index = v04.build_alias_index()

    alias = v04.resolve_mention(temp_conn, "THREAT_ACTOR", "Fancy Bear", index)
    assert alias["canonical_name"] == "APT28"
    assert alias["method"] == "KNOWN_ALIAS"
    assert alias["entity_id"] == v04.generate_entity_id("THREAT_ACTOR", "APT28")

    new = v04.resolve_mention(temp_conn, "ORGANIZATION", "Smiths Group", index)
    assert new["method"] == "NEW_ENTITY"
    again = v04.resolve_mention(temp_conn, "ORGANIZATION", "smiths group", index)
    assert again["method"] == "EXACT_MATCH"
    assert again["entity_id"] == new["entity_id"]

    # alias pelaku ancaman tidak dipakai untuk tipe ORGANIZATION
    wrong_type = v04.resolve_mention(temp_conn, "ORGANIZATION", "Fancy Bear", index)
    assert wrong_type["method"] == "NEW_ENTITY"
    assert wrong_type["canonical_name"] == "Fancy Bear"
    assert v04.resolve_mention(temp_conn, "ORGANIZATION", "   ", index) is None


def test_save_entity_mention_increments_count_once(temp_conn, empty_cache):
    v04.create_tables(temp_conn)
    entity_id = v04.create_entity(temp_conn, "ORGANIZATION", "Smiths Group", "NEW_ENTITY")
    args = (
        temp_conn, 1, "ORGANIZATION", "Smiths Group", "Smiths Group",
        entity_id, 1.0, 1.0, "NEW_ENTITY",
    )
    assert v04.save_entity_mention(*args) == 1
    assert v04.save_entity_mention(*args) == 0
    count = temp_conn.execute(
        "SELECT mention_count FROM v04_entities WHERE entity_id = ?", (entity_id,)
    ).fetchone()[0]
    assert count == 1
    version = temp_conn.execute(
        "SELECT pipeline_version FROM v04_entity_mentions"
    ).fetchone()[0]
    assert version
