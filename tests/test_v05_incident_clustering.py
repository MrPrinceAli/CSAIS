"""Pengujian csais/v05_incident_clustering.py: similarity, hard constraint, sinyal identitas."""

import re
from datetime import datetime, timezone

import pytest

from csais import v05_incident_clustering as v05


@pytest.fixture
def token_df(monkeypatch):
    """Frekuensi dokumen token buatan, terisolasi dari run() di tes integrasi."""
    df = {"smiths": 3, "attacked": 100, "png": 2, "rivers": 2, "casino": 2, "microsoft": 500}
    monkeypatch.setattr(v05, "_TOKEN_DF", df)
    monkeypatch.setattr(v05, "_RARE_DF_LIMIT", 5)
    monkeypatch.setattr(v05, "_TARGET_DF_LIMIT", 20)
    return df


def make_article(**overrides):
    """Dict artikel seperti keluaran prepare_article, dengan nilai default."""
    tokens = overrides.pop("tokens", None)
    published = overrides.pop("published", "2025-03-01T08:00:00+00:00")
    parsed = v05.parse_date(published)
    article = {
        "article_id": 1,
        "article_uid": "uid-1",
        "attack_type": "network_intrusion",
        "target": "smiths group",
        "target_entity_id": "ent-smiths",
        "threat_actor": None,
        "threat_actor_entity_id": None,
        "location": "united kingdom",
        "attack_date": None,
        "attack_method": None,
        "tokens": tokens if tokens is not None else {"smiths", "group", "engineering", "firm", "hit"},
        "published": parsed,
        "published_date": parsed.isoformat() if parsed else None,
    }
    article.update(overrides)
    return article


def make_incident(**overrides):
    """Dict incident dengan kolom persis INCIDENT_COLUMNS."""
    incident = {
        "incident_id": "INCIDENT_TEST",
        "attack_type": "network_intrusion",
        "target": "smiths group",
        "target_entity_id": "ent-smiths",
        "threat_actor": None,
        "threat_actor_entity_id": None,
        "location": "united kingdom",
        "attack_date": None,
        "attack_method": None,
        "document_count": 1,
        "incident_confidence": 1.0,
        "anchor_text": "engineering firm group hit smiths",
        "anchor_published_date": "2025-03-01T08:00:00+00:00",
        "last_published_date": "2025-03-01T08:00:00+00:00",
    }
    incident.update(overrides)
    assert set(incident) == set(v05.INCIDENT_COLUMNS)
    return incident


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, True), ("", True), ("UNKNOWN", True), (" n/a ", True), ("-", True),
        ("Acme", False), ("0", False),
    ],
)
def test_is_unknown(value, expected):
    assert v05.is_unknown(value) is expected


def test_normalize_value():
    assert v05.normalize_value("  Smiths  GROUP ") == "smiths group"
    assert v05.normalize_value("UNKNOWN") is None
    assert v05.normalize_value(None) is None


def test_parse_date():
    utc = timezone.utc
    assert v05.parse_date("2025-01-15T10:00:00Z") == datetime(2025, 1, 15, 10, tzinfo=utc)
    assert v05.parse_date("2025-01-15") == datetime(2025, 1, 15, tzinfo=utc)
    assert v05.parse_date("2025-01-15T10:00:00") == datetime(2025, 1, 15, 10, tzinfo=utc)
    assert v05.parse_date("yesterday") is None
    assert v05.parse_date("UNKNOWN") is None
    assert v05.parse_date(None) is None


def test_calculate_date_similarity():
    assert v05.calculate_date_similarity("2025-01-01", "2025-01-01") == 1.0
    assert v05.calculate_date_similarity("2025-01-01", "2025-01-08") == pytest.approx(0.5)
    assert v05.calculate_date_similarity("2025-01-01", "2025-03-01") == 0.0
    assert v05.calculate_date_similarity("2025-01-01", "unknown") is None
    assert v05.calculate_date_similarity("not a date", "2025-01-01") is None


def test_attack_type_set():
    assert v05.attack_type_set("ransomware, data_breach, ") == {"ransomware", "data_breach"}
    assert v05.attack_type_set(None) == set()
    assert v05.attack_type_set("") == set()


def test_calculate_field_similarity():
    assert v05.calculate_field_similarity("Smiths Group", "smiths group") == 1.0
    assert v05.calculate_field_similarity("smiths group plc", "smiths group") == pytest.approx(2 / 3)
    assert v05.calculate_field_similarity("x", None) is None
    assert v05.calculate_field_similarity("UNKNOWN", "x") is None


def test_text_tokens_removes_publisher_and_stopwords():
    tokens = v05.text_tokens(
        "Smiths Group hit by cyber attack - Reuters",
        "The engineering firm was attacked. Reuters",
    )
    assert tokens == {"smiths", "group", "hit", "engineering", "firm", "attacked"}


def test_distinctive_tokens_drops_generic_and_frequent(token_df):
    assert v05.distinctive_tokens("Smiths Group") == {"smiths"}
    assert v05.distinctive_tokens("Microsoft") == set()  # DF 500 > batas 20
    assert v05.distinctive_tokens("The Hospital Group") == set()  # hanya kata generik
    assert v05.distinctive_tokens(None) == set()


def test_shared_rare_tokens(token_df):
    tokens_a = {"smiths", "attacked", "png", "rivers", "novel", "group"}
    tokens_b = {"smiths", "attacked", "png", "rivers", "novel"}
    # "attacked" terlalu sering (100 > 5), "png" terlalu pendek, "novel" tidak ada di korpus
    assert v05.shared_rare_tokens(tokens_a, tokens_b) == {"smiths", "rivers"}
    assert v05.shared_rare_tokens(set(), tokens_b) == set()


def test_generate_incident_id_deterministic():
    incident_id = v05.generate_incident_id("abc")
    assert incident_id == v05.generate_incident_id("abc")
    assert re.fullmatch(r"INCIDENT_[0-9A-F]{12}", incident_id)
    assert incident_id != v05.generate_incident_id("abd")


def test_incident_columns_match_table(temp_conn):
    v05.create_tables(temp_conn)
    columns = {row[1] for row in temp_conn.execute("PRAGMA table_info(v05_incidents)")}
    assert set(v05.INCIDENT_COLUMNS) <= columns


def test_passes_hard_constraints_accepts_compatible_article():
    assert v05.passes_hard_constraints(make_article(), make_incident()) is True
    # tipe serangan tidak diketahui di satu sisi tidak menghalangi
    assert v05.passes_hard_constraints(make_article(attack_type=None), make_incident()) is True
    # jenis serangan cukup beririsan sebagian
    assert v05.passes_hard_constraints(
        make_article(attack_type="ransomware, data_theft"),
        make_incident(attack_type="data_theft"),
    ) is True


@pytest.mark.parametrize(
    "article_overrides,incident_overrides",
    [
        ({"target_entity_id": "ent-other"}, {}),
        ({"threat_actor_entity_id": "ta-1"}, {"threat_actor_entity_id": "ta-2"}),
        ({"attack_type": "ransomware"}, {"attack_type": "phishing, ddos"}),
        ({"attack_date": "2025-01-01"}, {"attack_date": "2025-03-01"}),
        ({"published": "2025-04-15T00:00:00+00:00"}, {}),  # terbit jauh setelah incident
        ({"published": "2025-01-15T00:00:00+00:00"}, {}),  # terbit jauh sebelum incident
    ],
    ids=["target-entity", "actor-entity", "attack-type", "attack-date", "published-after", "published-before"],
)
def test_passes_hard_constraints_rejects_conflicts(article_overrides, incident_overrides):
    assert v05.passes_hard_constraints(
        make_article(**article_overrides), make_incident(**incident_overrides)
    ) is False


def test_has_identity_signal_same_target_entity(token_df):
    details = {"target": 1.0, "actor": None, "text": 0.1}
    assert v05.has_identity_signal(make_article(), make_incident(), details) is True


def test_has_identity_signal_generic_target_is_not_enough(token_df):
    article = make_article(
        target="hospital group", target_entity_id="ent-h",
        tokens={"hospital", "group", "outage"},
    )
    incident = make_incident(
        target="hospital group", target_entity_id="ent-h",
        anchor_text="hospital group ransomware",
    )
    details = {"target": 1.0, "actor": None, "text": 0.5}
    assert v05.has_identity_signal(article, incident, details) is False


def test_has_identity_signal_target_name_in_other_text(token_df):
    details = {"target": None, "actor": None, "text": 0.1}
    # target artikel tidak diketahui, tetapi nama target incident muncul di teks artikel
    article = make_article(
        target=None, target_entity_id=None, tokens={"smiths", "engineering", "update"}
    )
    assert v05.has_identity_signal(article, make_incident(), details) is True
    # sebaliknya: nama target artikel muncul di anchor text incident
    article = make_article(
        target="rivers casino", target_entity_id=None, tokens={"casino", "breach"}
    )
    incident = make_incident(
        target=None, target_entity_id=None,
        anchor_text="rivers casino philadelphia ransomware",
    )
    assert v05.has_identity_signal(article, incident, details) is True


def test_has_identity_signal_shared_rare_token(token_df):
    details = {"target": None, "actor": None, "text": 0.2}
    article = make_article(target=None, target_entity_id=None, tokens={"rivers", "outage"})
    incident = make_incident(target=None, target_entity_id=None, anchor_text="rivers ransomware")
    assert v05.has_identity_signal(article, incident, details) is True
    # token yang terlalu sering di korpus bukan bukti
    article = make_article(target=None, target_entity_id=None, tokens={"attacked", "outage"})
    incident = make_incident(target=None, target_entity_id=None, anchor_text="attacked ransomware")
    assert v05.has_identity_signal(article, incident, details) is False


def test_has_identity_signal_same_actor_requires_text_similarity(token_df):
    article = make_article(
        target=None, target_entity_id=None, threat_actor_entity_id="ta-qilin", tokens={"outage"}
    )
    incident = make_incident(
        target=None, target_entity_id=None, threat_actor_entity_id="ta-qilin",
        anchor_text="ransomware",
    )
    enough = {"target": None, "actor": 1.0, "text": v05.MIN_TEXT_SIMILARITY_WITH_ACTOR}
    too_low = {"target": None, "actor": 1.0, "text": 0.1}
    assert v05.has_identity_signal(article, incident, enough) is True
    assert v05.has_identity_signal(article, incident, too_low) is False


def test_calculate_incident_similarity_ignores_unknown_components():
    score, details = v05.calculate_incident_similarity(make_article(), make_incident())
    assert score == pytest.approx(1.0)
    assert details["target"] == 1.0
    assert details["actor"] is None
    assert details["text"] == 1.0


def test_create_tables_needs_migration_for_pipeline_version(temp_conn):
    # create_tables() saja belum memuat kolom pipeline_version yang ditulis oleh
    # save_incident_document(); run() selalu memanggil migrate_existing_tables().
    v05.create_tables(temp_conn)
    v05.migrate_existing_tables(temp_conn)
    columns = {row[1] for row in temp_conn.execute("PRAGMA table_info(v05_incident_documents)")}
    assert {"incident_id", "article_id", "similarity_score", "pipeline_version"} <= columns


def test_find_best_incident_with_database(temp_conn, token_df):
    v05.create_tables(temp_conn)
    v05.migrate_existing_tables(temp_conn)  # seperti run(): menambah kolom pipeline_version
    anchor = make_article(article_id=1, article_uid="uid-a")
    incident_id = v05.create_incident(temp_conn, anchor, 1.0)
    assert v05.save_incident_document(temp_conn, incident_id, 1, 1.0, 1.0, "NEW_INCIDENT") == 1

    # liputan lanjutan dengan entity target yang sama -> incident yang sama
    follow_up = make_article(
        article_id=2, article_uid="uid-b",
        tokens={"smiths", "group", "contained", "recovering"},
        published="2025-03-05T10:00:00+00:00",
    )
    best, score = v05.find_best_incident(temp_conn, follow_up)
    assert best is not None
    assert best["incident_id"] == incident_id
    assert score >= v05.MIN_SCORE_WITH_IDENTITY

    # cerita lain dengan target dan jenis serangan berbeda -> tidak ada kandidat
    unrelated = make_article(
        article_id=3, article_uid="uid-c", attack_type="ransomware",
        target="rivers casino", target_entity_id="ent-rivers",
        tokens={"rivers", "casino", "ransomware"}, published="2025-03-02T12:00:00+00:00",
    )
    assert v05.find_best_incident(temp_conn, unrelated) == (None, 0.0)

    # jenis serangan sama saja, tanpa sinyal identitas atau teks mirip -> tidak digabung
    same_type_only = make_article(
        article_id=4, article_uid="uid-d", target=None, target_entity_id=None, location=None,
        tokens={"unrelated", "story", "outage"}, published="2025-03-02T12:00:00+00:00",
    )
    assert v05.find_best_incident(temp_conn, same_type_only) == (None, 0.0)
