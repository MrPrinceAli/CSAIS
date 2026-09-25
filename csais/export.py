"""Ekspor hasil pipeline ke JSON Lines: satu incident per baris.

Ini kontrak keluaran CSAIS untuk sistem lain (ledger bukti, trust score,
laporan). Baris pertama adalah metadata, baris berikutnya masing-masing satu
incident lengkap dengan klaim tiap artikel, bukti, dan relasi antar sumber.

Skema (versi 1):
  meta     : {"type": "meta", "schema_version", "generated_at",
              "pipeline_version", "database", "incident_count"}
  incident : {"type": "incident", "incident_id", "attack_type", "target",
              "target_entity_id", "threat_actor", "threat_actor_entity_id",
              "location", "attack_date", "attack_method", "first_published",
              "last_published", "document_count", "incident_confidence",
              "evidence": [...], "relations": [...]}
  evidence : {"evidence_uid", "article_uid", "article_id", "url",
              "source_name", "source_type", "source_domain", "language",
              "published_date", "title", "summary", "content_hash",
              "evidence_type", "independence_score", "evidence_confidence",
              "relevance_label", "relevance_score", "pipeline_version",
              "claims": {"attack_type", "attack_method", "target",
                         "target_sector", "target_group", "location",
                         "attack_date", "threat_actor", "impact",
                         "indicator", "extraction_confidence"}}
  relation : {"article_id_a", "article_id_b", "relation_type",
              "text_similarity", "title_similarity", "same_domain",
              "independence_score", "relation_confidence"}
"""

import json
import os

from csais.config import DATABASE_FILE
from csais.db import get_connection, get_timestamp
from csais.provenance import pipeline_stamp

SCHEMA_VERSION = 1

_INCIDENT_SQL = """
    SELECT incident_id, attack_type, target, target_entity_id, threat_actor,
           threat_actor_entity_id, location, attack_date, attack_method,
           anchor_published_date, last_published_date, document_count,
           incident_confidence
    FROM v05_incidents
    WHERE document_count >= ?
    ORDER BY anchor_published_date, incident_id
"""

_EVIDENCE_SQL = """
    SELECT e.evidence_uid, a.article_uid, a.article_id, a.article_url,
           a.source_name, a.source_type, e.source_domain, a.language,
           a.published_date, a.title, a.summary, a.content_hash,
           e.evidence_type, e.evidence_independence_score, e.evidence_confidence,
           r.relevance_label, r.relevance_score, e.pipeline_version,
           x.attack_type, x.attack_method, x.target, x.target_sector,
           x.target_group, x.location, x.attack_date, x.threat_actor, x.impact,
           x.indicator, x.extraction_confidence
    FROM v05_incident_documents d
    JOIN articles a ON a.article_id = d.article_id
    LEFT JOIN v06_evidence e
        ON e.incident_id = d.incident_id AND e.article_id = d.article_id
    LEFT JOIN v02_relevance r ON r.article_id = a.article_id
    LEFT JOIN v03_information_extraction x ON x.article_id = a.article_id
    WHERE d.incident_id = ?
    ORDER BY a.published_date, a.article_id
"""

_RELATION_SQL = """
    SELECT article_id_a, article_id_b, relation_type, text_similarity,
           title_similarity, domain_same, independence_score, relation_confidence
    FROM v06_source_relations
    WHERE incident_id = ?
    ORDER BY article_id_a, article_id_b
"""

_CLAIM_FIELDS = (
    "attack_type", "attack_method", "target", "target_sector", "target_group",
    "location", "attack_date", "threat_actor", "impact", "indicator",
    "extraction_confidence",
)


def _evidence_record(row):
    base = dict(
        zip(
            (
                "evidence_uid", "article_uid", "article_id", "url", "source_name",
                "source_type", "source_domain", "language", "published_date",
                "title", "summary", "content_hash", "evidence_type",
                "independence_score", "evidence_confidence", "relevance_label",
                "relevance_score", "pipeline_version",
            ),
            row[:18],
        )
    )
    base["claims"] = dict(zip(_CLAIM_FIELDS, row[18:]))
    return base


def _relation_record(row):
    record = dict(
        zip(
            (
                "article_id_a", "article_id_b", "relation_type", "text_similarity",
                "title_similarity", "same_domain", "independence_score",
                "relation_confidence",
            ),
            row,
        )
    )
    record["same_domain"] = bool(record["same_domain"])
    return record


def export_incidents(path, min_docs=1):
    """Tulis semua incident dengan >= min_docs artikel ke berkas JSONL."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(_INCIDENT_SQL, (min_docs,))
    incidents = cursor.fetchall()

    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        meta = {
            "type": "meta",
            "schema_version": SCHEMA_VERSION,
            "generated_at": get_timestamp(),
            "pipeline_version": pipeline_stamp(),
            "database": os.path.basename(DATABASE_FILE),
            "incident_count": len(incidents),
        }
        fh.write(json.dumps(meta, ensure_ascii=False) + "\n")

        for row in incidents:
            (
                incident_id, attack_type, target, target_entity_id, threat_actor,
                threat_actor_entity_id, location, attack_date, attack_method,
                first_published, last_published, document_count, incident_confidence,
            ) = row
            cursor.execute(_EVIDENCE_SQL, (incident_id,))
            evidence = [_evidence_record(r) for r in cursor.fetchall()]
            cursor.execute(_RELATION_SQL, (incident_id,))
            relations = [_relation_record(r) for r in cursor.fetchall()]
            record = {
                "type": "incident",
                "incident_id": incident_id,
                "attack_type": attack_type,
                "target": target,
                "target_entity_id": target_entity_id,
                "threat_actor": threat_actor,
                "threat_actor_entity_id": threat_actor_entity_id,
                "location": location,
                "attack_date": attack_date,
                "attack_method": attack_method,
                "first_published": first_published,
                "last_published": last_published,
                "document_count": document_count,
                "incident_confidence": incident_confidence,
                "evidence": evidence,
                "relations": relations,
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    conn.close()
    return len(incidents)
