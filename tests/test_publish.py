"""Tes penerbitan ke Turso dengan transport palsu (tanpa jaringan)."""

import sqlite3

import pytest

from csais import publish


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


class SqliteClient(publish.TursoClient):
    """Turso tiruan di atas SQLite di memori; mencatat setiap permintaan."""

    def __init__(self):
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.calls = []

    def execute(self, statements):
        statements = list(statements)
        self.calls.append(statements)
        results = []
        for sql, args in statements:
            rows = self.db.execute(sql, args).fetchall()
            cells = [[publish._to_arg(value) for value in row] for row in rows]
            results.append({"type": "ok", "response": {"result": {"rows": cells}}})
        return results

    def rows(self, table):
        return sorted(self.db.execute(f'SELECT * FROM "{table}"').fetchall())

    def written(self):
        """Statement penulisan (bukan baca, bukan BEGIN/COMMIT) sejak terakhir dipanggil."""
        calls, self.calls = self.calls, []
        skip = ("SELECT", "PRAGMA", "BEGIN", "COMMIT")
        return [sql for call in calls for sql, _ in call if not sql.startswith(skip)]


def _local_sources(tmp_path, n=7):
    conn = sqlite3.connect(tmp_path / "local.db")
    conn.execute("CREATE TABLE sources (domain TEXT PRIMARY KEY, article_count INTEGER, score REAL, updated_at TEXT)")
    conn.executemany(
        "INSERT INTO sources VALUES (?, ?, ?, ?)",
        [(f"d{i}.id", i, i / 2, "t1") for i in range(n)],
    )
    conn.commit()
    return conn


def _published(client):
    return [row[:-1] for row in client.rows("sources")]  # tanpa kolom hash


def test_publish_table_rebuilds_when_remote_table_missing(tmp_path, monkeypatch):
    conn = _local_sources(tmp_path)
    monkeypatch.setattr(publish, "CHUNK_ROWS", 3)
    monkeypatch.setattr(publish, "ROWS_PER_STATEMENT", 1)
    client = SqliteClient()

    written = publish.publish_table(conn, client, "sources", "SELECT * FROM sources", ["domain"], log=lambda *_: None)
    assert written == 7
    assert _published(client) == sorted(conn.execute("SELECT * FROM sources").fetchall())
    columns = [row[1] for row in client.db.execute("PRAGMA table_info(sources)")]
    assert columns[-1] == publish.HASH_COLUMN
    tables = {row[0] for row in client.db.execute("SELECT name FROM sqlite_master")}
    assert "sources__new" not in tables and "idx_sources_domain" in tables
    conn.close()


def test_publish_table_writes_only_changes(tmp_path):
    conn = _local_sources(tmp_path, n=20)
    client = SqliteClient()
    publish.publish_table(conn, client, "sources", "SELECT * FROM sources", ["domain"], log=lambda *_: None)
    client.written()

    # tanpa perubahan: tidak ada yang ditulis
    assert publish.publish_table(conn, client, "sources", "SELECT * FROM sources", [], log=lambda *_: None) == 0
    assert client.written() == []

    # hanya stempel waktu (kolom volatil) berubah: tetap tidak ditulis
    conn.execute("UPDATE sources SET updated_at = 't2'")
    assert publish.publish_table(conn, client, "sources", "SELECT * FROM sources", [], log=lambda *_: None) == 0

    # satu baris berubah, satu dihapus, satu baru: 2 dihapus + 2 ditambah
    conn.execute("UPDATE sources SET article_count = 99 WHERE domain = 'd1.id'")
    conn.execute("DELETE FROM sources WHERE domain = 'd2.id'")
    conn.execute("INSERT INTO sources VALUES ('baru.id', 1, 0.5, 't2')")
    written = publish.publish_table(conn, client, "sources", "SELECT * FROM sources", ["domain"], log=lambda *_: None)
    assert written == 4
    statements = client.written()
    assert statements[0].startswith('DELETE FROM "sources" WHERE rowid IN')
    assert not any("__new" in sql for sql in statements)
    published = {row[0]: row for row in _published(client)}
    assert set(published) == {row[0] for row in conn.execute("SELECT domain FROM sources")}
    assert published["d1.id"][1] == 99
    assert published["d0.id"][3] == "t1"  # baris lama tidak disentuh
    conn.close()


def test_publish_table_stages_large_diff(tmp_path, monkeypatch):
    conn = _local_sources(tmp_path, n=20)
    client = SqliteClient()
    publish.publish_table(conn, client, "sources", "SELECT * FROM sources", [], log=lambda *_: None)
    monkeypatch.setattr(publish, "CHUNK_ROWS", 2)
    conn.execute("UPDATE sources SET score = -1 WHERE domain IN ('d1.id', 'd2.id', 'd3.id')")
    client.written()

    assert publish.publish_table(conn, client, "sources", "SELECT * FROM sources", [], log=lambda *_: None) == 6
    assert any(sql.startswith('INSERT INTO "sources__add"') for sql in client.written())
    assert _published(client) == sorted(conn.execute("SELECT * FROM sources").fetchall())
    tables = {row[0] for row in client.db.execute("SELECT name FROM sqlite_master")}
    assert "sources__add" not in tables
    conn.close()


def test_publish_table_rebuilds_on_big_diff_or_schema_change(tmp_path):
    conn = _local_sources(tmp_path)
    client = SqliteClient()
    publish.publish_table(conn, client, "sources", "SELECT * FROM sources", [], log=lambda *_: None)

    conn.execute("UPDATE sources SET score = -1")  # semua baris berubah
    client.written()
    assert publish.publish_table(conn, client, "sources", "SELECT * FROM sources", [], log=lambda *_: None) == 7
    assert any("sources__new" in sql for sql in client.written())

    conn.execute("ALTER TABLE sources ADD COLUMN country TEXT")
    assert publish.publish_table(conn, client, "sources", "SELECT * FROM sources", [], log=lambda *_: None) == 7
    assert any("sources__new" in sql for sql in client.written())
    assert _published(client) == sorted(conn.execute("SELECT * FROM sources").fetchall())
    conn.close()


def test_remote_hashes_pages_and_keeps_duplicates(monkeypatch):
    monkeypatch.setattr(publish, "HASH_PAGE", 2)
    client = SqliteClient()
    client.db.execute('CREATE TABLE t (a TEXT, "_h" TEXT)')
    client.db.executemany("INSERT INTO t VALUES (?, ?)", [("x", "h1"), ("x", "h1"), ("y", "h2"), ("z", None), ("w", "h3")])
    assert publish.remote_hashes(client, "t") == {"h1": [1, 2], "h2": [3], "": [4], "h3": [5]}


def test_insert_statements_pack_multiple_rows(monkeypatch):
    monkeypatch.setattr(publish, "ROWS_PER_STATEMENT", 2)
    columns = [("a", "TEXT"), ("b", "INTEGER")]
    statements = publish.insert_statements("t__new", columns, [("x", 1), ("y", 2), ("z", 3)])
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
    client = SqliteClient()
    total = publish.publish_all(
        client=client,
        tables={"sources": ("SELECT * FROM sources", []), "hilang": ("SELECT * FROM hilang", [])},
        log=lambda *_: None,
    )
    assert total == 2  # tabel yang tidak ada dilewati, bukan gagal
    assert client.rows("sources") == [("a.id", publish.row_hash(("a.id",))), ("b.id", publish.row_hash(("b.id",)))]
