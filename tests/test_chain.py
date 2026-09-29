"""Uji penjangkaran: pengodean ABI, klien palsu, dan penerapan ke evidence_batches."""

import sqlite3

import pytest

from csais import chain, ledger

ROOT = "ab" * 32


class FakeClient:
    """Kontrak palsu di memori yang meniru anchorRoot dan getAnchor."""

    def __init__(self):
        self.anchors = {}
        self.block = 10
        self.sent = []

    def chain_id(self):
        return 31337

    def accounts(self):
        return ["0x" + "11" * 20, "0x" + "22" * 20]

    def send(self, sender, to, data):
        assert data.startswith("0x" + chain.selector("anchorRoot(uint64,bytes32,bytes32,uint8)"))
        words = chain.decode_words("0x" + data[10:])
        self.block += 1
        self.anchors[words[1]] = (int(words[0], 16), int(words[3], 16), words[2], self.block, 0)
        self.sent.append(words[1])
        return {"transactionHash": "0x" + f"{self.block:064x}", "blockNumber": hex(self.block)}

    def eth_call(self, to, data):
        root = chain.decode_words("0x" + data[10:])[0]
        batch_id, kind, previous, block, ts = self.anchors.get(root, (0, 0, "0" * 64, 0, 0))
        return "0x" + "".join(chain.word(v) for v in (batch_id, kind)) + previous + "".join(chain.word(v) for v in (block, ts))


def test_word_encoding():
    assert chain.word(1) == "0" * 63 + "1"
    assert chain.word("0x" + "ab" * 20) == "0" * 24 + "ab" * 20
    assert chain.word(ROOT) == ROOT
    with pytest.raises(ValueError):
        chain.word("0x1234")
    assert chain.code_bytes32("BSSN") == "4253534e" + "0" * 56
    assert chain.encode_call("getAnchor(bytes32)", ROOT) == "0x7feb51d9" + ROOT


def test_anchor_batches_skips_existing():
    client = FakeClient()
    batches = [
        {"batch_id": 1, "merkle_root": ROOT, "previous_root": None, "batch_kind": "evidence"},
        {"batch_id": 2, "merkle_root": "cd" * 32, "previous_root": ROOT, "batch_kind": "official_record"},
    ]
    rows = chain.anchor_batches(batches, client, "0x" + "99" * 20, "anvil-lokal")
    assert [r["kind"] for r in rows] == [0, 1] and all(r["tx_hash"] for r in rows)
    assert client.anchors["cd" * 32][2] == ROOT  # previous_root tersimpan
    again = chain.anchor_batches(batches, client, "0x" + "99" * 20, "anvil-lokal")
    assert [r["tx_hash"] for r in again] == ["", ""] and len(client.sent) == 2
    assert again[0]["block_number"] == rows[0]["block_number"]


def test_store_rows_keeps_tx_hash(tmp_path, monkeypatch):
    path = tmp_path / "input.db"
    monkeypatch.setenv("SURVEY_DATABASE_URL", f"file:{path}")
    row = {"merkle_root": ROOT, "batch_id": 1, "kind": 0, "chain": "anvil-lokal", "chain_id": 31337,
           "contract": "0x99", "tx_hash": "0xabc", "block_number": 11, "anchored_at": "t1"}
    chain.store_anchor_rows([row])
    chain.store_anchor_rows([{**row, "tx_hash": "", "anchored_at": "t2"}])
    assert sqlite3.connect(path).execute("SELECT tx_hash, anchored_at FROM chain_anchors").fetchall() == [("0xabc", "t1")]


def test_apply_anchors_requires_matching_root(temp_conn):
    ledger.create_tables(temp_conn)
    temp_conn.execute(
        "INSERT INTO evidence_batches (merkle_root, leaf_count, created_at, pipeline_version) VALUES (?, 1, 't', 'v')",
        (ROOT,),
    )
    temp_conn.commit()
    rows = [
        (ROOT, 1, "anvil-lokal", 31337, "0x99", "0xabc", 11, "t"),
        ("ef" * 32, 1, "anvil-lokal", 31337, "0x99", "0xdef", 12, "t"),  # akar lain, batch sama: diabaikan
    ]
    assert chain.apply_anchors(temp_conn, rows) == 1
    status, where, tx, block = temp_conn.execute(
        "SELECT anchor_status, anchor_chain, anchor_tx, anchor_block FROM evidence_batches"
    ).fetchone()
    assert (status, where, tx, block) == ("ANCHORED", "anvil-lokal:31337@0x99", "0xabc", 11)
    assert chain.apply_anchors(temp_conn, rows) == 0  # tidak diulang
