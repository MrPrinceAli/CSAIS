"""Tes penerbitan ke Turso dengan transport palsu (tanpa jaringan)."""

import sqlite3

import pytest

from csais import publish


class FakeClient:
    """Mencatat statement; meniru API TursoClient."""

    def __init__(self):
        self.calls = []

    def execute(self, statements):
        self.calls.append(("execute", list(statements)))
        return []

    def transaction(self, statements):
        self.calls.append(("transaction", list(statements)))
        return []


def test_to_arg_types():
    assert publish._to_arg(None) == {"type": "null"}
    assert publish._to_arg(7) == {"type": "integer", "value": "7"}
    assert publish._to_arg(True) == {"type": "integer", "value": "1"}
    assert publish._to_arg(1.5) == {"type": "float", "value": 1.5}
    assert publish._to_arg("x") == {"type": "text", "value": "x"}
    with pytest.raises(TypeError):
        publish._to_arg(b"blob")


def test_client_normalises_url_and_requires_credentials():
    client = publish.TursoClient("libsql://csais-ali.turso.io", "tok", session=object())
    assert client.endpoint == "https://csais-ali.turso.io/v2/pipeline"
    assert client.headers["Authorization"] == "Bearer tok"
    with pytest.raises(ValueError):
        publish.TursoClient("", "tok")


def test_publish_table_creates_fills_and_swaps(tmp_path, monkeypatch):
    conn = sqlite3.connect(tmp_path / "local.db")
    conn.execute("CREATE TABLE sources (domain TEXT PRIMARY KEY, article_count INTEGER, score REAL)")
    conn.executemany(
        "INSERT INTO sources VALUES (?, ?, ?)",
        [(f"d{i}.id", i, i / 2) for i in range(7)],
    )
    conn.commit()
    monkeypatch.setattr(publish, "CHUNK_ROWS", 3)
    monkeypatch.setattr(publish, "ROWS_PER_STATEMENT", 1)

    client = FakeClient()
    total = publish.publish_table(conn, client, "sources", "SELECT * FROM sources", ["domain"], log=lambda *_: None)
    assert total == 7

    kinds = [kind for kind, _ in client.calls]
    # create (execute), 3 potongan insert (3+3+1), lalu swap (transaction)
    assert kinds == ["execute", "transaction", "transaction", "transaction", "transaction"]
    create_sql = client.calls[0][1][1][0]
    assert create_sql.startswith('CREATE TABLE "sources__new" (') and '"score" REAL' in create_sql
    first_chunk = client.calls[1][1]
    assert len(first_chunk) == 3 and first_chunk[0][0].startswith('INSERT INTO "sources__new"')
    assert first_chunk[0][1] == ["d0.id", 0, 0.0]
    swap = [sql for sql, _ in client.calls[-1][1]]
    assert 'DROP TABLE IF EXISTS "sources"' in swap
    assert 'ALTER TABLE "sources__new" RENAME TO "sources"' in swap
    assert any("idx_sources_domain" in sql for sql in swap)
    conn.close()


def test_insert_statements_pack_multiple_rows(monkeypatch):
    monkeypatch.setattr(publish, "ROWS_PER_STATEMENT", 2)
    columns = [("a", "TEXT"), ("b", "INTEGER")]
    statements = publish.insert_statements("t", columns, [("x", 1), ("y", 2), ("z", 3)])
    assert len(statements) == 2
    sql, args = statements[0]
    assert sql == 'INSERT INTO "t__new" ("a", "b") VALUES (?, ?), (?, ?)'
    assert args == ["x", 1, "y", 2]
    assert statements[1] == ('INSERT INTO "t__new" ("a", "b") VALUES (?, ?)', ["z", 3])


def test_publish_all_uses_given_client_for_every_table(tmp_path, monkeypatch):
    db = tmp_path / "local.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sources (domain TEXT)")
    conn.execute("CREATE TABLE pipeline_runs (run_id INTEGER, stage TEXT, pipeline_version TEXT, "
                 "started_at TEXT, finished_at TEXT, rows_processed INTEGER, notes TEXT)")
    conn.executemany("INSERT INTO sources VALUES (?)", [("a.id",), ("b.id",)])
    conn.commit()
    conn.close()
    monkeypatch.setattr(publish, "get_connection", lambda: sqlite3.connect(db))
    monkeypatch.setattr(publish, "record_run", lambda *a, **k: None)
    client = FakeClient()
    total = publish.publish_all(
        client=client,
        tables={"sources": ("SELECT * FROM sources", []), "hilang": ("SELECT * FROM hilang", [])},
        log=lambda *_: None,
    )
    assert total == 2  # tabel yang tidak ada dilewati, bukan gagal
    assert any(sql.startswith('CREATE TABLE "sources__new"') for _, stmts in client.calls for sql, _ in stmts)
