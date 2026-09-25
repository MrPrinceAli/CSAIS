"""Uji integrasi V0.4 -> V0.5 -> V0.6 -> ekspor pada database sementara kecil.

Empat artikel sintetis: dua salinan sindikasi berita yang sama (A, B), satu
berita lain (C), dan satu liputan lanjutan dengan nama target yang sama (D).
Skema dibuat oleh modul-modul itu sendiri; baris V0.2/V0.3 dimasukkan langsung
agar hasil tidak bergantung pada daftar kata kunci, lalu ``run()`` V0.4-V0.6
dijalankan sungguhan dengan stdout ditangkap.
"""

import contextlib
import io
import json
import os

import pytest

from csais import crawler, export, provenance, schema
from csais import v02_relevance_detection as v02
from csais import v03_information_extraction as v03
from csais import v04_entity_resolution as v04
from csais import v05_incident_clustering as v05
from csais import v06_evidence_correlation as v06
from csais.config import DATABASE_FILE
from csais.db import get_connection, get_timestamp

SMITHS_SUMMARY = (
    "Engineering firm Smiths Group said hackers gained unauthorised access to its systems "
    "in a cyber attack, prompting the isolation of affected networks while external "
    "specialists investigate. The FTSE 100 company said it had activated its business "
    "continuity plans and was working to restore affected systems as quickly as possible."
)

SMITHS_V03 = {"attack_type": "NETWORK_INTRUSION", "target": "Smiths Group", "location": "United Kingdom"}

ARTICLES = [
    {
        "key": "smiths_reuters",
        "title": "Smiths Group hit by cyber attack - Reuters",
        "summary": SMITHS_SUMMARY + " Reuters",
        "url": "https://www.reuters.com/technology/smiths-group-cyber-attack",
        "published": "2025-03-01T08:00:00+00:00",
        "v03": SMITHS_V03,
    },
    {
        "key": "smiths_bbc",
        "title": "Smiths Group hit by cyber attack - BBC News",
        "summary": SMITHS_SUMMARY + " BBC News",
        "url": "https://www.bbc.com/news/smiths-group-cyber-attack",
        "published": "2025-03-01T09:30:00+00:00",
        "v03": SMITHS_V03,
    },
    {
        "key": "qilin_casino",
        "title": "Qilin ransomware claims attack on Rivers Casino Philadelphia - BleepingComputer",
        "summary": (
            "The Qilin ransomware gang has claimed responsibility for the attack on Rivers "
            "Casino Philadelphia, listing the casino on its leak site and threatening to "
            "publish customer data stolen during the intrusion. BleepingComputer"
        ),
        "url": "https://www.bleepingcomputer.com/news/security/qilin-rivers-casino",
        "published": "2025-03-02T12:00:00+00:00",
        "v03": {
            "attack_type": "RANSOMWARE, DATA_THEFT",
            "target": "Rivers Casino Philadelphia",
            "threat_actor": "Qilin",
            "location": "United States",
            "impact": "DATA_THEFT",
        },
    },
    {
        "key": "smiths_register",
        "title": "Smiths Group says cyber attack contained, operations recovering - The Register",
        "summary": (
            "Smiths Group has confirmed the cyber attack disclosed last week has been "
            "contained and business operations are recovering, the engineering company "
            "said in a stock exchange filing. The Register"
        ),
        "url": "https://www.theregister.com/2025/03/05/smiths_group_recovery",
        "published": "2025-03-05T10:00:00+00:00",
        "v03": SMITHS_V03,
    },
]

V03_DEFAULTS = {
    "attack_type": "UNKNOWN", "attack_method": "UNKNOWN", "target": "UNKNOWN",
    "target_sector": "UNKNOWN", "target_group": "UNKNOWN", "location": "UNKNOWN",
    "attack_date": "UNKNOWN", "threat_actor": "UNKNOWN", "impact": "UNKNOWN",
    "indicator": "UNKNOWN",
}


def _insert_fixture_articles():
    """Masukkan artikel beserta baris V0.2 dan V0.3; kembalikan {key: article_id}."""
    conn = get_connection()
    cursor = conn.cursor()
    now = get_timestamp()
    ids = {}
    for article in ARTICLES:
        cursor.execute(
            """
            INSERT INTO articles (
                source_name, source_type, source_url, title, summary, content, article_url,
                published_date, collected_date, language, language_confidence,
                query_keyword, query_language, content_hash, first_seen, last_seen
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "Google News", "RSS", "https://news.google.com/rss/search?q=test",
                article["title"], article["summary"], None, article["url"],
                article["published"], now, "en", 0.99, "cyber attack", "en",
                crawler.generate_content_hash(article["title"], article["summary"], article["url"]),
                now, now,
            ),
        )
        article_id = cursor.lastrowid
        ids[article["key"]] = article_id
        cursor.execute(
            """
            INSERT INTO v02_relevance (
                article_id, relevance_label, relevance_score, relevance_confidence,
                relevance_method, attack_matches, event_matches, non_incident_matches,
                analyzed_at
            )
            VALUES (?, 'RELEVANT', 0.8, 0.6, 'RULE_BASED', 'cyber attack', 'hit by', '', ?)
            """,
            (article_id, now),
        )
        fields = dict(V03_DEFAULTS, **article["v03"])
        cursor.execute(
            """
            INSERT INTO v03_information_extraction (
                article_id, attack_type, attack_method, target, target_organization,
                target_sector, target_group, location, attack_date, threat_actor, impact,
                indicator, extraction_confidence, extraction_method, extracted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'RULE_BASED', ?)
            """,
            (
                article_id, fields["attack_type"], fields["attack_method"], fields["target"],
                fields["target"], fields["target_sector"], fields["target_group"],
                fields["location"], fields["attack_date"], fields["threat_actor"],
                fields["impact"], fields["indicator"], 0.4, now,
            ),
        )
    conn.commit()
    conn.close()
    return ids


@pytest.fixture(scope="module")
def pipeline(fresh_db_module):
    """Bangun database, jalankan V0.4-V0.6 dan ekspor sekali untuk seluruh modul."""
    crawler.initialize_database()
    v02.initialize_v02_database()
    v03.initialize_v03_database()
    ids = _insert_fixture_articles()

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        v04.run()
        v05.run()
        v06.run()

    export_path = os.path.join(os.path.dirname(DATABASE_FILE), "incidents.jsonl")
    exported = export.export_incidents(export_path)
    return {
        "ids": ids,
        "output": output.getvalue(),
        "export_path": export_path,
        "exported": exported,
    }


def _query(sql, params=()):
    conn = get_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def _incident_of(pipeline, key):
    rows = _query(
        "SELECT incident_id FROM v05_incident_documents WHERE article_id = ?",
        (pipeline["ids"][key],),
    )
    assert len(rows) == 1
    return rows[0][0]


def _article(key):
    return next(article for article in ARTICLES if article["key"] == key)


def test_pipeline_stages_complete(pipeline):
    output = pipeline["output"]
    assert "V0.4 ENTITY RESOLUTION SELESAI" in output
    assert "V0.5 INCIDENT CLUSTERING SELESAI" in output
    assert "V0.6 EVIDENCE CORRELATION SELESAI" in output
    assert "ERROR" not in output
    assert _query("SELECT COUNT(*) FROM v04_processed_articles")[0][0] == len(ARTICLES)
    assert _query("SELECT COUNT(*) FROM v05_processed_articles")[0][0] == len(ARTICLES)


def test_v04_resolves_entities_across_articles(pipeline):
    ids = pipeline["ids"]
    smiths_entities = {
        _query(
            "SELECT entity_id, canonical_name FROM v04_entity_mentions "
            "WHERE article_id = ? AND entity_type = 'ORGANIZATION'",
            (ids[key],),
        )[0]
        for key in ("smiths_reuters", "smiths_bbc", "smiths_register")
    }
    assert len(smiths_entities) == 1
    assert next(iter(smiths_entities))[1] == "Smiths Group"

    actor = _query(
        "SELECT canonical_name, resolution_method FROM v04_entity_mentions "
        "WHERE article_id = ? AND entity_type = 'THREAT_ACTOR'",
        (ids["qilin_casino"],),
    )
    assert actor == [("Qilin", "KNOWN_ALIAS")]

    location = _query(
        "SELECT canonical_name, resolution_method FROM v04_entity_mentions "
        "WHERE article_id = ? AND entity_type = 'LOCATION'",
        (ids["smiths_reuters"],),
    )
    assert location == [("United Kingdom", "KNOWN_ALIAS")]

    canonical = {row[0] for row in _query("SELECT canonical_name FROM v04_entities")}
    assert canonical == {
        "Smiths Group", "Rivers Casino Philadelphia", "Qilin", "United Kingdom", "United States",
    }


def test_syndicated_copies_share_one_incident(pipeline):
    assert _incident_of(pipeline, "smiths_reuters") == _incident_of(pipeline, "smiths_bbc")


def test_unrelated_story_gets_its_own_incident(pipeline):
    assert _incident_of(pipeline, "qilin_casino") != _incident_of(pipeline, "smiths_reuters")
    assert _query("SELECT COUNT(*) FROM v05_incidents")[0][0] == 2
    row = _query(
        "SELECT target, threat_actor, document_count FROM v05_incidents WHERE incident_id = ?",
        (_incident_of(pipeline, "qilin_casino"),),
    )
    assert row == [("rivers casino philadelphia", "qilin", 1)]


def test_follow_up_with_same_target_joins_incident(pipeline):
    incident_id = _incident_of(pipeline, "smiths_reuters")
    assert _incident_of(pipeline, "smiths_register") == incident_id
    row = _query(
        "SELECT document_count, anchor_published_date, last_published_date, target "
        "FROM v05_incidents WHERE incident_id = ?",
        (incident_id,),
    )
    assert row == [(3, _article("smiths_reuters")["published"], _article("smiths_register")["published"], "smiths group")]
    methods = _query(
        "SELECT clustering_method FROM v05_incident_documents WHERE incident_id = ? "
        "ORDER BY article_id",
        (incident_id,),
    )
    assert methods == [("NEW_INCIDENT",), ("RULE_BASED_CLUSTERING",), ("RULE_BASED_CLUSTERING",)]


def test_incident_id_is_deterministic_from_anchor_article_uid(pipeline):
    anchor_uid = schema.article_uid(_article("smiths_reuters")["url"])
    assert _incident_of(pipeline, "smiths_reuters") == v05.generate_incident_id(anchor_uid)
    anchor_id = _query(
        "SELECT anchor_article_id FROM v05_incidents WHERE incident_id = ?",
        (_incident_of(pipeline, "smiths_reuters"),),
    )[0][0]
    assert anchor_id == pipeline["ids"]["smiths_reuters"]


def test_article_uid_backfilled_by_pipeline(pipeline):
    rows = _query("SELECT article_url, article_uid FROM articles")
    assert len(rows) == len(ARTICLES)
    assert all(uid == schema.article_uid(url) for url, uid in rows)


def test_v06_marks_syndicated_pair_and_single_source(pipeline):
    ids = pipeline["ids"]
    smiths_incident = _incident_of(pipeline, "smiths_reuters")
    a, b = sorted((ids["smiths_reuters"], ids["smiths_bbc"]))
    relation = _query(
        "SELECT relation_type, text_similarity, title_similarity, domain_same "
        "FROM v06_source_relations WHERE incident_id = ? AND article_id_a = ? AND article_id_b = ?",
        (smiths_incident, a, b),
    )
    assert len(relation) == 1
    relation_type, text_similarity, title_similarity, domain_same = relation[0]
    assert relation_type in {"LIKELY_DUPLICATE", "LIKELY_REPRODUCED"}
    assert text_similarity >= v06.TEXT_SIMILARITY_THRESHOLD
    assert 0.0 <= title_similarity <= 1.0
    assert domain_same == 0
    # 3 artikel -> 3 pasangan
    assert _query(
        "SELECT COUNT(*) FROM v06_source_relations WHERE incident_id = ?", (smiths_incident,)
    )[0][0] == 3

    evidence = _query(
        "SELECT article_id, evidence_type, evidence_independence_score, evidence_uid, "
        "pipeline_version, source_domain FROM v06_evidence ORDER BY article_id"
    )
    assert len(evidence) == len(ARTICLES)
    valid_types = {
        "SINGLE_SOURCE", "INDEPENDENT_SUPPORT", "REPRODUCED_OR_SYNDICATED",
        "DUPLICATE_OR_REPEATED", "UNCERTAIN",
    }
    assert all(row[1] in valid_types for row in evidence)
    assert all(row[4] == provenance.pipeline_stamp() for row in evidence)

    by_article = {row[0]: row for row in evidence}
    casino = by_article[ids["qilin_casino"]]
    assert casino[1] == "SINGLE_SOURCE"
    assert casino[2] == 1.0
    assert casino[5] == "bleepingcomputer.com"
    casino_incident = _incident_of(pipeline, "qilin_casino")
    casino_uid = schema.article_uid(_article("qilin_casino")["url"])
    assert casino[3] == schema.evidence_uid(casino_incident, casino_uid)


def test_pipeline_runs_recorded(pipeline):
    rows = _query("SELECT stage, pipeline_version, rows_processed FROM pipeline_runs")
    stages = {row[0]: row for row in rows}
    assert {"v04_entity_resolution", "v05_incident_clustering", "v06_evidence_correlation"} <= set(stages)
    assert stages["v04_entity_resolution"][2] == len(ARTICLES)
    assert stages["v05_incident_clustering"][2] == len(ARTICLES)
    assert stages["v06_evidence_correlation"][2] == 2
    assert all(row[1] == provenance.pipeline_stamp() for row in rows)


def _read_export(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def test_export_meta_line(pipeline):
    assert pipeline["exported"] == 2
    records = _read_export(pipeline["export_path"])
    meta = records[0]
    assert meta["type"] == "meta"
    assert meta["schema_version"] == export.SCHEMA_VERSION
    assert meta["incident_count"] == 2
    assert meta["pipeline_version"] == provenance.pipeline_stamp()
    assert meta["database"] == os.path.basename(DATABASE_FILE)
    assert meta["generated_at"]
    assert len(records) == 3


def test_export_incident_lines_have_evidence_with_claims(pipeline):
    ids = pipeline["ids"]
    records = _read_export(pipeline["export_path"])
    incidents = {record["incident_id"]: record for record in records[1:]}
    assert all(record["type"] == "incident" for record in incidents.values())

    smiths = incidents[_incident_of(pipeline, "smiths_reuters")]
    assert smiths["document_count"] == 3 == len(smiths["evidence"])
    assert smiths["target"] == "smiths group"
    assert len(smiths["relations"]) == 3
    assert all(isinstance(rel["same_domain"], bool) for rel in smiths["relations"])

    by_article = {ev["article_id"]: ev for ev in smiths["evidence"]}
    assert set(by_article) == {ids["smiths_reuters"], ids["smiths_bbc"], ids["smiths_register"]}
    for key in ("smiths_reuters", "smiths_bbc", "smiths_register"):
        ev = by_article[ids[key]]
        assert ev["article_uid"] == schema.article_uid(_article(key)["url"])
        assert ev["evidence_uid"] == schema.evidence_uid(smiths["incident_id"], ev["article_uid"])
        assert ev["url"] == _article(key)["url"]
        assert ev["relevance_label"] == "RELEVANT"
        assert set(ev["claims"]) == set(export._CLAIM_FIELDS)
        assert ev["claims"]["attack_type"] == "NETWORK_INTRUSION"
        assert ev["claims"]["target"] == "Smiths Group"

    casino = incidents[_incident_of(pipeline, "qilin_casino")]
    assert casino["threat_actor"] == "qilin"
    assert casino["relations"] == []
    assert casino["evidence"][0]["claims"]["threat_actor"] == "Qilin"
    assert casino["evidence"][0]["evidence_type"] == "SINGLE_SOURCE"


def test_export_min_docs_filter(pipeline):
    path = os.path.join(os.path.dirname(pipeline["export_path"]), "incidents_min2.jsonl")
    assert export.export_incidents(path, min_docs=2) == 1
    records = _read_export(path)
    assert records[0]["incident_count"] == 1
    assert [record["incident_id"] for record in records[1:]] == [
        _incident_of(pipeline, "smiths_reuters")
    ]
