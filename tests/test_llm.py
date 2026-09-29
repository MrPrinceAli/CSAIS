"""Uji klien LLM lokal (tanpa server nyata) dan penggabungan hasil LLM ke V0.3."""

import json

import pytest

from csais import llm, llm_extraction


class FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = json.dumps(body)

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeSession:
    """Menolak response_format sekali (seperti server lama), lalu menjawab dengan <think>."""

    def __init__(self, reject_schema=True):
        self.reject_schema = reject_schema
        self.payloads = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.payloads.append(json)
        if self.reject_schema and "response_format" in json:
            return FakeResponse(400, {"error": "response_format not supported"})
        content = '<think>panjang</think>```json\n{"is_incident": true, "attack_types": ["RANSOMWARE", "BUKAN"], "target": " BSI ", "threat_actor": "null", "attack_date": "8 Mei 2023", "location": "Indonesia", "target_groups": ["BANK_CUSTOMERS"], "confidence": 3}\n```'
        return FakeResponse(200, {"choices": [{"message": {"content": content}}]})

    def get(self, url, headers=None, timeout=None):
        return FakeResponse(200, {"data": [{"id": "qwen"}]})


def test_parse_json_text_variants():
    assert llm.parse_json_text('<think>x</think>{"a": 1}') == {"a": 1}
    assert llm.parse_json_text('Berikut hasilnya: {"a": 2} semoga membantu') == {"a": 2}
    with pytest.raises(llm.LLMError):
        llm.parse_json_text("tidak ada json")


def test_client_falls_back_without_schema_and_normalizes():
    session = FakeSession()
    client = llm.LLMClient(session=session, base_url="http://x/v1", model="qwen", no_think=True, json_schema=True)
    result, raw = llm_extraction.extract(client, "Judul", "Ringkasan")
    assert "response_format" in session.payloads[0] and "response_format" not in session.payloads[1]
    assert session.payloads[1]["messages"][1]["content"].endswith("/no_think")
    assert result == {
        "is_incident": True, "attack_type": "RANSOMWARE", "target": "BSI", "threat_actor": None,
        "attack_date": None,  # bukan format YYYY-MM-DD
        "location": "indonesia", "target_group": "BANK_CUSTOMERS", "confidence": 1.0,
    }
    assert client.models() == ["qwen"]


def test_client_requires_config(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    with pytest.raises(llm.LLMError):
        llm.LLMClient()


def test_schema_enums_match_keywords():
    enum = llm_extraction.SCHEMA["properties"]["attack_types"]["items"]["enum"]
    assert "RANSOMWARE" in enum and "CYBER_ATTACK" in enum
    assert set(llm_extraction.SCHEMA["required"]) == set(llm_extraction.SCHEMA["properties"])


def test_fill_unknown_only_fills_blanks(temp_conn):
    temp_conn.executescript("""
        CREATE TABLE articles (article_id INTEGER PRIMARY KEY, article_uid TEXT);
        CREATE TABLE v03_information_extraction (article_id INTEGER PRIMARY KEY, attack_type TEXT, target TEXT,
            threat_actor TEXT, attack_date TEXT, location TEXT, target_group TEXT, field_confidence TEXT, extraction_method TEXT);
        INSERT INTO articles VALUES (1, 'u1'), (2, 'u2');
        INSERT INTO v03_information_extraction VALUES
            (1, 'CYBER_ATTACK', 'UNKNOWN', 'LockBit', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', '{"target": 0.0}', 'RULE_BASED'),
            (2, 'PHISHING', 'Bank X', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', '{}', 'RULE_BASED');
    """)
    row = lambda uid, incident, attack, target, actor: (uid, "qwen", "v1", incident, attack, target, actor, None, "indonesia", None, 0.8, "{}", "t")  # noqa: E731
    llm_extraction.store_local(temp_conn, [row("u1", 1, "RANSOMWARE", "BSI", "ALPHV"), row("u2", 0, "MALWARE", "Bank Y", "Z")])
    assert llm_extraction.fill_unknown(temp_conn) == 1  # u2 bukan incident menurut LLM
    target, actor, attack, method, confidence = temp_conn.execute(
        "SELECT target, threat_actor, attack_type, extraction_method, field_confidence FROM v03_information_extraction WHERE article_id = 1"
    ).fetchone()
    assert (target, actor, attack, method) == ("BSI", "LockBit", "RANSOMWARE", "RULE_BASED+LLM")  # pelaku aturan tidak ditimpa
    assert json.loads(confidence)["target"] == llm_extraction.FILL_CONFIDENCE
    assert llm_extraction.fill_unknown(temp_conn) == 0
