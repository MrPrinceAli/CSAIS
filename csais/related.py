"""Incident terkait lewat embedding (RAG tahap 1): kemiripan makna antar incident.

Perintah lokal ``main.py --embed``:
  1. ambil teks tiap incident dari Turso (judul artikel jangkar, beberapa judul
     artikel lain, dan ringkasan jangkar);
  2. ubah menjadi vektor dengan model embedding di LM Studio
     (``EMBED_MODEL``, default text-embedding-nomic-embed-text-v1.5), dengan
     cache di ``database/embeddings.db`` sehingga hanya teks baru yang dihitung;
  3. cari tetangga terdekat (kosinus) dalam jendela ``WINDOW_DAYS``; pasangan
     sangat mirip dan berdekatan waktunya ditandai ``same_event`` (kemungkinan
     kejadian yang sama, termasuk lintas bahasa);
  4. tulis tabel ``incident_links`` ke database masukan (token tulis).
Pipeline menyalin tabel itu ke database pipeline dan menerbitkannya; web
menampilkan "Incident terkait" di detail incident. Belum ada penggabungan
otomatis: itu tahap berikutnya (#21), dengan penilaian LLM per pasangan.
"""

import hashlib
import os
import sqlite3
from datetime import datetime

import requests

from csais.config import DATABASE_DIR
from csais.db import get_connection, get_timestamp
from csais.schema import record_run

EMBED_MODEL_DEFAULT = "text-embedding-nomic-embed-text-v1.5"
CACHE_FILE = os.path.join(DATABASE_DIR, "embeddings.db")
PREFIX = "clustering: "  # awalan tugas model nomic-embed untuk pengelompokan
BATCH = 128
TOP_K = 5
# Ambang dari kalibrasi 29 Sep 2026 (contoh pasangan per rentang skor):
# >= 0,88 topik/kejadian serupa; >= 0,95 dengan jarak <= 3 hari hampir selalu
# kejadian yang sama; skor tinggi berjarak jauh biasanya seri berita berulang
# (laporan bulanan); lintas bahasa skornya lebih rendah (SmartTube id/en 0,92).
RELATED_MIN = 0.88
SAME_EVENT_MIN = 0.95
SAME_EVENT_DAYS = 3
CROSS_MIN = 0.92
CROSS_DAYS = 7
CROSS_LANGS = {"id", "en"}  # deteksi bahasa teks pendek kadang keliru (ca/es); lintas bahasa hanya bila salah satunya id/en
WINDOW_DAYS = 60
PAGE = 10000

LINKS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS incident_links (
        incident_id TEXT NOT NULL,
        related_id TEXT NOT NULL,
        similarity REAL NOT NULL,
        same_event INTEGER NOT NULL,
        cross_language INTEGER NOT NULL,
        model TEXT NOT NULL,
        computed_at TEXT NOT NULL,
        PRIMARY KEY (incident_id, related_id)
    )
"""
LINK_COLUMNS = ("incident_id", "related_id", "similarity", "same_event", "cross_language", "model", "computed_at")
LINKS_SQL = f"SELECT {', '.join(LINK_COLUMNS)} FROM incident_links"

INCIDENTS_SQL = """
    SELECT i.incident_id, i.anchor_article_id, i.anchor_published_date, a.language
    FROM v05_incidents i LEFT JOIN articles a ON a.article_id = i.anchor_article_id
    ORDER BY i.incident_id LIMIT ? OFFSET ?
"""
DOCS_SQL = """
    SELECT d.incident_id, a.article_id, a.title, a.summary
    FROM v05_incident_documents d JOIN articles a ON a.article_id = d.article_id
    ORDER BY d.incident_id, a.published_date LIMIT ? OFFSET ?
"""


# --- Teks incident ---
def _paged(sql):
    from csais.publish import TursoClient
    from csais.survey import _hrana_value

    url = os.environ.get("TURSO_DATABASE_URL") or ""
    rows, offset = [], 0
    if url.startswith("file:"):
        conn = sqlite3.connect(url[len("file:"):])
        try:
            return conn.execute(sql.replace("LIMIT ? OFFSET ?", ""), ()).fetchall()
        finally:
            conn.close()
    client = TursoClient(url, os.environ.get("TURSO_AUTH_TOKEN"))
    while True:
        result = client.execute([(sql, [PAGE, offset])])[0]["response"]["result"]
        page = [tuple(_hrana_value(cell) for cell in row) for row in result["rows"]]
        rows.extend(page)
        if len(page) < PAGE:
            return rows
        offset += PAGE


def incident_texts(incidents, docs):
    """Teks per incident: judul jangkar, sampai 3 judul lain, dan ringkasan jangkar."""
    from csais.text import split_publisher

    by_incident = {}
    for incident_id, article_id, title, summary in docs:
        by_incident.setdefault(incident_id, []).append((article_id, title or "", summary or ""))
    out = {}
    for incident_id, anchor_id, published, language in incidents:
        items = by_incident.get(incident_id) or []
        if not items:
            continue
        anchor = next((i for i in items if i[0] == anchor_id), items[0])
        headline = split_publisher(anchor[1])[0]
        others = []
        for _, title, _ in items:
            other = split_publisher(title)[0]
            if other and other != headline and other not in others:
                others.append(other)
            if len(others) >= 3:
                break
        summary = split_publisher(anchor[2])[0] if anchor[2] else ""
        text = ". ".join(part for part in [headline, *others, summary if summary != headline else ""] if part)
        out[incident_id] = {"text": text[:2000], "published": published, "language": language}
    return out


# --- Embedding dengan cache ---
def _cache():
    os.makedirs(DATABASE_DIR, exist_ok=True)
    conn = sqlite3.connect(CACHE_FILE)
    conn.execute("CREATE TABLE IF NOT EXISTS emb (incident_id TEXT PRIMARY KEY, text_hash TEXT, model TEXT, vector BLOB)")
    return conn


def embed_batch(texts, model, base_url, session=None):
    session = session or requests.Session()
    response = session.post(
        f"{base_url}/embeddings",
        json={"model": model, "input": [PREFIX + t for t in texts]},
        timeout=300,
    )
    response.raise_for_status()
    data = sorted(response.json()["data"], key=lambda item: item["index"])
    return [item["embedding"] for item in data]


def embeddings(items, model, base_url, log=print, embed=embed_batch):
    """Vektor ternormalisasi per incident (numpy), menghitung ulang hanya teks yang berubah."""
    import numpy as np

    cache = _cache()
    known = {row[0]: (row[1], row[2], row[3]) for row in cache.execute("SELECT incident_id, text_hash, model, vector FROM emb")}
    pending = []
    for incident_id, item in items.items():
        digest = hashlib.sha256(item["text"].encode("utf-8")).hexdigest()[:24]
        item["hash"] = digest
        cached = known.get(incident_id)
        if not cached or cached[0] != digest or cached[1] != model:
            pending.append(incident_id)
    log(f"Incident: {len(items)}, perlu embedding baru: {len(pending)}")
    for start in range(0, len(pending), BATCH):
        chunk = pending[start : start + BATCH]
        vectors = embed([items[i]["text"] for i in chunk], model, base_url)
        cache.executemany(
            "INSERT OR REPLACE INTO emb (incident_id, text_hash, model, vector) VALUES (?, ?, ?, ?)",
            [(i, items[i]["hash"], model, np.asarray(v, dtype=np.float32).tobytes()) for i, v in zip(chunk, vectors)],
        )
        cache.commit()
        if (start // BATCH) % 20 == 0:
            log(f"   {min(start + BATCH, len(pending))}/{len(pending)}")
    ids = list(items)
    rows = {row[0]: row[1] for row in cache.execute("SELECT incident_id, vector FROM emb")}
    cache.close()
    matrix = np.vstack([np.frombuffer(rows[i], dtype=np.float32) for i in ids])
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return ids, matrix / np.where(norms == 0, 1, norms)


# --- Tetangga terdekat ---
def _day(value):
    try:
        return datetime.fromisoformat(str(value)[:10]).toordinal()
    except (TypeError, ValueError):
        return None


def neighbors(ids, matrix, items, top_k=TOP_K, related_min=RELATED_MIN, chunk=2048):
    """Pasangan (incident, terkait, kemiripan) teratas per incident dalam jendela waktu."""
    import numpy as np

    days = np.array([_day(items[i]["published"]) or 0 for i in ids])
    known_day = np.array([_day(items[i]["published"]) is not None for i in ids])
    links = []
    for start in range(0, len(ids), chunk):
        block = matrix[start : start + chunk] @ matrix.T
        for offset, sims in enumerate(block):
            index = start + offset
            sims = sims.copy()
            sims[index] = -1
            if known_day[index]:
                sims[known_day & (np.abs(days - days[index]) > WINDOW_DAYS)] = -1
            best = np.argpartition(-sims, top_k)[:top_k]
            for j in best[np.argsort(-sims[best])]:
                if sims[j] < related_min:
                    break
                links.append((ids[index], ids[j], float(sims[j]), int(abs(days[index] - days[j]))))
    return links


def link_rows(links, items, model, now):
    rows = []
    for incident_id, related_id, similarity, gap in links:
        lang_a, lang_b = items[incident_id]["language"] or "", items[related_id]["language"] or ""
        cross = lang_a != lang_b and bool({lang_a, lang_b} & CROSS_LANGS)
        same = (similarity >= SAME_EVENT_MIN and gap <= SAME_EVENT_DAYS) or (cross and similarity >= CROSS_MIN and gap <= CROSS_DAYS)
        rows.append((incident_id, related_id, round(similarity, 4), int(same), int(cross), model, now))
    return rows


def store_links(rows, log=print):
    """Ganti isi incident_links di database masukan."""
    from csais.publish import TursoClient

    url = (os.environ.get("SURVEY_DATABASE_URL") or "").strip()
    insert = f"INSERT OR REPLACE INTO incident_links ({', '.join(LINK_COLUMNS)}) VALUES ({', '.join('?' for _ in LINK_COLUMNS)})"
    if url.startswith("file:"):
        conn = sqlite3.connect(url[len("file:"):])
        conn.execute(LINKS_SCHEMA)
        conn.execute("DELETE FROM incident_links")
        conn.executemany(insert, rows)
        conn.commit()
        conn.close()
        return
    token = os.environ.get("SURVEY_WRITE_TOKEN")
    if not url or not token:
        raise SystemExit("SURVEY_DATABASE_URL dan SURVEY_WRITE_TOKEN harus diisi")
    client = TursoClient(url, token)
    client.transaction([(LINKS_SCHEMA, []), ("DELETE FROM incident_links", [])])
    for start in range(0, len(rows), 500):
        client.transaction([(insert, list(r)) for r in rows[start : start + 500]])
    log(f"incident_links: {len(rows)} baris ditulis ke database masukan")


def run_embed(log=print):
    """Perintah lokal: embedding incident, tetangga terdekat, tulis incident_links."""
    base_url = (os.environ.get("LLM_BASE_URL") or "http://localhost:1234/v1").rstrip("/")
    model = os.environ.get("EMBED_MODEL") or EMBED_MODEL_DEFAULT
    items = incident_texts(_paged(INCIDENTS_SQL), _paged(DOCS_SQL))
    ids, matrix = embeddings(items, model, base_url, log)
    links = neighbors(ids, matrix, items)
    rows = link_rows(links, items, model, get_timestamp())
    same = sum(r[3] for r in rows)
    cross = sum(1 for r in rows if r[3] and r[4])
    log(f"Pasangan terkait: {len(rows)}, kemungkinan kejadian sama: {same} (lintas bahasa {cross})")
    if os.environ.get("EMBED_DRY") == "1":
        log("EMBED_DRY=1: hasil tidak ditulis.")
        return rows
    store_links(rows, log)
    return rows


# --- Tahap pipeline ---
def run():
    """Salin incident_links dari database masukan ke database pipeline (untuk diterbitkan)."""
    from csais.survey import fetch_rows

    print("\n==================================================")
    print("   INCIDENT TERKAIT (EMBEDDING)")
    print("==================================================")
    rows = fetch_rows(LINKS_SQL)
    if rows is None:
        print("SURVEY_DATABASE_URL belum diisi; tahap dilewati.")
        return
    started_at = get_timestamp()
    conn = get_connection()
    try:
        conn.execute(LINKS_SCHEMA)
        conn.execute("DELETE FROM incident_links")
        conn.executemany(
            f"INSERT OR REPLACE INTO incident_links ({', '.join(LINK_COLUMNS)}) VALUES ({', '.join('?' for _ in LINK_COLUMNS)})",
            rows,
        )
        conn.commit()
        record_run(conn, "incident_links", started_at, len(rows))
    finally:
        conn.close()
    print(f"Pasangan terkait disalin: {len(rows)}")
    print("==================================================")


if __name__ == "__main__":
    run()
